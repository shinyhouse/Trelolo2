from ..config import Config
from flask import Blueprint, request
from rq import Queue
from trelolo.rq_connect import rq_connect

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
    if request.method == 'POST':
        pass
    return __name__
