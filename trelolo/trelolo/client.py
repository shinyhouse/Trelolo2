import copy
from collections import OrderedDict
import logging
import re
from trello import TrelloClient, ResourceUnavailable
from trelolo.trelolo import helpers
from trelolo.extensions import db
from trelolo import models

from .mixins import GitLabMixin

log = logging.getLogger(__name__)


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
                'remove': True,
                'desc_title': 'Main Board'
            }),
            topboard_id: self.get_board_data(topboard_id, {
                'prefix': 'OKR:',
                'remove': True,
                'desc_title': 'Top Board'
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
            log.error('invalid board {}'.format(board_id))
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

    def get_members(self, card):
        members = []
        for member_id in card.member_ids:
            members.append(self.get_member_email(member_id))
        try:
            found_emails = re.findall('[\w\.-]+@[\w\.-]+', card.desc)
            for email in found_emails:
                if email not in members:
                    members.append(email)
        except AttributeError:
            pass
        log.info(
            'found members: {}'.format(','.join(list(members)))
        )
        return members

    def get_member_email(self, member_id):
        try:
            member = self.get_member(member_id)
            stored_member = models.Emails.query.filter_by(
                username=member.username
            ).first()
            return stored_member.email
        except ResourceUnavailable:
            log.error(
                'could not fetch trello member {}'.format(member_id)
            )

    def add_label_to_gitlab_issues(self, parent_card, label):
        """
        Adds the OKR label to gitlab issues
        """
        issues = models.Issues.query.filter_by(
            parent_card_id=parent_card.id
        ).all()
        for issue in issues:
            project_id = issue.project_id
            log.info(
                'adding label to issue {}/{}'.format(project_id, issue.id)
            )
            try:
                self.create_gl_label(project_id, label)
            except Exception as e:
                log.error(
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
                log.error(
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
                    log.error(
                        'error adding OKR label to card {}: {}'.format(
                            tcard.name, str(e)
                        )
                    )
                # add label to gitlab issues
                self.add_label_to_gitlab_issues(tcard, label)
        except Exception as e:
            log.error('error adding OKR label: {}'.format(str(e)))

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
                log.error(
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
            log.info(
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
                log.error(
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
                    log.error(
                        'error removing OKR label from card {}: {}'.format(
                            tcard.name, str(e)
                        )
                    )
                self.remove_label_from_gitlab_issues(tcard, label)
        except Exception as e:
            log.error('error removing OKR label: {}'.format(str(e)))

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
            log.info(
                'changed {} label to {}'.format(
                    old_label, new_label
                )
            )

    def handle_generic_event(self, parent_board_id, card_id, stored_card):
        board_data = self.board_data[parent_board_id]
        card = self.get_card(card_id)
        card.fetch(eager=False)
        label = self.get_label(card.labels, board_data['metadata'])
        try:
            if label != stored_card.label:
                self.remove_checklist_item(stored_card)
                card.set_description('')
                db.session.delete(stored_card)
                stored_card = {}
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
            'state': completeness == 100,
            'members': self.get_members(card)
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
                log.info('found card {}'.format(card.name))
                # new item (the whole sub card)
                item = self.add_checklist_item(
                    card, child['title'], child['state']
                )
                # update child card description
                child['card'].set_description(
                    helpers.format_teamboard_card_descritpion(
                        board_data['metadata']['desc_title'],
                        child['card'].desc,
                        card.url
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
        try:
            parent_card_id = stored_card.parent_card_id \
                if stored_card else card.id
            parent_card = self.get_card(parent_card_id)
            cd = helpers.CardDescription(parent_card.desc)
            cd.set_list_value('members', child['members'])
            parent_card.set_description(cd.get_description())
        except Exception as e:
            log.warning(
                'failed to update parent card: {}'.format(str(e))
            )
        # save changes
        db.session.commit()
        try:
            pass
        except Exception as e:
            log.error(
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

    def update_checklist_item(self, item_name, checked, stored_card):
        if not stored_card:
            log.warning('card or item not specified')
            return False
        card = self.get_card(stored_card.parent_card_id)
        card.fetch(eager=False)
        cl = card.fetch_checklists()[0]
        # item = self.get_checklist_item(cl, stored_card.item_id)
        log.info(
            'updating item {} on card {}'.format(item_name, card.name)
        )
        upd = {}
        # check name change
        if item_name != stored_card.item_name:
            log.info(
                'renaming item {} to {}'.format(
                    stored_card.item_name, item_name
                )
            )
            cl.rename_checklist_item(stored_card.item_name, item_name)
            upd['item_name'] = item_name
        # check status change
        if checked != stored_card.checked:
            log.info(
                'set checked status {} to {}'.format(item_name, checked)
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
            log.error('could not remove checklist item')
        self.remove_webhook(
            stored_card.hook_id,
            stored_card.parent_card_id
        )

    def handle_delete_card(self, stored_card):
        self.remove_checklist_item(stored_card)
        db.session.delete(stored_card)
        db.session.commit()
        log.info('card has been succesfully deleted')

    # GITLAB WEBHOOKS

    @staticmethod
    def check_labels(labels, label):
        try:
            return any(
                l for l in labels if l.name[0] == '$'
                and l.name[1:] == label
            )
        except IndexError:
            return False

    def get_cards_for_gitlab(self, label, milestone):
        gl_cards = []
        for board in self.list_team_boards():
            cards = board.open_cards()
            for card in cards:
                if self.check_labels(card.labels, label):
                    gl_cards.append(card)
                if self.check_labels(card.labels, milestone):
                    gl_cards.append(card)
        return gl_cards

    def handle_gitlab_generic_event(self, data):
        stored_targets = models.Issues.query.filter_by(
            issue_id=str(data['id']),
            target_type=data['type']
        ).all()
        stored_targets = {target.parent_card_id: target
                          for target in stored_targets}
        stored_card_ids = [id for id in stored_targets.keys()]
        cards = self.get_cards_for_gitlab(data['label'], data['milestone'])
        trello_links = []
        if cards:
            for card in cards:
                try:
                    card.fetch(eager=False)
                    stored_card_ids.remove(card.id)
                except ValueError:
                    pass
                if card.id in stored_targets.keys():
                    target = stored_targets[card.id]
                    if data['label'] or data['milestone']:
                        log.info(
                            'updating gitlab item {} on card {}'.format(
                                target.item_name, card.name)
                        )
                        upd = self.update_checklist_item(
                            data['target_title'], data['state'], target
                        )
                        if upd and target:
                            target.item_name = data['target_title']
                            target.checked = data['state']
                        trello_links.append(
                            helpers.format_trello_link(card.url)
                        )
                    else:
                        log.info(
                            'removing gitlab item {} from card {}'.format(
                                target.item_name, card.name)
                        )
                        self.remove_checklist_item(target)
                        db.session.delete(target)
                else:
                    item = self.add_checklist_item(
                        card, data['target_title'], data['state']
                    )
                    new_item = models.Issues(
                        issue_id=data['id'],
                        project_id=data['project_id'],
                        parent_card_id=card.id,
                        label=data['label'],
                        milestone=data['milestone'],
                        item_id=item['id'],
                        item_name=data['target_title'],
                        checked=data['state'],
                        target_type=data['type'],
                        hook_id='',
                        hook_url=''
                    )
                    log.info(
                        'creating gitlab item {}'.format(data['target_title'])
                    )
                    db.session.add(new_item)
                    trello_links.append(helpers.format_trello_link(card.url))

                cd = helpers.CardDescription(card.desc)
                cd.set_list_value('members', data['assignee_email'] or '')
                card.set_description(cd.get_description())

            db.session.commit()
        else:
            log.warning(
                'no suitable card found on any team-board \
                 for label: {} or milestone: {}'.format(
                    data['label'], data['milestone']
                )
            )
        for card_id in stored_card_ids:
            target = stored_targets[card_id]
            log.info(
                'removing gitlab item {} from card {}'.format(
                    target.item_name, card_id)
            )
            self.remove_checklist_item(target)
            db.session.delete(target)
        db.session.commit()

        # update GL target description
        old_desc = self.parse_gl_target_desc(data['description'])
        new_desc = self.format_gl_desc([old_desc[0], trello_links])

        log.info(data['description'])
        log.info(new_desc)

        if new_desc != data['description']:
            self.update_gl_desc(
                data['project_id'],
                data['target_url'],
                data['id'],
                [old_desc[0], trello_links]
            )

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
                    log.error(
                        'could not fetch a checklist for card {}'.format(
                            card.name
                        )
                    )
            except ResourceUnavailable:
                log.error(
                    'could not get trello card {} for GL target {}'.format(
                        target.parent_card_id, id
                    )
                )
        db.session.commit()
        log.info(
            'succesfully synced trello GL items with GL target'
        )
