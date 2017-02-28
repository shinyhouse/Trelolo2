import logging
from ..config import Config

from trelolo.trelolo.client import Trelolo
from trelolo import models
from trelolo.extensions import db

log = logging.getLogger(__name__)


client = Trelolo(api_key=Config.TRELOLO_API_KEY, token=Config.TRELOLO_TOKEN)

client.setup_trelolo(
    Config.TRELOLO_MAIN_BOARD,
    Config.TRELOLO_TOP_BOARD,
    Config.WEBHOOK_URL
)

client.setup_gitlab(
    Config.GITLAB_URL, Config.GITLAB_TOKEN
)


def get_card_from_db(card_id):
    try:
        return models.Cards.query.filter_by(card_id=card_id).first()
    except IndexError:
        return False


def payload_update_label(parent_board_id, data):
    try:
        client.handle_update_label(
            parent_board_id, data['old']['name'], data['label']['name']
        )
    except KeyError:
        pass


def payload_delete_card(data):
    card = get_card_from_db(data['card']['id'])
    try:
        if card:
            client.handle_delete_card(card)
    except KeyError:
        pass


def payload_generic_event(parent_board_id, data):
    try:
        stored_card = get_card_from_db(data['card']['id'])
        client.handle_generic_event(
            parent_board_id, data['card']['id'], stored_card
        )
        # okr exception
        if parent_board_id == Config.TRELOLO_TOP_BOARD:
            label = data['label']['name']
            if not label.startswith('OKR:'):
                return False
            card = client.get_card(data['card']['id'])
            if data['action'] == 'addLabelToCard':
                client.add_okr_label(
                    card, label, data['label']['color']
                )
            if data['action'] == 'removeLabelFromCard':
                client.remove_okr_label(card, label)
    except KeyError:
        pass


def payload_gitlab_generic_event(data):
    # these values are unfortunately not
    # in a webhook payload yet
    data['label'] = client.fetch_gl_labels(
        data['project_id'], data['target_url'], data['id']
    )
    data['milestone'] = client.fetch_gl_milestone(
        data['project_id'], data['milestone_id']
    )
    data['target_title'] = '[{} / {}]({})'.format(
        client.fetch_gl_project_name(data['project_id']),
        data['title'],
        data['url']
    )
    data['assignee_email'] = client.fetch_gl_assignee_email(
        data['assignee_id']
    )
    client.handle_gitlab_generic_event(data)


def payload_gitlab_state_change(data):
    try:
        client.handle_gitlab_state_change(
            data['project_id'], data['id'], data['type'], data['state']
        )
    except KeyError:
        pass


# these are run only from manage.py (be careful)
def unhook_all():
    for hook in client.list_hooks(client.resource_owner_key):
        found = models.Boards.query.filter_by(
            trello_id=hook.id_model
        ).first()
        if found:
            db.session.delete(found)
            db.session.commit()
        log.warning('unhooking: {}'.format(hook.desc))
        hook.delete()


def hook_teamboard(board_id):
    exclude = client.board_data.keys()
    for board in client.list_boards():
        if board.id not in exclude and \
         board.id == board_id and \
         not client.does_webhook_exist(board.id):
            webhook = client.create_hook(
                '{}/trello/teamboard'.format(client.webhook_url),
                board.id,
                'teamboard {}'.format(board.name),
                token=client.resource_owner_key
            )
            if webhook:
                insert_board = models.Boards(
                    trello_id=board.id,
                    name=board.name,
                    type=3,
                    hook_id=webhook.id,
                    hook_url=webhook.callback_url
                )
                db.session.add(insert_board)
                db.session.commit()
            for card in board.open_cards():
                card_list = card.get_list()
                # ignore archived lists
                if not card_list.closed:
                    client.handle_generic_event(
                        Config.TRELOLO_MAIN_BOARD, card.id, None
                    )
    return True


def unhook_teamboard(board_id):
    hooks = client.list_hooks(token=client.resource_owner_key)
    for board in client.list_boards():
        for hook in hooks:
            if board.id == board_id:
                if hook.id_model == board.id:
                    found = models.Boards.query.filter_by(
                        trello_id=hook.id_model
                    ).first()
                    if found:
                        db.session.delete(found)
                        db.session.commit()
                    log.warning('unhooking: {}').format(hook.desc)
                    hook.delete()
