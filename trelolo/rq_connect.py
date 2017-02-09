import redis
from redis.connection import ConnectionPool

from .config import Config


rq_connect = redis.Redis(
    connection_pool=ConnectionPool.from_url(Config.REDIS)
)
