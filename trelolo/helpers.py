import re
from .config import Config


def webhook_url_mainboard():
    return '{}/trello/mainboard'.format(
        Config.CALLBACK_URL
    )


def webhook_url_teamboard():
    return '{}/trello/teamboard'.format(
        Config.CALLBACK_URL
    )


def webhook_url_card(card_id, item_id):
    return '{}/trello/card/{}/{}'.format(
        Config.CALLBACK_URL, card_id, item_id
    )


def parse_gitlab_targets(text):
    try:
        found = re.search('<\n(.+?)\n>', text).group(1)
        return found.split('\n')
    except TypeError:
        return []
