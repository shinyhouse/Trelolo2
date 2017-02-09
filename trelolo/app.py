from .config import Config
from flask import Flask
from rainbow_logging_handler import RainbowLoggingHandler
import sys
from trelolo.admin.views import admin_page


app = Flask(__name__)
__all__ = ['create_app']


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    app.register_blueprint(admin_page)
    configure_logging(app)
    return app


def configure_logging(app):
    handler = RainbowLoggingHandler(sys.stderr)
    app.logger.addHandler(handler)
