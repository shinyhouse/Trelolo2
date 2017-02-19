import copy
from collections import OrderedDict
import logging
from trello import TrelloClient, ResourceUnavailable
from trelolo.trelolo import helpers
from trelolo import models
from trelolo.extensions import db

from .mixins import GitLabMixin

logger = logging.getLogger(__name__)


class Trelolo(TrelloClient, GitLabMixin):

    CHECKLIST_TITLE = "Issues"

    def setup_gitlab(self, gitlab_url, gitlab_token):
        self.gitlab_url = gitlab_url
        self.gitlab_token = gitlab_token

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
            i for i in self.list_hooks(token=self.resource_owner_key)
            if i.id_model == model_id
        )

    def remove_webhook(self, hook_id, model_id):
        for hook in self.list_hooks(token=self.resource_owner_key):
            if hook.id == hook_id or \
             hook.id_model == model_id:
                hook.delete()

    def list_team_boards(self):
        boards = []
        team_boards = models.Boards.query.filter_by(type=3).all()
        for b in team_boards:
            board = self.get_board(b.trello_id)
            boards.append(board)
        return boards

    def list_sub_cards(self, parent_card):
        cards = []
        sub_cards = models.Cards.query.filter_by(
            parent_card_id=parent_card.id
        ).all()
        for card in sub_cards:
            card = self.get_card(card.card_id)
            card.fetch(eager=False)
            cards.append(card)
        return cards

    def add_members(self, data):
        pass

    def add_label_to_gitlab_issues(self, parent_card, label):
        """
        Adds the OKR label to gitlab issues
        """
        issues = models.Issues.query.filter_by(
            parent_card_id=parent_card.id
        ).all()
        for issue in issues:
            project_id = issue.project_id
            logger.info(
                'adding label to issue {}/{}'.format(project_id, issue.id)
            )
            try:
                self.create_gl_label(project_id, label)
            except Exception as e:
                logger.error(
                    'error creating gitlab label {}: {}'.format(label, str(e))
                )
            try:
                self.add_gl_label(
                    project_id,
                    issue.issue_id,
                    'issues' if issue.target_type == 'issue'
                    else 'merge_requests',
                    label
                )
            except Exception as e:
                logger.error(
                    'error adding gitlab label {} to issue {}: {}'.format(
                        label, issue.issue_id, str(e)
                    )
                )

    def add_okr_label(self, card, label, color):
        """
        Adds an OKR label to team cards and gitlab issues.
        """
        try:
            # load team labels
            team_labels = {}
            for tboard in self.list_team_boards():
                tlabel = self.find_label(tboard.get_labels(), label)
                # create label if does not exist on board
                if not tlabel:
                    tlabel = tboard.add_label(label, color)
                if tlabel:
                    team_labels[tboard.id] = tlabel
            # add label to teamboard cards
            team_board_cards = self.list_sub_cards(card)
            for tcard in team_board_cards:
                try:
                    tlabel = team_labels[tcard.board_id]
                    if tlabel:
                        tcard.add_label(tlabel)
                except Exception as e:
                    logger.error(
                        'error adding OKR label to card {}: {}'.format(
                            tcard.name, str(e)
                        )
                    )
                # add label to gitlab issues
                self.add_label_to_gitlab_issues(tcard, label)
        except Exception as e:
            logger.error('error adding OKR label: {}'.format(str(e)))

    def add_okr_label_to_card(self, card, okr_label):
        tboard = card.board
        label, color = (okr_label.name, okr_label.color)
        tlabel = self.find_label(tboard.get_labels(), label)
        if not tlabel:
            tlabel = tboard.add_label(label, color)
        if tlabel:
            try:
                card.add_label(tlabel)
            except Exception as e:
                logger.error(
                    'error adding OKR label to card {}: {}'.format(
                        card.name, str(e)
                    )
                )
            self.add_label_to_gitlab_issues(card, label)

    def remove_label_from_gitlab_issues(self, parent_card, label):
        issues = models.Issues.query.filter_by(
            parent_card_id=parent_card.id
        ).all()
        for issue in issues:
            project_id = issue.project_id
            logger.info(
                'removing label from issue {}/{}'.format(
                    project_id, issue.id
                )
            )
            try:
                self.remove_gl_label(
                    project_id,
                    issue.issue_id,
                    'issues' if issue.target_type == 'issue'
                    else 'merge_requests',
                    label
                )
            except Exception as e:
                logger.error(
                    'error removing label {} from issue {}: {}'.format(
                        label, issue.issue_id, str(e)
                    )
                )

    def remove_okr_label(self, card, label):
        """
        Removes the OKR label from team cards and gitlab issues.
        """
        try:
            team_labels = {}
            for tboard in self.list_team_boards():
                tlabel = self.find_label(tboard.get_labels(), label)
                if tlabel:
                    team_labels[tboard.id] = tlabel
            team_board_cards = self.list_sub_cards(card)
            for tcard in team_board_cards:
                try:
                    tlabel = team_labels[tcard.board_id]
                    if tlabel:
                        tcard.remove_label(tlabel)
                except Exception as e:
                    logger.error(
                        'error removing OKR label from card {}: {}'.format(
                            tcard.name, str(e)
                        )
                    )
                self.remove_label_from_gitlab_issues(tcard, label)
        except Exception as e:
            logger.error('error removing OKR label: {}'.format(str(e)))

    def handle_targets(self,
                       card,
                       targets=[],
                       stored_targets=[],
                       target_url='issues',
                       target_type='issue',
                       tag='GLIS'):

        trello_link = '* {}'.format(card.url)

        stored = {'{}*{}*{}'.format(
                    target_type,
                    target.project_id,
                    target.issue_id): target
                  for target in stored_targets
                  if target.target_type == target_type}

        fetched = [self.fetch_gl_target(
                    target, target_url, tag) for target in targets]

        fetched = {'{}*{}*{}'.format(
                    target_type,
                    target['project_id'],
                    target['id']): target for target in fetched if target}

        newfound = {k: v for k, v in fetched.items() if k not in stored.keys()}

        for k, target in newfound.items():
            cl = card.checklists[0]
            for ei in cl.items:
                if ei['name'] == target['title']:
                    logger.error(
                        'removing duplicate item: {}'.format(
                            ei['id']
                        )
                    )
                    # @HACK custom trello API call
                    self.fetch_json(
                        '/checklists/{}/checkItems/{}'.format(
                            cl.id, ei['id']
                        ),
                        http_method='DELETE'
                    )
                    del ei
            # append to checklist
            item = card.checklists[0].add_checklist_item(
                target['title'], target['checked']
            )
            # update db
            issue = models.Issues(
                issue_id=target['id'],
                project_id=target['project_id'],
                parent_card_id=card.id,
                item_id=item['id'],
                item_name=target['title'],
                label='',
                milestone='',
                hook_id='',
                hook_url='',
                checked=target['checked'],
                target_type=target_type
            )
            db.session.add(issue)
            db.session.commit()

            # update trello links
            if trello_link not in target['description'][1]:
                target['description'][1].append(
                    trello_link
                )
                logger.info(self.update_gl_desc(
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
                desc = self.fetch_gl_target_desc(
                    target.project_id,
                    target_url,
                    target.issue_id
                )
                # update trello links
                if desc:
                    if trello_link in desc[1]:
                        desc[1].remove(trello_link)
                    logger.info(self.update_gl_desc(
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
        seeks for GL targets in a teamboard's card description
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
        ).all()
        # get card & its checklist
        card = self.get_card(card_id)
        card.fetch(eager=True)
        if not card.checklists:
            card.add_checklist(self.CHECKLIST_TITLE, [], [])
        # parse what we have in an updated description
        targets = self.parse_gl_targets(new_desc)

        self.handle_targets(
            card, targets, stored_targets, 'issues', 'issue', 'GLIS'
        )
        self.handle_targets(
            card, targets, stored_targets, 'merge_requests', 'mr', 'GLMR'
        )

    @staticmethod
    def get_completeness(card):
        try:
            cl = card.fetch_checklists()[0]
            completed_tasks = sum([item['checked'] for item in cl.items])
            return completed_tasks / len(cl.items) * 100
        except (IndexError, ZeroDivisionError):
            return -1

    @staticmethod
    def find_label(labels, label_name):
        return next(
            (label for label in labels if label.name == label_name), None
        )

    @staticmethod
    def find_card(board_data, card_name):
        return next(
            (card for card in board_data['board'].open_cards()
             if card.name == card_name), None
        )

    @staticmethod
    def get_label(labels, label_data):
        try:
            try:
                project_labels = [l.name for l in labels if
                                  l.name.startswith(label_data['prefix'])]
            except AttributeError:
                project_labels = [l['name'] for l in labels if
                                  l['name'].startswith(label_data['prefix'])]
            tag = project_labels[-1]
            if label_data['remove']:
                tag = tag[len(label_data['prefix']):]
            return tag
        except IndexError:
            return False
        return False

    def handle_update_label(self, parent_board_id, old_tag, new_tag):
        board_data = self.board_data[parent_board_id]
        old_label = self.get_label(
            [{'name': old_tag}], board_data['metadata']
        )
        new_label = self.get_label(
            [{'name': new_tag}], board_data['metadata']
        )
        card = self.find_card(board_data, old_label)
        if card:
            card.set_name(new_label)
            models.Cards.query.filter_by(
                label=old_label
            ).update({models.Cards.label: new_label})
            logger.info(
                'changed {} label to {}'.format(
                    old_label, new_label
                )
            )

    def handle_generic_event(self, parent_board_id, card_id, stored_card):
        board_data = self.board_data[parent_board_id]
        card = self.get_card(card_id)
        card.fetch(eager=False)
        label = self.get_label(card.labels, board_data['metadata'])
        # if label has been changed(removed) on a card
        try:
            if label != stored_card.label:
                self.remove_checklist_item(stored_card)
                card.set_description('')
                db.session.delete(stored_card)
                db.session.commit()
        except (AttributeError, TypeError):
            pass
        # useful dict for later
        completeness = self.get_completeness(card)
        child = {
            'card': copy.deepcopy(card),
            'title': helpers.format_itemname(
                completeness, card.url, card.get_list().name
            ),
            'state': completeness == 100
        }
        if label:
            if not stored_card:
                # search for suitable parent cards
                card = self.find_card(board_data, label)
                if card is None:
                    card = board_data['inbox'].add_card(
                        label,
                        desc=helpers.CardDescription.INIT_DESCRIPTION
                    )
                card.fetch(eager=False)
                # new item (the whole sub card)
                item = self.add_checklist_item(
                    card, child['title'], child['state']
                )
                # update child card description
                child['card'].set_description(
                    helpers.format_teamboard_card_descritpion(
                        child['card'].description, card.url
                    )
                )
                # insert into db
                new_card = models.Cards(
                    card_id=child['card'].id,
                    board_id=child['card'].board_id,
                    parent_card_id=card.id,
                    item_id=item['id'],
                    item_name=child['title'],
                    label=label,
                    checked=child['state'],
                    hook_id=item['hook_id'],
                    hook_url=item['hook_url']
                )
                db.session.add(new_card)
                okr_label = next(
                    (label for label in card.labels
                     if label.name.startswith('OKR:')), None
                )
                if okr_label:
                    self.add_okr_label_to_card(child['card'], okr_label)
            else:
                upd = self.update_checklist_item(
                    child['title'], child['state'], stored_card
                )
                if upd and stored_card:
                    stored_card.item_name = child['title']
                    stored_card.checked = child['state']
        # save changes
        db.session.commit()
        try:
            pass
        except Exception as e:
            logger.error(
                'Error updating card description: {}'.format(str(e))
            )

    def add_checklist_item(self, card, item_name, checked):
        try:
            cl = card.fetch_checklists()[0]
        except IndexError:
            cl = card.add_checklist(self.CHECKLIST_TITLE, [], [])
        item = cl.add_checklist_item(item_name, checked)
        hook = self.create_hook(
            "/trello/{}/{}".format(card.id, item['id']),
            card.id,
            '',
            token=self.resource_owner_key
        )
        return {
            'id': item['id'],
            'hook_id': hook.id if hook else '',
            'hook_url': hook.callback_url if hook else ''
        }
        # self.add_members(data)

    def update_checklist_item(self, item_name, checked, stored_card):
        if not stored_card:
            logger.error('card or item not specified')
            return False
        card = self.get_card(stored_card.parent_card_id)
        card.fetch(eager=False)
        cl = card.fetch_checklists()[0]
        item = self.get_checklist_item(cl, stored_card.item_id)
        logger.info(
            'updating item {} on card {}'.format(
                item['name'], card.name)
        )
        upd = {}
        # check name change
        if item_name != stored_card.item_name:
            logger.info(
                'renaming item {} to {}'.format(
                    stored_card.item_name, item_name
                )
            )
            cl.rename_checklist_item(stored_card.item_name, item_name)
            upd['item_name'] = item_name
        # check status change
        if checked != stored_card.checked:
            logger.info(
                'set checked status {} to {}'.format(
                    item_name, checked
                )
            )
            cl.set_checklist_item(item_name, checked)
            upd['checked'] = checked
        return upd
        # self.add_members(data)

    @staticmethod
    def get_checklist_item(checklist, item_id):
        return next(
            (item for item in checklist.items if item['id'] == item_id), None
        )

    def remove_checklist_item(self, stored_card):
        try:
            card = self.get_card(stored_card.parent_card_id)
            card.fetch(eager=False)
            cl = card.fetch_checklists()[0]
            item = self.get_checklist_item(
                cl, stored_card.item_id
            )
            cl.delete_checklist_item(item['name'])
        except:
            logger.error('could not remove checklist item')
        self.remove_webhook(
            stored_card.hook_id,
            stored_card.card_id
        )

    def handle_delete_card(self, stored_card):
        self.remove_checklist_item(stored_card)
        db.session.delete(stored_card)
        db.session.commit()
        logger.info("deleteCard payload handled succesfully")

    def handle_gitlab_state_change(self, project_id, id, type, state):
        stored_targets = models.Issues.query.filter_by(
            project_id=str(project_id),
            issue_id=str(id),
            target_type=type
        ).all()
        for target in stored_targets:
            try:
                card = self.get_card(target.parent_card_id)
                card.fetch(eager=False)
                try:
                    cl = card.fetch_checklists()[0]
                    item = self.get_checklist_item(cl, target.item_id)
                    cl.set_checklist_item(item['name'], state)
                    target.checked = state
                except:
                    logger.error(
                        'could not fetch a checklist for card {}'.format(
                            card.name
                        )
                    )
            except ResourceUnavailable:
                logger.error(
                    'could not get trello card {} for GL target {}'.format(
                        target.parent_card_id, id
                    )
                )
        db.session.commit()
        logger.info(
            'succesfully synced trello GL items with GL target'
        )
