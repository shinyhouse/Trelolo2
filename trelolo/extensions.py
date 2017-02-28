from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
import redis
from redis.connection import ConnectionPool
from raven.contrib.flask import Sentry

from .config import Config


db = SQLAlchemy()
migrate = Migrate()
sentry = Sentry()

rq = redis.Redis(
    connection_pool=ConnectionPool.from_url(Config.REDIS)
)
