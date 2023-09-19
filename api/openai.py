import asyncio
from api.utilities.openai import OpenAIEngines
from config import (
    openai_api_key,
    paid_service_channel_ids,
    gpt4,
    gpt4_for_all,
    gpt4_whitelist_role_ids,
    bot_vip_ids,
    paid_service_all_channels,
    use_helicone
)
from structlog import get_logger
from servicemodules.serviceConstants import Services, openai_channel_ids
from utilities.serviceutils import ServiceMessage
from utilities import utilities, Utilities
from utilities import discordutils
if use_helicone:
    from openai import Moderation
    try:
        from helicone import openai
    except ImportError:
        from helicone import openai_proxy as openai
else:
    import openai
    from openai import Moderation
import discord

openai.api_key = openai_api_key
start_sequence = "\nA:"
restart_sequence = "\n\nQ: "
utils = Utilities.get_instance()


class OpenAI:
    def __init__(self):
        self.class_name = self.__class__.__name__
        self.log = get_logger()

    def is_channel_allowed(self, message: ServiceMessage) -> bool:
        if message.service in openai_channel_ids and message.channel.id in openai_channel_ids[message.service]:
            # For Rob's discord
            return True
        elif paid_service_all_channels:
            return True
        elif message.channel.id in paid_service_channel_ids:
            # if list is empty, default
            return True
        else:
            return False
    def is_text_risky(self, text: str) -> bool:
        """Ask the openai moderation endpoint if the text is risky
        Returns:
            0 - The text is safe.
            2 - This text is unsafe.

        See https://platform.openai.com/docs/guides/moderation/quickstart for details"""

        try:
            response = Moderation.create(input=text)
        except openai.error.AuthenticationError as e:
            self.log.error(self.class_name, error="OpenAI Authentication Failed")
            loop = asyncio.get_running_loop()
            loop.create_task(utils.log_error(f"OpenAI Authenication Failed"))
            loop.create_task(utils.log_exception(e))
            return True
        except openai.error.RateLimitError as e:
            self.log.warning(self.class_name, error="OpenAI Rate Limit Exceeded")
            loop = asyncio.get_running_loop()
            loop.create_task(utils.log_error(f"OpenAI Rate Limit Exceeded"))
            loop.create_task(utils.log_exception(e))
            return True

        flagged: bool = response["results"][0]["flagged"]

        all_morals: frozenset[str] = ["sexual", "hate", "harassment", "self-harm", "sexual/minors", "hate/threatening", "violence/graphic", "self-harm/intent", "self-harm/instructions", "harassment/threatening", "violence"]
        allowed_categories = frozenset()
        violated_categories = set()

        if flagged:
            for moral in all_morals - allowed_categories:
                if response["results"][0][moral]:
                    violated_categories.add(moral)

        if len(violated_categories) > 0:
            self.log.warning(self.class_name, msg=f"Prompt violated these categories: {violated_categories}")
            return True
        else:
            self.log.info(self.class_name, msg=f"Prompt looks clean")
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
            response = openai.Completion.create(
                engine=str(engine),
                prompt=prompt,
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
            if choice["finish_reason"] == "stop" and choice["text"].strip() != "Unknown":
                text = choice["text"].strip(". \n").split("\n")[0]
                self.log.info(self.class_name, gpt_response=text)
                return text

        return ""
