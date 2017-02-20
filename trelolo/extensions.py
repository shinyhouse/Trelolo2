from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy
import redis
from redis.connection import ConnectionPool

from .config import Config


db = SQLAlchemy()
migrate = Migrate()

rq = redis.Redis(
    connection_pool=ConnectionPool.from_url(Config.REDIS)
)
