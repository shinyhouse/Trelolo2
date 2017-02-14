from flask import Blueprint, request
from rq import Queue

from trelolo.config import Config
from trelolo.rq_connect import rq_connect
from trelolo import worker


ALLOWED_WEBHOOK_ACTIONS = (
    'addChecklistToCard', 'addLabelToCard', 'addMemberToCard',
    'deleteCard', 'removeLabelFromCard', 'updateCard',
    'updateCheckItemStateOnCard', 'updateLabel'
)


q = Queue(
    connection=rq_connect,
    default_timeout=Config.QUEUE_TIMEOUT
)

bp = Blueprint('trello', __name__)


@bp.route(
    '/callback/trello/teamboard',
    methods=['GET', 'POST']
)
def teamboard_webhook():
    if request.method == 'POST':
        json = request.json
        if json['action']['type'] in ALLOWED_WEBHOOK_ACTIONS:
            if json['action']['type'] == 'updateCard':
                q.enqueue(worker.payload_teamboard_update_card, json)
    return __name__


@bp.route(
    '/callback/trello/mainboard',
    methods=['GET', 'POST']
)
def mainboard_webhook():
    if request.method == 'POST':
        pass
    return __name__


@bp.route(
    '/callback/trello/card/<card_id>/<issue_id>',
    methods=['GET', 'POST']
)
def card_webhook(card_id, issue_id):
    if request.method == 'POST':
        pass
    return __name__
