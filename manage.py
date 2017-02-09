#!/usr/bin/env python
from __future__ import print_function, unicode_literals
from flask_script import Manager, Shell, Server
from trelolo import create_app


def _make_context():
    ctx = {
        'app': app
    }
    return ctx


app = create_app()
manager = Manager(app)
manager.add_command('shell', Shell(make_context=_make_context))
manager.add_command('runserver', Server(host='0.0.0.0'))


if __name__ == "__main__":
    manager.run()
