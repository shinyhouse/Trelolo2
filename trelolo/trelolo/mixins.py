from enum import Enum
import logging
import requests

log = logging.getLogger(__name__)


class TargetTag(Enum):
    ISSUE = 'GLIS'
    MR = 'GLMR'


class GitLabMixin(object):

    gitlab_url = None
    gitlab_token = None

    def urls_into_desc(self, separator, description, urls):
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

    def parse_gl_target_desc(self, desc):
        parts = desc.split('### Trello Cards:')
        gitlab = parts[0].strip('\r\n\r\n')
        try:
            return (gitlab, parts[1].split('\r\n'))
        except (IndexError, TypeError):
            return [gitlab, []]

    def format_gl_desc(self, desc):
        return '\r\n\r\n{}\r\n\r\n'.format(
            '### Trello Cards:'
        ).join([desc[0], "\r\n".join([v for v in desc[1] if v])])

    def update_gl_desc(self, project_id, target_url, id, desc):
        data = {
            'description': self.format_gl_desc(desc)
        }
        url = "{}/api/v3/projects/{}/{}/{}?access_token={}".format(
            self.gitlab_url,
            project_id,
            target_url,
            id,
            self.gitlab_token
        )
        r = requests.put(url, data)
        return [r.json(), url, data]

    def fetch_gl_target_desc(self, project_id, target_url, id):
        url = "{}/api/v3/projects/{}/{}/{}?access_token={}".format(
            self.gitlab_url,
            project_id,
            target_url,
            id,
            self.gitlab_token
        )
        r = requests.get(url)
        try:
            data = r.json()
            return self.parse_gl_target_desc(
                data['description']
            )
        except KeyError:
            pass

    def create_gl_label(self, project_id, name):
        url = '{}/api/v3/projects/{}/labels?access_token={}'.format(
            self.gitlab_url, project_id, self.gitlab_token
        )
        try:
            requests.post(url, {
                'name': name,
                'color': '#5843AD'
            })
        except Exception as e:
            log.warning(
                'error creating gitlab label {}: {}'.format(name, str(e))
            )

    def add_gl_label(self, project_id, id, target_url, name):
        url = '{}/api/v3/projects/{}/{}/{}?access_token={}'.format(
            self.gitlab_url, project_id, target_url, id, self.gitlab_token
        )
        try:
            r = requests.get(url)
            labels = r.json()['labels']
            if name not in labels:
                labels.append(name)
            r = requests.put(url, {
                'labels': ','.join(labels)
            })
            log.info(
                'setting labels for target {}: {}'.format(id, labels)
            )
        except Exception as e:
            log.warning(
                'error adding gitlab label {} to {}: {}'.format(
                    name, id, str(e)
                )
            )

    def remove_gl_label(self, project_id, id, target_url, name):
        url = '{}/api/v3/projects/{}/{}/{}?access_token={}'.format(
            self.gitlab_url, project_id, target_url, id, self.gitlab_token
        )
        try:
            r = requests.get(url)
            labels = r.json()['labels']
            if name in labels:
                labels.remove(name)
            r = requests.put(url, {
                'labels': ','.join(labels)
            })
            log.info(
                'removing labels from target {}: {}'.format(id, labels)
            )
        except Exception as e:
            log.warning(
                'error removing label from {}: {}'.format(id, str(e))
            )

    def fetch_gl_labels(self, project_id, target_url, id):
        url = '{}/api/v3/projects/{}/{}/{}?access_token={}'.format(
            self.gitlab_url, project_id, target_url, id, self.gitlab_token
        )
        r = requests.get(url)
        try:
            labels = [l for l in r.json()['labels'] if l[0] == '$']
            return labels[0][1:]
        except Exception as e:
            log.warning(
                'error fetching labels from {}({}): {}'.format(
                    target_url, id, str(e)
                )
            )

    def fetch_gl_milestone(self, project_id, milestone_id):
        url = '{}/api/v3/projects/{}/milestones/{}?access_token={}'.format(
            self.gitlab_url, project_id, milestone_id, self.gitlab_token
        )
        r = requests.get(url)
        try:
            milestone = r.json()['title']
            return milestone[1:] if milestone[0] == '$' else False
        except Exception as e:
            log.warning(
                'error fetching gl milestone {} for project {}: {}'.format(
                    milestone_id, project_id, str(e)
                )
            )

    def fetch_gl_project_name(self, project_id):
        url = '{}/api/v3/projects/{}?access_token={}'.format(
            self.gitlab_url, project_id, self.gitlab_token
        )
        r = requests.get(url)
        try:
            data = r.json()
            project_name = data['name_with_namespace'] \
                if data['name_with_namespace'] else data['name']
            return project_name
        except Exception as e:
            log.warning(
                'error fetching gl project {}: {}'.format(project_id, str(e))
            )

    def fetch_gl_assignee_email(self, assignee_id):
        url = '{}/api/v3/users/{}/?access_token={}'.format(
            self.gitlab_url, assignee_id, self.gitlab_token
        )
        r = requests.get(url)
        try:
            return r.json()['email']
        except Exception as e:
            log.warning(
                'error fetching email from assignee {}'.format(
                    assignee_id, str(e)
                )
            )
