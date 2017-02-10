import logging

from .config import trello_client


logger = logging.getLogger(__name__)


def foo():
    logger.info("TRELLO")
