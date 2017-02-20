#!/usr/bin/env python
from __future__ import print_function, unicode_literals
from flask_migrate import Migrate, MigrateCommand
from flask_script import Manager, Shell, Server
from rq import Worker, Queue, Connection
from trelolo import create_app
from trelolo.extensions import db, rq
from trelolo.worker import unhook_all


def _make_context():
    ctx = {
        'app': app
    }
    return ctx


app = create_app()
migrate = Migrate(app, db)

manager = Manager(app)
manager.add_command('shell', Shell(make_context=_make_context))
manager.add_command('runserver', Server(host=app.config['FLASK_HOST']))
manager.add_command('db', MigrateCommand)


with app.app_context():
    q = Queue(
        connection=rq,
        default_timeout=app.config.get('QUEUE_TIMEOUT')
    )


@manager.command
def unhookall():
    q.enqueue(unhook_all)


@manager.command
def work():
    with Connection(rq):
        worker = Worker(map(Queue, ['high', 'default', 'low']))
        worker.work()


if __name__ == "__main__":
    manager.run()
