from api.utilities.gooseutils import GooseAIEngines
from config import goose_api_key, goose_engine_fallback_order
from structlog import get_logger
from typing import Any
import json
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

    def get(self, url: str):
        """
        Calls the API specified with url using HTTP GET.
        url already includes base. I.e. if trying to call https://api.goose.ai/v1/engines/{engine_id}
        just use /engines/{engine_id}
        """
        response = requests.get(f"{self._url}{url}", headers=self._headers)
        return json.loads(response.text)

    def post(self, url: str, data: dict[str, Any]):
        """
        Calls the API specified with url using HTTP GET.
        url already includes base. I.e. if trying to call https://api.goose.ai/v1/engines/{engine_id}
        just use /engines/{engine_id}
        """
        response = requests.post(f"{self._url}{url}", headers=self._headers, data=json.dumps(data))
        return json.loads(response.text)

    def get_engine(self) -> GooseAIEngines:
        for engine in goose_engine_fallback_order:
            try:
                response = self.get(f"/engines/{str(engine)}")
                if response["ready"] is True:
                    return engine
            except Exception as e:
                log.error(self.class_name, _msg="Got error checking if {engine.name} is online.", e=e)
        log.critical(self.class_name, error="No engines for GooseAI are online!")

    def completion(
        self,
        engine: str,
        prompt: str,
        temperature: float,
        max_tokens: int,
        top_p: float,
        logit_bias: dict[int, int],
    ):
        data = {
            "prompt": prompt,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "top_p": top_p,
            "stop": ["\n"],
            "logit_bias": logit_bias,
        }
        return self.post(f"/engines/{engine}/completions", data=data)

    def get_response(self, engine: GooseAIEngines, prompt: str, logit_bias: dict[int, int]) -> str:
        response = self.completion(
            engine=str(engine),
            prompt=prompt,
            temperature=0,
            max_tokens=100,
            top_p=1,
            logit_bias=logit_bias,
        )

        if "error" in response:
            error = response["error"]
            log.error(self.class_name, code=error["code"], error=error["message"], info=error["type"])
            return ""

        if response["choices"]:
            choice = response["choices"][0]
            if choice["finish_reason"] == "stop" and choice["text"].strip() != "Unknown":
                text = choice["text"].strip(". \n").split("\n")[0]
                log.info(self.class_name, gpt_response=text)
                return text

        return ""
