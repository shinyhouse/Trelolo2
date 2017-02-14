from collections import OrderedDict
from enum import Enum
import json
import logging
from trello import TrelloClient, ResourceUnavailable, Unauthorized, WebHook

from ..models import Boards, Cards, Issues
from trelolo.trelolo.helpers import CardDescription, get_list_num, find_card, update_label, add_attachment_to_card, \
    check_labels, find_label, get_checklist_item, move_card, is_todo_column, GitLabMixin, urls_into_description

logger = logging.getLogger(__name__)


class Trelolo(TrelloClient, GitLabMixin):
    CHK_TITLE = "Issues"

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
            i for i in self.list_hooks(self.resource_owner_key)
            if i.id_model == model_id
        )

    def list_team_boards(self):
        boards = []

        team_boards = Boards.query.filter_by(type=3)
        print(json.dumps(team_boards, indent=4))

        for b in team_boards:
            board = self.get_board(b.trello_id)
            boards.append(board)

        return boards

    def list_sub_cards(self, parent_card):
        cards = []

        sub_cards = Cards.query.filter_by(parent_card_id=parent_card.id)
        for card in sub_cards:
            card = self.get_card(card['card_id'])
            card.fetch(eager=False)

            cards.append(card)

        return cards

    def get_hook_by_id(self, hook_id):
        url = '/webhooks/{}'.format(hook_id)
        hook_json = self.fetch_json(url)
        hook = WebHook(self, self.resource_owner_key, hook_json['id'], hook_json['description'],
                       hook_json['idModel'],
                       hook_json['callbackURL'], hook_json['active'])

        return hook

    def hook_card(self, card_id, item_id):
        url = '{}/trello/card/{}/{}'.format(self.webhook_url, card_id, item_id)
        return self.create_hook(url,
                                item_id,
                                '',
                                self.resource_owner_key)

    def add_members(self, data):
        pass
        # for member in data['members']:
        #     if member:
        #         self.gapi.add_member(data['label'], member)
        #         self.slackapi.add_member(data['label'], member)

    def add_card(self, board_data, data, data_storage):
        col = board_data['inbox']
        new_card = col.add_card(data['label'], desc=CardDescription.INIT_DESCRIPTION)

        logger.info("""created new card {} on board {}"""
                    .format(new_card.name, board_data['board'].name))

        data_storage['parent_card_id'] = new_card.id

        # self.gapi.create_group(data['label'])
        # self.slackapi.create_channel(data['label'])

        return new_card

    def check_card_list(self, board_data, data):
        card = self.get_card(data['storage']['parent_card_id'])
        card.fetch(eager=False)
        cl = card.fetch_checklists()[0]

        checked = sum([not is_todo_column(cl_item['name']) or
                       cl_item['checked'] for cl_item in cl.items])
        list_num = int(checked > 0)

        logger.info("""moving card {} to list #{}"""
                    .format(card.name,
                            list_num))

        move_card(board_data, card, list_num)

    def add_checklist_item(self, card, data, data_storage):
        card.fetch(eager=False)

        logger.info("""adding item {} to card {}"""
                    .format(data['name'],
                            card.name))

        try:
            cl = card.fetch_checklists()[0]
        except IndexError:
            cl = card.add_checklist(self.CHK_TITLE, [])

        new_item = cl.add_checklist_item(data['name'], data['checked'])

        url = '{}/trello/card/{}/{}'.format(self.webhook_url, card.id, new_item['id'])
        hook = self.create_hook(url,
                                new_item['id'],
                                '',
                                self.resource_owner_key)

        data['item_id'] = new_item['id']

        data_storage['label'] = data['label']
        data_storage['checked'] = data['checked']
        data_storage['parent_card_id'] = card.id
        data_storage['item_id'] = data['item_id']
        data_storage['item_name'] = data['name']

        if hook:
            data_storage['hook_id'] = hook.id
            data_storage['hook_url'] = hook.callback_url

        self.add_members(data)

    def update_checklist_item(self, data, data_storage):
        if 'parent_card_id' not in data_storage or 'item_id' not in data_storage:
            logger.error("card or item not specified")
            return False

        card = self.get_card(data_storage['parent_card_id'])
        card.fetch(eager=False)
        cl = card.fetch_checklists()[0]

        item = get_checklist_item(cl, data_storage['item_id'])

        logger.info("""updating item {} on card {}"""
                    .format(item['name'],
                            card.name))

        # check name change
        if data['name'] != data_storage['item_name']:
            logger.debug("renaming item {} to {}"
                         .format(data_storage['item_name'], data['name']))

            cl.rename_checklist_item(data_storage['item_name'],
                                     data['name'])
            data_storage['item_name'] = data['name']

        # check status change
        if data['checked'] != data_storage['checked']:
            logger.debug("set checked status {} to {}"
                         .format(data['name'], data['checked']))

            cl.set_checklist_item(data['name'],
                                  data['checked'])

            data_storage['checked'] = data['checked']

        self.add_members(data)

    def remove_checklist_item(self, data, data_storage):
        if 'parent_card_id' not in data_storage or 'item_id' not in data_storage:
            logger.error("card or item not specified")
            return False

        try:
            card = self.get_card(data_storage['parent_card_id'])
            card.fetch(eager=False)
            cl = card.fetch_checklists()[0]

            item = get_checklist_item(cl, data_storage['item_id'])

            logger.info("""removing item {} from card {}"""
                        .format(item['name'],
                                card.name))

            cl.delete_checklist_item(item['name'])

            logger.info("deleting hook {}"
                        .format(data_storage['hook_id']))
            hook = self.get_hook_by_id(data_storage['hook_id'])
            hook.delete()
        except:
            pass

        try:
            self.trello_source.delete_hook(data['id'])
        except:
            pass

    def update_card_description(self, card, data, data_storage):
        try:
            cd = CardDescription(card.desc)
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

        issues = Issues.query.filter_by(parent_card_id=parent_card.id)

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
                tlabel = find_label(tboard.get_labels(), label)

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
        tlabel = find_label(tboard.get_labels(), label)

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
        issues = Issues.query.filter_by(parent_card_id=parent_card.id)

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
                tlabel = find_label(tboard.get_labels(), label)
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

    def update_on_trello_change(self, board_id, response):
        board_data = self.board_data[board_id]
        data = self.trello_source.normalize_board_response(response,
                                                           board_data['label_data'])

        if data:
            action = data['action']
            data_storage = data['storage']

            if action == 'deleteCard':
                self.remove_checklist_item(data, data_storage)
                self.trello_source.remove_data(data_storage['id'])
                Cards.query.get(data['id']).delete()
                return

            if action == 'updateLabel':
                update_label(board_data, data)
                return

            if action == 'addAttachmentToCard':
                add_attachment_to_card(board_data, data)
                return

            try:
                if data['label'] != data_storage['label']:
                    self.remove_checklist_item(data, data_storage)
                    self.trello_source \
                        .update_teamboard_card_description(data['card'], "")
                    self.trello_source.remove_data(data['id'])
                    Cards.query.get(data_storage['id']).delete()
                    data['storage'] = data_storage = {}
            except KeyError:
                pass

            if data['label']:
                if 'parent_card_id' not in data_storage:
                    card = find_card(board_data, data['label'])
                    if card is None:
                        card = self.add_card(board_data, data, data_storage)

                    card.fetch(eager=False)
                    data_storage['card_id'] = data['id']
                    data_storage['hook_id'] = ''
                    data_storage['hook_url'] = ''
                    data_storage['board_id'] = card.board_id

                    self.add_checklist_item(card, data, data_storage)

                    self.trello_source \
                        .update_teamboard_card_description(data['card'],
                                                           card.url)

                    okr_label = self.trello_source.get_okr_label(card)
                    if okr_label:
                        self.add_okr_label_to_card(data['card'], okr_label)
                else:
                    self.update_checklist_item(data, data_storage)

            if data['storage'] != {}:
                self.trello_source.save_data(data['id'], data_storage)

            try:
                card = self.get_card(data_storage['parent_card_id'])
                self.update_card_description(card, data, data_storage)
            except Exception as e:
                logger.error("Error updating card description: {}"
                             .format(str(e)))

            # check OKR label for mainboard ===================================
            if action == 'addLabelToCard' \
                    and board_data['type'] == 'top' \
                    and response['action']['data']['label']['name'].startswith('OKR:'):
                self.okr_label_added(data, data_storage, board_data)
                return

            if action == 'removeLabelFromCard' \
                    and board_data['type'] == 'top' \
                    and response['action']['data']['label']['name'].startswith('OKR:'):
                self.okr_label_removed(data, data_storage, board_data)
                return

    def get_cards_for_gitlab(self, label):
        gl_cards = []
        for board in self.list_team_boards():
            cards = board.all_cards()
            for card in cards:
                if check_labels(card.labels, label):
                    gl_cards.append(card)
        return gl_cards

    def update_on_gitlab_change(self, card_id, issue_id, response):
        data = self.normalize_card_response(response)
        if data:
            urls = []
            logger.debug("""data: {}"""
                         .format(json.dumps(data, indent=4)))

            cards = self.get_cards_for_gitlab(data['label'])
            cards += self.get_cards_for_gitlab(data['milestone'])

            old_card_ids = [cid for cid in data['storage']]

            logger.debug("""old_card_ids: {}"""
                         .format(old_card_ids))

            if cards:
                for card in cards:
                    try:
                        old_card_ids.remove(card.id)
                    except ValueError:
                        pass

                    if card.id in data['storage']:
                        data_storage = data['storage'][card.id]

                        if data['label'] or data['milestone']:
                            logger.info("updating gitlab item {} on card {}"
                                        .format(data_storage['item_name'],
                                                card.name))
                            self.update_checklist_item(data, data['storage'][card.id])

                            urls.append(card.url)

                        else:
                            logger.info("removing gitlab item {} from card {}"
                                        .format(data_storage['item_name'], card.name))

                            self.remove_checklist_item(data, data_storage)
                    else:
                        logger.info("creating gitlab item")

                        data['storage'][card.id] = {
                            'issue_id': data['id'],
                            'project_id': data['project_id'],
                            'hook_id': '',
                            'hook_url': '',
                            'label': data['label'],
                            'milestone': data['milestone'],
                            'target_type': data['target_type']
                        }

                        urls.append(card.url)

                        self.add_checklist_item(card,
                                                data,
                                                data['storage'][card.id])

                self.gl_source.save_data(data['id'], data['storage'])
            else:
                logger.warn("""no suitable card found on any
                               team-board for label: {} or milestone: {}"""
                            .format(data['label'], data['milestone']))

            for card_id in old_card_ids:
                data_storage = data['storage'][card_id]
                logger.info("removing gitlab item {} from card {}"
                            .format(data_storage['item_name'], card_id))

                self.remove_checklist_item(data, data_storage)
                Issues.query.get(data_storage['id']).delete()

            # update description trello links
            desc = urls_into_description(data['description'], urls)

            if desc != data['description']:
                self.update_gitlab_description(data['project_id'],
                                               data['id'],
                                               desc)
