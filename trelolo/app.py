from flask import Flask
from trelolo.admin.views import admin_page
from .config import Config

app = Flask(__name__)
__all__ = ['create_app']


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.register_blueprint(admin_page)
    return app
