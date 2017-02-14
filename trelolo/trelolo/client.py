import logging

from collections import OrderedDict

from trello import WebHook, TrelloClient, ResourceUnavailable

from trelolo import models
from trelolo.trelolo import helpers
from trelolo.extensions import db

logger = logging.getLogger(__name__)


class Trelolo(TrelloClient, helpers.GitLabMixin):
    CHK_TITLE = "Issues"

    def setup_trelolo(self, mainboard_id, topboard_id, webhook_url):
        self.webhook_url = webhook_url
        self.board_data = OrderedDict({
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

    def get_hook_by_id(self, hook_id):
        url = '/webhooks/{}'.format(hook_id)
        hook_json = self.fetch_json(url)
        hook = WebHook(self, self.resource_owner_key, hook_json['id'], hook_json['description'],
                       hook_json['idModel'],
                       hook_json['callbackURL'], hook_json['active'])

        return hook

    def list_team_boards(self):
        boards = []

        team_boards = models.Boards.query.filter_by(type=3)
        for b in team_boards:
            board = self.get_board(b.trello_id)
            boards.append(board)

        return boards

    def list_sub_cards(self, parent_card):
        cards = []
        sub_cards = models.Cards.query.filter_by(parent_card_id=parent_card.id)
        for card in sub_cards:
            card = self.get_card(card['card_id'])
            card.fetch(eager=False)

            cards.append(card)

        return cards

    def add_members(self, data):
        pass
        # for member in data['members']:
        #     if member:
        #         self.gapi.add_member(data['label'], member)
        #         self.slackapi.add_member(data['label'], member)

    def add_card(self, board_data, data, data_storage):
        col = board_data['inbox']
        new_card = col.add_card(data['label'], desc=helpers.CardDescription.INIT_DESCRIPTION)

        logger.info("""created new card {} on board {}"""
                    .format(new_card.name, board_data['board'].name))

        data_storage['parent_card_id'] = new_card.id

        # self.gapi.create_group(data['label'])
        # self.slackapi.create_channel(data['label'])

        return new_card

    def update_card_description(self, card, data, data_storage):
        try:
            cd = helpers.CardDescription(card.desc)
            # cd.set_value('group email', self.gapi.get_project_mail(data['label']))
            # cd.set_value('slack channel', self.slackapi.get_channel_name(data['label']))

            if 'members' in data:
                cd.set_list_value('members', data['members'])

            card.set_description(cd.get_description())

            self.fetch_json(
                '/cards/' + card.id + '/desc',
                http_method='PUT',
                post_args={'value': cd.get_description()})
        except Exception as e:
            logger.error(e)
            pass

    def add_label_to_gitlab_issues(self, parent_card, label):
        """
        Adds the OKR label to gitlab issues
        """

        issues = models.Issues.query.filter_by(parent_card_id=parent_card.id)

        logger.debug("Found {} issues for card {}"
                     .format(len(issues), parent_card.name))

        for issue in issues:
            project_id = issue['project_id']

            logger.debug("Adding label to issue {}/{}"
                         .format(project_id, issue['id']))

            try:
                self.create_label(project_id, label)
            except Exception as e:
                logger.error("Error creating gitlab label {}: {}"
                             .format(label, str(e)))

            try:
                for source in self.sources:
                    try:
                        if source.TARGET_TYPE == issue['target_type']:
                            source.add_label(project_id, issue['issue_id'], label)
                    except AttributeError:
                        pass
            except Exception as e:
                logger.error("Error adding gitlab label {} to issue {}: {}"
                             .format(label, issue['issue_id'], str(e)))

    def okr_label_added(self, data, data_storage, board_data):
        """
        Adds an OKR label to team cards and gitlab issues.
        """

        label = data['data']['label']['name']
        color = data['data']['label']['color']

        logger.info("Adding {} label to team cards/gitlab issues"
                    .format(label))

        try:
            # prepare data ====================================================
            card = self.get_card(data['id'])

            # load team labels
            team_labels = {}
            for tboard in self.list_team_boards():
                tlabel = helpers.find_label(tboard.get_labels(), label)

                # create label if does not exist on board
                if not tlabel:
                    tlabel = self.trello_source.add_label_to_board(tboard, label, color)

                if tlabel:
                    team_labels[tboard.id] = tlabel

            # add label to teamboard cards ====================================
            team_board_cards = self.list_sub_cards(card)
            for tcard in team_board_cards:
                try:
                    tlabel = team_labels[tcard.board_id]
                    if tlabel:
                        tcard.add_label(tlabel)
                except Exception as e:
                    logger.error("Error adding OKR label to card {}: {}"
                                 .format(tcard.name, str(e)))

                # add label to gitlab issues ======================================
                self.add_label_to_gitlab_issues(tcard, label)
        except Exception as e:
            logger.error("Error adding OKR label: {}"
                         .format(str(e)))

    def add_okr_label_to_card(self, card, okr_label):
        logger.info("Adding OKR label %s to card %s",
                    okr_label.name,
                    card.name)

        tboard = card.board
        label, color = (okr_label.name, okr_label.color)
        tlabel = helpers.find_label(tboard.get_labels(), label)

        if not tlabel:
            tlabel = self.trello_source.add_label_to_board(tboard, label, color)

        if tlabel:
            try:
                card.add_label(tlabel)
            except Exception as e:
                logger.error("Error adding OKR label to card {}: {}"
                             .format(card.name, str(e)))

            # add label to gitlab issues ======================================
            self.add_label_to_gitlab_issues(card, label)

    def remove_label_from_gitlab_issues(self, parent_card, label):
        issues = models.Issues.query.filter_by(parent_card_id=parent_card.id)

        logger.debug("Found {} issues for card {}"
                     .format(len(issues), parent_card.name))

        for issue in issues:
            project_id = issue['project_id']

            logger.debug("Removing label from issue {}/{}"
                         .format(project_id, issue['id']))

            try:
                for source in self.sources:
                    try:
                        if source.TARGET_TYPE == issue['target_type']:
                            source.remove_label(project_id, issue['issue_id'], label)
                    except AttributeError:
                        pass
            except Exception as e:
                logger.error("Error removing label {} from issue {}: {}"
                             .format(label, issue['issue_id'], str(e)))

    def okr_label_removed(self, data, data_storage, board_data):
        """
        Removes the OKR label from team cards and gitlab issues.
        """

        label = data['data']['label']['name']

        logger.info("Removing {} label from team cards/gitlab issues"
                    .format(label))

        try:
            # prepare data ====================================================
            card = self.get_card(data['id'])

            # load team labels
            team_labels = {}
            for tboard in self.list_team_boards():
                tlabel = helpers.find_label(tboard.get_labels(), label)
                if tlabel:
                    team_labels[tboard.id] = tlabel

            # remove label from teamboard cards ===============================
            team_board_cards = self.list_sub_cards(card)
            for tcard in team_board_cards:
                try:
                    tlabel = team_labels[tcard.board_id]
                    if tlabel:
                        tcard.remove_label(tlabel)
                except Exception as e:
                    logger.error("Error removing OKR label from card {}: {}"
                                 .format(tcard.name, str(e)))

                # remove label from gitlab issues =================================
                self.remove_label_from_gitlab_issues(tcard, label)
        except Exception as e:
            logger.error("Error removing OKR label: {}"
                         .format(str(e)))

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
        self.handle_targets(
            card, targets, stored_targets, 'issues', 'issue', 'GLIS'
        )
        self.handle_targets(
            card, targets, stored_targets, 'merge_requests', 'mr', 'GLMR'
        )
        # TODO update trello link list in GL description
