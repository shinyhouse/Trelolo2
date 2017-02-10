import logging

from .config import client


logger = logging.getLogger(__name__)


def foo():
    logger.info("GITLAB")
