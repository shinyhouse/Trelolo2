from flask import Blueprint, request
from rq import Queue

from trelolo.config import Config
from trelolo.rq_connect import rq_connect


ALLOWED_WEBHOOK_ACTIONS = (
    'open', 'close', 'reopen', 'update'
)

q = Queue(
    connection=rq_connect,
    default_timeout=Config.QUEUE_TIMEOUT
)

bp = Blueprint('gitlab', __name__)


@bp.route(
    '/callback/gitlab',
    methods=['GET', 'POST']
)
def gitlab_webhook():
    if request.method == 'POST':
        pass
    return __name__
