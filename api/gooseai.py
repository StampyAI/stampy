from api.utilities.gooseutils import GooseAIEngines
from config import goose_api_key, goose_engine_fallback_order
from enum import Enum
from structlog import get_logger
import requests


log = get_logger()


class GooseAI:
    """
    Wrapper for GooseAI API
    """

    def __init__(self):
        self.class_name = self.__class__.__name__
        self._url = "https://api.goose.ai/v1"
        self._headers = {"Authorization": "Bearer " + goose_api_key}

    def getEngine(self) -> GooseAIEngines:
        for engine in goose_engine_fallback_order:
            try:
                response = requests.get(f"/engines/{str(engine)}")
            except Exception as e:
                log.error(self.class_name, _msg="Got error checking if {engine.name} is online.", e=e)

    def get(self, url: str) -> requests.Response:
        """
        Calls the API specified with url using HTTP GET.
        url already includes base. I.e. if trying to call https://api.goose.ai/v1/engines/{engine_id}
        just use /engines/{engine_id}
        """
        response = requests.get(f"{self._url}{url}", headers=self._headers)
        return response
