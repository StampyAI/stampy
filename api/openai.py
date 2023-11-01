import asyncio
from api.utilities.openai import OpenAIEngines
from config import (
    openai_api_key,
    gpt4,
    gpt4_for_all,
    gpt4_whitelist_role_ids,
    bot_vip_ids,
    paid_service_all_channels,
    use_helicone,
    disable_prompt_moderation,
    openai_allowed_sources,
)
from structlog import get_logger
from utilities.serviceutils import ServiceMessage
from utilities import Utilities, discordutils
if use_helicone:
    try:
        from helicone import openai
    except ImportError:
        from helicone import openai_proxy as openai
else:
    import openai
    from openai import Moderation
import discord
import requests
import json # moderation response dump


OPENAI_NASTY_CATEGORIES = {
    "sexual", "hate", "harassment", "self-harm", "sexual/minors", "hate/threatening",
    "violence/graphic", "self-harm/intent", "self-harm/instructions",
    "harassment/threatening", "violence"
}

openai.api_key = openai_api_key
start_sequence = "\nA:"
restart_sequence = "\n\nQ: "
utils = Utilities.get_instance()


class OpenAI:
    def __init__(self):
        self.class_name = self.__class__.__name__
        self.log = get_logger()

    def is_channel_allowed(self, message: ServiceMessage) -> bool:
        channel_id = (message.channel and message.channel.id)
        return (
            paid_service_all_channels or
            channel_id in openai_allowed_sources.get(message.service.value, [])
        )

    def log_error(self, error, exception=None, warning=False):
        if warning:
            self.log.warning(self.class_name, error=error)
        else:
            self.log.error(self.class_name, error=error)

        loop = asyncio.get_running_loop()
        loop.create_task(utils.log_error(error))
        if exception:
            loop.create_task(utils.log_exception(exception))

    def is_text_risky(self, text: str) -> bool:
        """Ask the openai moderation endpoint if the text is risky.

        See https://platform.openai.com/docs/guides/moderation/quickstart for details.
        """
        allowed_categories = {"violence"} # Can be triggered by some AI safety terms

        if disable_prompt_moderation:
            return False

        response = None
        if use_helicone:
            try:
                http_response = requests.post(
                    'https://api.openai.com/v1/moderations',
                    headers={
                        "Content-Type": "application/json",
                        "Authorization": f"Bearer {openai_api_key}"
                    },
                    json={"input": text}
                )
            except Exception as e:
                self.log_error("Error in Requests module trying to moderate content", e)
                return True

            if http_response.status_code == 401:
                self.log_error("OpenAI Authentication Failed")
                return True
            elif http_response.status_code == 429:
                self.log_error("OpenAI Rate Limit Exceeded", warning=True)
                return True
            elif http_response.status_code != 200:
                self.log_error(
                    f"Possible issue with the OpenAI API. Status: {http_response.status_code}, Content: {http_response.text}"
                )
                return True
            response = http_response.json()

        else:
            try:
                response = Moderation.create(input=text)
            except openai.error.AuthenticationError as e:
                self.log_error("OpenAI Authentication Failed", e)
                return True
            except openai.error.RateLimitError as e:
                self.log_error(self.class_name, "OpenAI Rate Limit Exceeded", e, warning=True)
                return True

        results = response.get("results", [])[0]
        if not results:
            return False

        if not results["flagged"]:
            self.log.info(self.class_name, msg=f"Checked with content filter, it says the text looks clean")
            return False

        violated_categories = [
            moral for moral in OPENAI_NASTY_CATEGORIES - allowed_categories if results.get(moral)
        ]
        if violated_categories:
            self.log.warning(self.class_name, msg=f"Text violated these unwanted categories: {violated_categories}")
            self.log.debug(self.class_name, msg=f"OpenAI moderation response: {json.dumps(response)}")
            return True

        self.log.info(self.class_name, msg="Checked with content filter, it doesn't violate any of our categories")
        return False

    def get_engine(self, message: ServiceMessage) -> OpenAIEngines:
        """Pick the appropriate engine to respond to a message with"""

        if gpt4:
            if gpt4_for_all or message.author.id in bot_vip_ids or \
                    any(discordutils.user_has_role(message.author, x)
                        for x in gpt4_whitelist_role_ids):
                return OpenAIEngines.GPT_4
        else:
            return OpenAIEngines.GPT_3_5_TURBO

    def get_response(self, engine: OpenAIEngines, prompt: str, logit_bias: dict[int, int]) -> str:
        if self.is_text_risky(prompt):
            self.log.info(self.class_name, msg="The content filter thought the prompt was risky")
            return ""

        try:
            response = openai.ChatCompletion.create(
                model=str(engine),
                messages=[{'role': 'user', 'content': prompt}],
                temperature=0,
                max_tokens=100,
                top_p=1,
                # stop=["\n"],
                logit_bias=logit_bias,
                # user=str(message.author.id),
            )
        except openai.error.AuthenticationError as e:
            self.log.error(self.class_name, error="OpenAI Authentication Failed")
            loop = asyncio.get_running_loop()
            loop.create_task(utils.log_error(f"OpenAI Authenication Failed"))
            loop.create_task(utils.log_exception(e))
            return ""
        except openai.error.RateLimitError as e:
            self.log.warning(self.class_name, error="OpenAI Rate Limit Exceeded")
            loop = asyncio.get_running_loop()
            loop.create_task(utils.log_error(f"OpenAI Rate Limit Exceeded"))
            loop.create_task(utils.log_exception(e))
            return ""

        if response["choices"]:
            choice = response["choices"][0]
            text = choice.get('message', {}).get('content', '').strip()
            if choice["finish_reason"] == "stop" and text != "Unknown":
                text = text.strip(". \n").split("\n")[0]
                self.log.info(self.class_name, gpt_response=text)
                return text

        return ""
