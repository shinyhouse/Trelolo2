import logging
from ..config import Config

from trelolo.trelolo.client import Trelolo
from trelolo import models
from trelolo.extensions import db

logger = logging.getLogger(__name__)


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
        logger.info(card_id)
    except IndexError:
        return False


def payload_teamboard_update_card(data):
    try:
        client.handle_teamboard_update_card(
            data['card']['id'],
            data['old']['desc'],
            data['card']['desc']
        )
    except KeyError:
        pass


def payload_update_label(parent_board_id, data):
    try:
        client.handle_update_label(
            parent_board_id,
            data['old']['name'],
            data['label']['name']
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
        client.handle_generic_event(
            parent_board_id,
            data['card']['id'],
            get_card_from_db(data['card']['id'])
        )
    except KeyError:
        pass


# these are run from manage.py (be careful)
def unhook_all():
    for hook in client.list_hooks(client.resource_owner_key):
        found = models.Boards.query.filter_by(
            trello_id=hook.id_model
        ).first()
        if found:
            db.session.delete(found)
            db.session.commit()
        logger.warning('unhooking: {}'.format(hook.desc))
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
                if card.labels:
                    pass
                    # label = card.labels[-1]
    return True


def unhook_teamboard(board_id):
    hooks = client.list_hooks(client.resource_owner_key)
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
                    logger.warning('unhooking: {}').format(hook.desc)
                    hook.delete()
