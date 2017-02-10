#!/usr/bin/env python
from __future__ import print_function, unicode_literals
from flask_script import Manager, Shell, Server
from rq import Worker, Queue, Connection
from trelolo import create_app
from trelolo.rq_connect import rq_connect
from trelolo.tasks.trello import foo


def _make_context():
    ctx = {
        'app': app
    }
    return ctx


app = create_app()

manager = Manager(app)
manager.add_command('shell', Shell(make_context=_make_context))
manager.add_command('runserver', Server(host=app.config['FLASK_HOST']))


with app.app_context():
    q = Queue(
        connection=rq_connect,
        default_timeout=app.config.get('QUEUE_TIMEOUT')
    )


@manager.command
def work():
    with Connection(rq_connect):
        worker = Worker(map(Queue, ['high', 'default', 'low']))
        worker.work()


if __name__ == "__main__":
    manager.run()
