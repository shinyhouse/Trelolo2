from collections import OrderedDict
from enum import Enum
import logging
from trello import TrelloClient, ResourceUnavailable
from ..models import Boards, Cards, Issues


logger = logging.getLogger(__name__)


class Trelolo(TrelloClient):

    def setup_gitlab(self, gitlab_url, gitlab_token):
        pass

    def setup_trelolo(self, mainboard_id, topboard_id, webhook_url):
        self.webhook_url = webhook_url
        self.boards = OrderedDict({
            mainboard_id: self.get_board_data(mainboard_id, {
                'prefix': '#',
                'remove': True
            }),
            topboard_id: self.get_board_data(topboard_id, {
                'prefix': 'OKR:',
                'remove': True
            })
        })
        if not self.does_webhook_exist(mainboard_id):
            self.create_hook(
                '{}/trello/mainboard'.format(self.webhook_url),
                mainboard_id,
                'mainboard: {}'.format(mainboard_id),
                token=self.resource_owner_key
            )

    def get_board_data(self, board_id, metadata):
        try:
            board = self.get_board(board_id)
            lists = board.open_lists() if board is not None else []
            inbox = next(
                (l for l in lists if l.name.lower() == 'inbox'),
                None
            )
            return {
                'board': board,
                'lists': lists,
                'inbox': inbox,
                'metadata': metadata
            }
        except ResourceUnavailable:
            logger.error('invalid board {}'.format(board_id))
            return False

    def does_webhook_exist(self, model_id):
        return any(
            i for i in self.list_hooks(self.resource_owner_key)
            if i.id_model == model_id
        )
