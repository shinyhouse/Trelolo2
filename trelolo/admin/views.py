from functools import wraps
from flask import (
    Blueprint, current_app, jsonify, render_template, request, Response
)
from rq import Queue

from ..config import Config
from ..rq_connect import rq_connect
from trelolo import worker


q = Queue(
    connection=rq_connect,
    default_timeout=Config.QUEUE_TIMEOUT
)


def check_auth(username, password):
    return username == current_app.config.get('ADMIN_USER') and \
        password == current_app.config.get('ADMIN_PASSWORD')


def authenticate():
    return Response('Could not verify your access level for that URL.\n'
                    'You have to login with proper credentials', 401,
                    {'WWW-Authenticate': 'Basic realm="Login Required"'})


def requires_auth(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.authorization
        if not auth or not check_auth(auth.username, auth.password):
            return authenticate()
        return f(*args, **kwargs)
    return decorated


bp = Blueprint('admin_page', __name__,
               template_folder='templates')


@bp.route('/config/job/<id>', methods=['GET', 'POST'])
def show_job_state(id):
    state = True
    if id:
        job = q.fetch_job(id)
        if job:
            state = q.fetch_job(id).is_finished
    return jsonify(state=state)


@bp.route('/config', methods=['GET', 'POST'])
@requires_auth
def show_config():
    return __name__
