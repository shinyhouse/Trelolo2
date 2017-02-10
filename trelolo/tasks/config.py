from trello import TrelloClient, ResourceUnavailable

from ..config import Config


client = TrelloClient(
    api_key=Config.TRELOLO_API_KEY,
    token=Config.TRELOLO_TOKEN
)
