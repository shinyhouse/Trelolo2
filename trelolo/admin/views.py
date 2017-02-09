from functools import wraps
from flask import abort, Blueprint, render_template, request, Response
from jinja2 import TemplateNotFound


def check_auth(username, password):
    return username == '' and \
        password == ''


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


admin_page = Blueprint('admin_page', __name__,
                       template_folder='templates')


@admin_page.route('/', defaults={'page': 'index'})
@admin_page.route('/<page>')
@requires_auth
def show(page):
    try:
        return render_template('config.html')
    except TemplateNotFound:
        abort(404)
