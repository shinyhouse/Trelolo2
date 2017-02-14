from collections import OrderedDict
import logging
from trello import TrelloClient, ResourceUnavailable
from trelolo.trelolo import helpers
from trelolo import models
from trelolo.extensions import db

logger = logging.getLogger(__name__)


class Trelolo(TrelloClient):

    def setup_trelolo(self, mainboard_id, topboard_id, webhook_url):
        self.webhook_url = webhook_url
        self.boards = OrderedDict({
            mainboard_id: self.get_board_data(mainboard_id, {
                'prefix': '#',
                'remove': True
            }),
            topboard_id: self.get_board_data(topboard_id, {
                'prefix': 'OKR:',
                'remove': True
            })
        })
        if not self.does_webhook_exist(mainboard_id):
            self.create_hook(
                '{}/trello/mainboard'.format(self.webhook_url),
                mainboard_id,
                'mainboard: {}'.format(mainboard_id),
                token=self.resource_owner_key
            )

    def get_board_data(self, board_id, metadata):
        try:
            board = self.get_board(board_id)
            lists = board.open_lists() if board is not None else []
            inbox = next(
                (l for l in lists if l.name.lower() == 'inbox'),
                None
            )
            return {
                'board': board,
                'lists': lists,
                'inbox': inbox,
                'metadata': metadata
            }
        except ResourceUnavailable:
            logger.error('invalid board {}'.format(board_id))
            return False

    def does_webhook_exist(self, model_id):
        return any(
            i for i in self.list_hooks(self.resource_owner_key)
            if i.id_model == model_id
        )

    def handle_targets(self,
                       card,
                       targets=[],
                       stored_targets=[],
                       target_url='issues',
                       target_type='issue',
                       tag='GLIS'):
        """
        help to separate GL issues from merge requests
        return actual state of targets in db as well as
        new-found target info for a specific target type
        """
        trello_link = '* {}'.format(card.url)

        stored = {'{}*{}*{}'.format(
                    target_type,
                    target.project_id,
                    target.issue_id): target
                  for target in stored_targets
                  if target.target_type == target_type}

        fetched = [helpers.fetch_gitlab_target(
                    target, target_url, tag) for target in targets]

        fetched = {'{}*{}*{}'.format(
                    target_type,
                    target['project_id'],
                    target['id']): target for target in fetched if target}

        newfound = {k: v for k, v in fetched.items() if k not in stored.keys()}

        for k, target in newfound.items():
            # append to checklist
            card.checklists[0].add_checklist_item(
                target['title'], not target['opened']
            )
            # update db
            issue = models.Issues(
                issue_id=target['id'],
                project_id=target['project_id'],
                parent_card_id=card.id,
                item_id='',
                item_name=target['title'],
                label='',
                milestone='',
                hook_id='',
                hook_url='',
                checked=target['opened'],
                target_type=target_type
            )
            db.session.add(issue)
            db.session.commit()

            # update trello links
            if trello_link not in target['description'][1]:
                target['description'][1].append(
                    trello_link
                )
                logger.info(helpers.update_gitlab_description(
                    target['project_id'],
                    target_url,
                    target['id'],
                    target['description']
                ))

        # cleanup
        for k, target in stored.items():
            if k not in fetched.keys():
                card.checklists[0].delete_checklist_item(
                    target.item_name
                )
                desc = helpers.fetch_gitlab_target_description(
                    target.project_id,
                    target_url,
                    target.issue_id
                )
                # update trello links
                if desc:
                    if trello_link in desc[1]:
                        desc[1].remove(trello_link)
                    logger.info(helpers.update_gitlab_description(
                        target.project_id,
                        target_url,
                        target.issue_id,
                        desc
                    ))
                # update db
                db.session.delete(target)
                db.session.commit()

    def handle_teamboard_update_card(self,
                                     card_id,
                                     old_desc,
                                     new_desc):
        """
        check for GL targets in a teamboard's card description
        example:
        <
        $GLIS:<project_id>:<id>
        $GLMR:<project_id>:<id>
        >
        """
        # nothing happens if no change
        if old_desc is new_desc:
            return False
        # load data from storage
        stored_targets = models.Issues.query.filter_by(
            parent_card_id=card_id
        )
        # get card & its checklist
        card = self.get_card(card_id)
        card.fetch(eager=True)
        if not card.checklists:
            card.add_checklist('Issues', [], [])
        # parse what we have in an updated description
        targets = helpers.parse_gitlab_targets(new_desc)
        issues = self.handle_targets(
            card, targets, stored_targets, 'issues', 'issue', 'GLIS'
        )
        merge_requests = self.handle_targets(
            card, targets, stored_targets, 'merge_requests', 'mr', 'GLMR'
        )
        # TODO update trello link list in GL description
