from flask import Blueprint, request
from rq import Queue

from trelolo.config import Config
from trelolo.rq_connect import rq_connect
from trelolo.tasks.gitlab import foo


q = Queue(
    connection=rq_connect,
    default_timeout=Config.QUEUE_TIMEOUT
)

bp = Blueprint('gitlab', __name__)


@bp.route(
    '/callback/gitlab',
    methods=['GET', 'POST']
)
def webhook_gitlab():
    q.enqueue(foo)
    if request.method == 'POST':
        pass
    return __name__
