import logging
from ..config import Config

from trelolo.trelolo.client import Trelolo

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
        hook.delete
        logger.warn('unhooking teamboard {}').format(hook.id)


def hook_teamboards(board_ids=[]):
    exclude = client.boards.keys()
    for board in client.list_boards():
        if board.id not in exclude and \
         board.id in board_ids and \
         not client.does_webhook_exist(board.id):
            webhook = client.create_hook(
                '{}/trello/teamboard'.format(client.webhook_url),
                board.id,
                token=client.resource_owner_key
            )
            if webhook:
                # TODO store to DB
                pass
            for card in board.open_cards():
                if card.labels:
                    label = card.labels[-1]
    return True


def unhook_teamboards(board_ids=[]):
    for board in client.list_boards():
        for hook in client.list_hooks(client.resource_owner_key):
            if board.id in board_ids:
                if hook.id_model == board.id:
                    hook.delete()
                    # TODO remove from DB
