from flask import Blueprint, request
from rq import Queue

from trelolo.config import Config
from trelolo.rq_connect import rq_connect
from trelolo import worker

ALLOWED_WEBHOOK_ACTIONS = ('close', 'reopen')


def pick_data(json):
    data = json['object_attributes']
    picked = {
        'action': data['action'],
        'project_id': data['project_id'],
        'id': data['id'],
        'type': 'issue' if json['object_kind'] != 'merge_request' else 'mr',
        'state': data['state'] not in ('opened', 'reopened')
    }
    return picked


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
        json = request.json
        if json['object_attributes']['action'] in ALLOWED_WEBHOOK_ACTIONS:
            data = pick_data(json)
            q.enqueue(worker.payload_gitlab, data)
    return __name__
