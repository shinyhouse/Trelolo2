from enum import Enum
import logging
import re
import requests

logger = logging.getLogger(__name__)


class TargetTag(Enum):
    ISSUE = 'GLIS'
    MR = 'GLMR'


class GitLabMixin(object):

    gitlab_url = None
    gitlab_token = None

    def parse_gl_targets(self, desc):
        try:
            return re.search(
                '<\n(.+?)\n>', desc, re.S).group(1).split('\n')
        except (AttributeError, TypeError):
            return []

    def get_gl_target(self, target, tag=TargetTag.ISSUE):
        try:
            return re.search(
                '\$' + tag + ':(.+?)\/(.+?):(\d+)', target
            ).group(1, 2, 3)
        except (AttributeError, TypeError):
            return None

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

    def update_gl_desc(self, project_id, target_url, issue_id, desc):
        data = {
            'description': '\r\n\r\n{}\r\n\r\n'.format(
                '### Trello Cards:'
            ).join([desc[0], "\r\n".join([v for v in desc[1] if v])])
        }
        url = "{}/api/v3/projects/{}/{}/{}?access_token={}".format(
            self.gitlab_url,
            project_id,
            target_url,
            issue_id,
            self.gitlab_token
        )
        r = requests.put(url, data)
        return [r.json(), url, data]

    def fetch_gl_target_desc(self, project_id, target_url, id):
        url = "{}/api/v3/projects/{}/{}/{}?access_token={}"
        url = url.format(
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

    def fetch_gl_target(self, target, target_url, tag):
        try:
            match = re.search(
                '\$' + tag + ':(\d+):(\d+)', target
            ).group(1, 2)
            url = "{}/api/v3/projects/{}?access_token={}"
            url = url.format(
                self.gitlab_url, match[0], self.gitlab_token
            )
            r = requests.get(url)
            try:
                data = r.json()
                project_name = data['name_with_namespace'] \
                    if data['name_with_namespace'] else data['name']
                url = "{}/api/v3/projects/{}/{}/{}?access_token={}"
                url = url.format(
                    self.gitlab_url,
                    match[0], target_url, match[1],
                    self.gitlab_token
                )
                r = requests.get(url)
                try:
                    data = r.json()
                    description = self.parse_gl_target_desc(
                        data['description']
                    )

                    # older versions of gitlab do not include web_url in response
                    try:
                        web_url = data['web_url']
                    except (KeyError, AttributeError):
                        web_url = "{}/projects/{}/{}/{}".format(
                            self.gitlab_url,
                            project_name, target_url, match[1]
                        )

                    logger.info(data)
                    return {
                        'project_id': data['project_id'],
                        'id': data['id'],
                        'url': web_url,
                        'title': '[{} / {}]({})'.format(
                            project_name, data['title'], web_url
                        ),
                        'checked': data['state'] not in ('opened', 'reopened'),
                        'description': description
                    }
                except KeyError:
                    return {}
            except KeyError:
                return {}
        except (AttributeError, TypeError):
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
            logger.error(
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
            logger.info(
                'setting labels for issue {}: {}'.format(id, labels)
            )
        except Exception as e:
            logger.error(
                'error adding gitlab label {} to {}: {}'.format(
                    name, id, str(e)
                )
            )

    def remove_gl_label(self, project_id, id, target_url, name):
        url = '{}/api/v3/projects/{}/{}/{}?access_token={}'.format(
            self.gitlab_url, project_id, target_url, id, self.gitlab_url
        )
        try:
            r = requests.get(url)
            labels = r.json()['labels']
            if name in labels:
                labels.remove(name)
            r = requests.put(url, {
                'labels': ','.join(labels)
            })
            logger.info(
                'removing labels from issue {}: {}'.format(id, labels)
            )
        except Exception as e:
            logger.error(
                'error removing label from {}: {}'.format(id, str(e))
            )
