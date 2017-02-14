from enum import Enum
import re
from ..config import Config
import requests


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
        pass


def parse_gitlab_targets(desc):
    try:
        return re.search(
            '<\n(.+?)\n>', desc, re.S).group(1).split('\n')
    except (AttributeError, TypeError):
        return []


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


def parse_gitlab_target_description(desc):
    parts = desc.split('### Trello Cards:')
    gitlab = parts[0].strip('\r\n\r\n')
    try:
        return (gitlab, parts[1].split('\r\n'))
    except (IndexError, TypeError):
        return (gitlab, [])


def update_gitlab_description(project_id, target_url, issue_id, desc):
    data = {
        'description': '\r\n\r\n{}\r\n\r\n'.format(
            '### Trello Cards:'
        ).join([desc[0], "\r\n".join(desc[1])])
    }
    url = "{}/api/v3/projects/{}/{}/{}?access_token={}".format(
        Config.GITLAB_URL,
        project_id,
        target_url,
        issue_id,
        Config.GITLAB_TOKEN
    )
    r = requests.put(url, data)
    return [r.json(), url, data]


def fetch_gitlab_target_description(project_id, target_url, id):
    url = "{}/api/v3/projects/{}/{}/{}?access_token={}"
    url = url.format(
        Config.GITLAB_URL,
        project_id,
        target_url,
        id,
        Config.GITLAB_TOKEN
    )
    r = requests.get(url)
    print(url)
    try:
        data = r.json()
        return parse_gitlab_target_description(
            data['description']
        )
    except KeyError:
        pass


def fetch_gitlab_target(target, target_url, tag):
    try:
        match = re.search(
            '\$' + tag + ':(\d+):(\d+)', target
        ).group(1, 2)
        url = "{}/api/v3/projects/{}?access_token={}"
        url = url.format(
            Config.GITLAB_URL,
            match[0],
            Config.GITLAB_TOKEN
        )
        r = requests.get(url)
        try:
            data = r.json()
            project_name = data['name_with_namespace'] \
                if data['name_with_namespace'] else data['name']
            url = "{}/api/v3/projects/{}/{}/{}?access_token={}"
            url = url.format(
                Config.GITLAB_URL,
                match[0], target_url, match[1],
                Config.GITLAB_TOKEN
            )
            r = requests.get(url)
            try:
                data = r.json()
                description = parse_gitlab_target_description(
                    data['description']
                )
                return {
                    'project_id': data['project_id'],
                    'id': data['id'],
                    'url': data['web_url'],
                    'title': '[{} / {}]({})'.format(
                        project_name, data['title'], data['web_url']
                    ),
                    'opened': data['state'] == 'opened',
                    'description': description
                }
            except KeyError:
                return {}
        except KeyError:
            return {}
    except (AttributeError, TypeError):
        pass
