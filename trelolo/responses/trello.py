from flask import Blueprint, request
from rq import Queue

from trelolo.config import Config
from trelolo.rq_connect import rq_connect
from trelolo.tasks.trello import foo


q = Queue(
    connection=rq_connect,
    default_timeout=Config.QUEUE_TIMEOUT
)

bp = Blueprint('trello', __name__)


@bp.route(
    '/callback/trello/teamboard',
    methods=['GET', 'POST']
)
def webhook_teamboard():
    q.enqueue(foo)
    if request.method == 'POST':
        pass
    return __name__


@bp.route(
    '/callback/trello/mainboard',
    methods=['GET', 'POST']
)
def webhook_mainboard():
    if request.method == 'POST':
        pass
    return __name__


@bp.route(
    '/callback/trello/topboard',
    methods=['GET', 'POST']
)
def webhook_topboard():
    if request.method == 'POST':
        pass
    return __name__


@bp.route(
    '/callback/trello/card/<card_id>/<issue_id>',
    methods=['GET', 'POST']
)
def webhook_card(card_id, issue_id):
    if request.method == 'POST':
        pass
    return __name__
