import logging
from ..config import Config

from trelolo.trelolo.client import Trelolo, BoardType
from trelolo import models
from trelolo.extensions import db

logger = logging.getLogger(__name__)


client = Trelolo(api_key=Config.TRELOLO_API_KEY, token=Config.TRELOLO_TOKEN)

client.setup_trelolo(
    Config.TRELOLO_MAIN_BOARD,
    Config.TRELOLO_TOP_BOARD,
    Config.WEBHOOK_URL
)


def payload_teamboard_update_card(json):
    print(json)


def payload_teamboard_add_label(json):
    print(json)


def payload_teamboard_remove_label(json):
    print(json)


# DB

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
    exclude = client.boards.keys()
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
                    type=BoardType.TEAMBOARD,
                    hook_id=webhook.id,
                    hook_url=webhook.callback_url
                )
                db.session.add(insert_board)
                db.session.commit()

            for card in board.open_cards():
                if card.labels:
                    label = card.labels[-1]
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
