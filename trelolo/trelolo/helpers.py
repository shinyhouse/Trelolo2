import logging
import json
import re
import requests

from collections import OrderedDict
from enum import Enum
from urllib.parse import urlencode

from trello import Unauthorized, ResourceUnavailable

from trelolo.extensions import db
from trelolo import models
from ..config import Config


logger = logging.getLogger(__name__)


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


def get_gitlab_target(target, tag=TargetTag.ISSUE):
    try:
        return re.search(
            '\$' + tag + ':(.+?)\/(.+?):(\d+)', target
        ).group(1, 2, 3)
    except (AttributeError, TypeError):
        return None


def urls_into_description(separator, description, urls):
    new_urls = []
    for url in urls:
        new_urls.append("* {}\r\n".format(url))
    parts = description.split(separator)
    orig_desc = parts[0].strip("\r\n\r\n")
    if len(new_urls) == 0:
        return orig_desc
    return "\r\n\r\n{}\r\n\r\n" \
        .format(separator).join([orig_desc,
                                "".join(new_urls)])


def format_item_name(name_space, title, url):
    if name_space is None:
        return "[{}]({})".format(title, url)
    else:
        return "[{} / {}]({})".format(name_space, title, url)


def is_mainboard_label(label):
    return label.startswith('#')


def is_topboard_label(label):
    return label.startswith('OKR:')


def is_todo_column(name):
    name = parse_listname(name)
    return any(possible_tag in name.upper()
               for possible_tag in ["TODO", "TO-DO", "TO_DO", "@TODO"])


def get_checklist_item(cl, issue_id):
    for item in cl.items:
        if item['id'] == issue_id:
            return item

    return None


def find_card(board_data, card_name):
    for card in board_data['board'].open_cards():
        if card.name == card_name:
            return card

    return None


def move_card(board_data, card, list_num):
    try:
        column = board_data['cols'][list_num]
        card.change_list(column.id)
    except (Unauthorized, ResourceUnavailable) as e:
        logger.error(e)

    return card


def update_label(board_data, data):
    card = find_card(board_data, data['old_label'])
    if card:
        card.set_name(data['new_label'])
        models.Cards.query.filter_by(label=data['old_label']).update({models.Cards.label: data['new_label']})
        logger.info("Changed {} label to {}".format(data['old_label'],
                                                    data['new_label']))
    return


def get_list_num(source, items):
    checked = sum([not source.is_todo_column(cl_item['name']) or
                   cl_item['checked'] for cl_item in items])
    return int(checked > 0)


def add_attachment_to_card(board_data, data):
    try:
        card = find_card(board_data, data['label'])

        attachment = data['response']['action']['data']['attachment']
        card.attach(name=attachment['name'],
                    url=attachment['url'])

        return True
    except Exception as e:
        logger.error("could not add attachment: {}"
                     .format(e))
        return False


def check_labels(labels, gl_label):
    for label in labels:
        try:
            n = label.name[1:]
            if label.name[0] == '$' and n == gl_label:
                return True
        except IndexError:
            pass

    return False


def find_label(labels, label_name):
    for label in labels:
        if label.name == label_name:
            return label

    return None


def load_gitlab_data(model_id, target_type):
    pg_data = models.Issues.query.filter(issue_id=model_id)\
        .filter(target_type=target_type)

    try:
        data = {}
        for card_data in pg_data:
            data[card_data.parent_card_id] = card_data

        return data
    except:
        return {}


def save_gitlab_data(model_id, data):
    for parent_card_id in data:
        db.session.update(data[parent_card_id])
    db.session.commit()


def allow_card_action(response):
    try:
        if response['object_kind'] == 'issue':
            action = response['object_attributes']['action']
            return action in ['open',
                              'close',
                              'reopen',
                              'update']
        return False
    except KeyError:
        return False


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


class GitLabMixin(object):
    API_URL = "{}/api/v3/projects/{}/issues/{}?access_token={}"
    ISSUE_FILTER_URL = "{}/api/v3/issues?labels={}&state=opened&access_token={}"
    USER_URL = "{}/api/v3/users/{}?access_token={}"
    MILESTONE_URL = "{}/api/v3/projects/{}/milestones/{}?access_token={}"
    SEPARATOR = "### Trello Cards:"
    TARGET_TYPE = "issue"

    gitlab_url = None
    gitlab_token = None

    def _get_url(self, api, params=None):
        params = params or {}
        params['access_token'] = self.gitlab_token

        return "{}/api/v3{}?{}".format(self.gitlab_url, api, urlencode(params))

    def create_label(self, project_id, name):
        logger.info("creating GitLab label {} in project {}"
                 .format(name,
                         project_id))

        url = self._get_url("projects/{}/labels".format(project_id))
        label_data = {
            'name': name,
            'color': '#5843AD'
        }

        r = requests.post(url, label_data)
        logger.debug("create label: {}"
                  .format(json.dumps(r, indent=4)))

    def get_label(self, project_id, issue_id):
        url = self.API_URL.format(self.gitlab_url, project_id, issue_id, self.gitlab_token)
        r = requests.get(url)

        logger.info(""" gitlab url: {} """.format(url))

        try:
            labels = r.json()['labels']
        except KeyError:
            return False

        try:
            project_labels = [l for l in labels if l[0] == '$']
            return project_labels[0][1:]
        except IndexError:
            return False

    def get_milestone(self, project_id, milestone_id):
        if not milestone_id:
            return False

        url = self.MILESTONE_URL.format(self.gitlab_url,
                                        project_id,
                                        milestone_id,
                                        self.gitlab_token)
        r = requests.get(url)

        try:
            milestone = r.json()['title'][1:]
            return milestone
        except (KeyError, IndexError):
            return False

    def get_members(self, issue):
        """
        Gets the members for the specified issue
        (either as assigned, or mentioned user)

        :param issue: issue to process
        :return: a list of emails
        """

        # get assignee email
        url = self.API_URL.format(self.gitlab_url, issue['project_id'],
                                  issue['id'], self.gitlab_token)
        r = requests.get(url)

        try:
            assignee = r.json()['assignee']
        except KeyError:
            return False

        members = []
        if assignee is not None:
            members.append(self.get_member_email(assignee['id']))

        # get mentioned users' emails
        members.extend(self.get_members_from_desc(issue))

        logger.info("""members: {}""".format(members))

        return members

    def get_members_from_desc(self, issue):
        """
        Parses the description for user mentions and retrieves their emails

        :param issue: issue with description to parse
        :return: a list of emails
        """

        users = {}

        mentions = parse_mentions(issue['description'])
        gitlab_members = []
        for username in mentions:
            try:
                gitlab_members.append(users[username])
            except KeyError:
                email = self.get_member_email(username, True)
                if email is not None:
                    users[username] = email
                    gitlab_members.append(email)

        return gitlab_members

    def get_member_email(self, user_id, username=False):
        """
        Retrieves the email for the specified user.

        :param user_id: ID or username of the user
        :param username True to look for user by username
        :return: email of the user
        """

        url = self._get_url("users", {'username': user_id}) if username\
            else self._get_url("users{}".format(user_id))
        r = requests.get(url)
        try:
            return r.json()['email']
        except:
            return None

    def get_project_name(self, project_id):
        url = self._get_url("projects/{}".format(project_id))
        r = requests.get(url)

        try:
            return r.json()['name_with_namespace']
        except:
            return None

    def normalize_card_response(self, response):
        if allow_card_action(response):
            issue = response['object_attributes']
            label = self.get_label(issue['project_id'], issue['id'])
            milestone = self.get_milestone(issue['project_id'],
                                           issue['milestone_id'])
            members = self.get_members(issue)
            storage = load_gitlab_data(issue['id'], self.TARGET_TYPE)
            name_with_namespace = self.get_project_name(issue['project_id'])

            ret = {
                'id': issue['id'],
                'project_id': issue['project_id'],
                'label': label,
                'milestone': milestone,
                'description': issue['description'],
                'name': format_item_name(name_with_namespace, issue['title'], issue['url']),
                'checked': issue['state'] == 'closed',
                'storage': storage,
                'can_create': True,
                'members': members,
                'target_type': self.TARGET_TYPE
            }
            return ret
        return False

    def update_gitlab_description(self, project_id, issue_id, description):
        data = {
            'description': description
        }
        requests.put(self.API_URL.format(self.gitlab_url, project_id,
                                         issue_id, self.gitlab_token), data)


class CardDescription(object):

    INIT_DESCRIPTION = '----\n' \
                       'owner:\n' \
                       'group email:\n' \
                       'slack channel:\n' \
                       'members:\n' \
                       'delivery time:'

    def __init__(self, desc=None):
        self.desc = desc
        self.desc_text = ''
        self.data = OrderedDict()

        self._parse()

        logger.debug("CardDescription({})"
                     .format(desc))

    def _parse(self):
        x = self.desc.split('----\n')

        try:
            self.desc_text = x[0].strip()

            desc_lines = x[1].split('\n')
            for line in desc_lines:
                kv = line.split(':')
                self.data[kv[0]] = kv[1]
        except IndexError:
            pass

    def get_value(self, key, default=None):
        try:
            return self.data[key]
        except KeyError:
            return default

    def set_value(self, key, value):
        self.data[key] = value

    def set_list_value(self, key, values):
        v = self.get_value(key, '').strip()
        l = v.split(',') \
            if v != '' else []

        l.extend([i for i in values
                  if i not in l])

        self.data[key] = ','.join(l)

    def set_description_text(self, desc_text):
        self.desc_text = desc_text

    def get_description(self):
        d = '{}\n\n'.format(self.desc_text) \
            if self.desc_text != '' else ''

        d += '----\n{}'\
            .format('\n'.join(['{}: {}'.format(key, value)
                               for (key, value) in self.data.items()]))

        return d
