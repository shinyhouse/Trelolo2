import csv
import io
from functools import wraps
from flask import (
    Blueprint, current_app, flash, jsonify,
    render_template, redirect, request, Response, url_for
)
from rq import Queue

from ..config import Config
from ..extensions import db, rq
from trelolo import models
from trelolo import worker


q = Queue(
    connection=rq,
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


@bp.route('/config/upload', methods=['POST'])
@requires_auth
def upload():
    if request.method == 'POST':
        file = request.files['file']
        try:
            db.session.query(models.Emails).delete()
            stream = io.StringIO(
                file.stream.read().decode("UTF8"), newline=None
            )
            csv_input = csv.reader(stream)
            for row in csv_input:
                email = models.Emails(username=row[0], email=row[1])
                db.session.add(email)
            db.session.commit()
            flash('Emails have been imported')
        except:
            flash('Something went wrong')
        return redirect(url_for('admin_page.show_config'))


@bp.route('/config', methods=['GET', 'POST'])
@requires_auth
def show_config():
    boards = models.Boards.query.all()
    ids = [board.trello_id for board in boards]
    hooks = {board.trello_id: board.hook_id for board in boards}
    if request.method == 'POST':
        job = None
        board_id = request.form.get('board_id')
        checked = request.form.get('checked')
        if board_id:
            if int(checked):
                if board_id not in ids:
                    job = q.enqueue(worker.hook_teamboard, board_id)
            else:
                if board_id in ids:
                    job = q.enqueue(worker.unhook_teamboard, board_id)
        job_id = job.id if job else None
        return jsonify(job_id=job_id)
    return render_template('config.html',
                           inuse=[Config.TRELOLO_TOP_BOARD,
                                  Config.TRELOLO_MAIN_BOARD],
                           checked_boards=ids,
                           stored_board_hooks=hooks,
                           boards=worker.client.list_boards())
