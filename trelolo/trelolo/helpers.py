import logging
import re
from collections import OrderedDict


logger = logging.getLogger(__name__)


def format_itemname(completeness, url, listname):
    if completeness >= 0:
        return "{:0.0f}% {} (#{})".format(
            completeness, url, listname
        )
    else:
        return "{} (#{})".format(url, listname)


def format_teamboard_card_descritpion(old_desc, new_desc):
    init_desc = "Main Board: {}\n\n-----\n{}"
    parts = old_desc.split("-----\n")
    if parts[0].startswith('Main Board: '):
        desc = init_desc.format(new_desc, parts[1]) \
         if new_desc else parts[1]
    else:
        desc = init_desc.format(new_desc, old_desc) \
         if new_desc else old_desc
    return desc


def parse_mentions(desc):
    return re.findall("@([.\w-]+)", desc)


def parse_listname(lst_name):
    try:
        return re.search(
            '\(\#([^]]+)\)', lst_name).group(1)
    except TypeError:
        pass


class CardDescription(object):

    INIT_DESCRIPTION = '----\n' \
                       'owner:\n' \
                       'members:\n' \
                       'delivery time:'

    def __init__(self, desc=None):
        self.desc = desc
        self.desc_text = ''
        self.data = OrderedDict()
        self._parse()
        logger.debug(
            'CardDescription({})'.format(desc)
        )

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
        val = self.get_value(key, '').strip()
        l = val.split(',') if val != '' else []
        l.extend([i for i in values if i not in l])
        self.data[key] = ','.join(l)

    def set_description_text(self, desc_text):
        self.desc_text = desc_text

    def get_description(self):
        desc = '{}\n\n'.format(self.desc_text) \
            if self.desc_text != '' else ''
        desc += '----\n{}' \
            .format(
                '\n'.join(
                    ['{}: {}'.format(key, value)
                     for (key, value) in self.data.items()]
                 )
             )
        return desc
