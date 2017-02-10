import logging

from .config import client
import trelolo.helpers as helpers


logger = logging.getLogger(__name__)


def foo():
    logger.error(helpers.webhook_url_teamboard())
    for board in client.list_boards():
        logger.info(board.name)
