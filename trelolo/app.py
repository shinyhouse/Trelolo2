from flask import Flask
import logging
from .config import Config
from .admin import views
from .extensions import db, migrate, sentry
from .payloads import gitlab, trello


BLUEPRINTS = (gitlab, trello, views)

app = Flask(__name__)
__all__ = ['create_app']


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    register_blueprints(app)
    db.init_app(app)
    migrate.init_app(app, db)
    sentry.init_app(app, logging=True, level=logging.ERROR)
    return app


def register_blueprints(app):
    for blueprint in BLUEPRINTS:
        app.register_blueprint(blueprint.bp)
