from __future__ import absolute_import

from huey import RedisHuey
from redis.connection import ConnectionPool

from ..app import create_app

trelolo_app = create_app()

with trelolo_app.app_context():
    huey = RedisHuey(
        connection_pool=ConnectionPool.from_url(trelolo_app.config['REDIS'])
    )
