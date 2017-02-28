from __future__ import absolute_import

from .app import create_app

import sys
import logging
from rainbow_logging_handler import RainbowLoggingHandler

log = logging.getLogger(__name__)
log.setLevel(logging.INFO)
formatter = logging.Formatter(
    "%(asctime)s %(name)s %(funcName)s():%(lineno)d\t%(message)s"
)
handler = RainbowLoggingHandler(sys.stderr)
handler.setFormatter(formatter)
log.addHandler(handler)
