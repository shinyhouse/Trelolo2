from flask import Blueprint, request
from rq import Queue

from trelolo.config import Config
from trelolo.extensions import rq
from trelolo import worker


ALLOWED_WEBHOOK_ACTIONS = (
    'addChecklistToCard', 'addLabelToCard', 'addMemberToCard',
    'deleteCard', 'removeLabelFromCard', 'updateCard',
    'updateCheckItemStateOnCard', 'updateLabel'
)


def pick_data(json):
    data = json['action']['data']
    picked = {
        'action': json['action']['type'],
        'card': {},
        'old': {},
        'label': {}
    }
    for i in ('card', 'old', 'label'):
        try:
            picked[i] = data[i]
        except KeyError:
            pass
    return picked


q = Queue(
    connection=rq,
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
            data = pick_data(json)
            if json['action']['type'] == 'updateCard':
                q.enqueue(worker.payload_teamboard_update_card, data)
            if json['action']['type'] == 'updateLabel':
                q.enqueue(
                    worker.payload_update_label,
                    Config.TRELOLO_MAIN_BOARD,
                    data
                )
            if json['action']['type'] == 'deleteCard':
                q.enqueue(worker.payload_delete_card, data)
            if json['action']['type'] in (
                'addLabelToCard',
                'addChecklistToCard',
                'updateCheckItemStateOnCard',
                'removeLabelFromCard'
            ):
                q.enqueue(
                    worker.payload_generic_event,
                    Config.TRELOLO_MAIN_BOARD,
                    data
                )
    return __name__


@bp.route(
    '/callback/trello/mainboard',
    methods=['GET', 'POST']
)
def mainboard_webhook():
    if request.method == 'POST':
        json = request.json
        if json['action']['type'] in ALLOWED_WEBHOOK_ACTIONS:
            data = pick_data(json)
            if json['action']['type'] == 'updateLabel':
                q.enqueue(
                    worker.payload_update_label,
                    Config.TRELOLO_TOP_BOARD,
                    data
                )
            if json['action']['type'] == 'deleteCard':
                q.enqueue(worker.payload_delete_card, data)
            if json['action']['type'] in (
                'addLabelToCard',
                'addChecklistToCard',
                'updateCheckItemStateOnCard',
                'removeLabelFromCard'
            ):
                q.enqueue(
                    worker.payload_generic_event,
                    Config.TRELOLO_TOP_BOARD,
                    data
                )
    return __name__


@bp.route(
    '/callback/trello/card/<card_id>/<issue_id>',
    methods=['GET', 'POST']
)
def card_webhook(card_id, issue_id):
    if request.method == 'POST':
        pass
    return __name__
