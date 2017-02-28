from flask import Blueprint, request
from rq import Queue

from trelolo.config import Config
from trelolo.extensions import rq
from trelolo import worker

ALLOWED_WEBHOOK_ACTIONS = ('open', 'update', 'close', 'reopen')


def pick_data(json):
    data = json['object_attributes']
    picked = {
        'action': data['action'],
        'id': data['id'],
        'title': data['title'],
        'url': data['url'],
        'milestone_id': data['milestone_id'],
        'description': data['description'],
        'type': 'issue' if json['object_kind'] != 'merge_request' else 'mr',
        'target_url': 'issues'
                      if json['object_kind'] != 'merge_request'
                      else 'merge_requests',
        'state': data['state'] not in ('opened', 'reopened'),
        'assignee_id': data['assignee_id']
    }
    try:
        picked['project_id'] = data['source_project_id']
    except KeyError:
        picked['project_id'] = data['project_id']
    return picked


q = Queue(
    connection=rq,
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
            if json['object_attributes']['action'] in ('close', 'reopen'):
                q.enqueue(worker.payload_gitlab_state_change, data)
            else:
                q.enqueue(worker.payload_gitlab_generic_event, data)
    return __name__
