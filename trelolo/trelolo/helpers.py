from enum import Enum
import re
from .config import Config


class TargetTag(Enum):
    ISSUE = 'GLIS'
    MR = 'GLMR'


def parse_mentions(desc):
    return re.findall("@([.\w-]+)", desc)


def parse_listname(lst_name):
    try:
        return re.search(
            '\(\#([^]]+)\)', lst_name).group(1)
    except TypeError:
        return None


def parse_gitlab_targets(desc):
    try:
        return re.search(
            '<\n(.+?)\n>', desc).group(1).split('\n')
    except (AttributeError, TypeError):
        return []


def get_gitlab_target(target, tag=TargetTag.ISSUE):
    try:
        return re.search(
            '\$' + tag + ':(.+?)\/(.+?):(\d+)', target
        ).group(1, 2, 3)
    except (AttributeError, TypeError):
        return None


def is_mainboard_label(label):
    return label.startswith('#')


def is_topboard_label(label):
    return label.startswith('OKR:')


def webhook_url_mainboard():
    return '{}/trello/mainboard'.format(
        Config.WEBHOOK_URL
    )


def webhook_url_teamboard():
    return '{}/trello/teamboard'.format(
        Config.WEBHOOK_URL
    )


def webhook_url_card(card_id, item_id):
    return '{}/trello/card/{}/{}'.format(
        Config.WEBHOOK_URL, card_id, item_id
    )
