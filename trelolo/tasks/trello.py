import logging

from .config import trello_client


logger = logging.getLogger(__name__)


def foo():
    for board in trello_client.list_boards():
        logger.info(board.name)
