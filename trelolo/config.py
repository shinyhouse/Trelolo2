from os import environ as env


class Config(object):
    SECRET_KEY = env.get('SECRET_KEY')
    CALLBACK_URL = env.get('CALLBACK_URL')
    TRELOLO_API_KEY = env.get('TRELOLO_API_KEY')
    TRELOLO_TOKEN = env.get('TRELOLO_TOKEN')
    TRELOLO_MAIN_BOARD = env.get('TRELOLO_MAIN_BOARD')
    TRELOLO_TOP_BOARD = env.get('TRELOLO_TOP_BOARD')
    GITLAB_URL = env.get('GITLAB_URL')
    GITLAB_TOKEN = env.get('GITLAB_TOKEN')
    REDIS = env.get('REDIS', 'redis://redis:6379')
    FLASK_HOST = env.get('FLASK_HOST', '0.0.0.0')
    FLASK_PORT = int(env.get('FLASK_PORT', '5000'))
    ADMIN_USER = env.get('ADMIN_USER', '')
    ADMIN_PASSWORD = env.get('ADMIN_PASSWORD', '')

    # TODO: find a better way (maybe?)
    e = env.get('environment', 'default')
    if e == 'testing':
        pass
