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
    from helicone import openai
else:
    import openai
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
    def cf_risk_level(self, prompt):
        """Ask the openai content filter if the prompt is risky
        Returns:
            0 - The text is safe.
            1 - This text is sensitive.
            2 - This text is unsafe.

        See https://beta.openai.com/docs/engines/content-filter for details"""

        try:
            response = openai.Completion.create(
                engine="content-filter-alpha",
                prompt="<|endoftext|>" + prompt + "\n--\nLabel:",
                temperature=0,
                max_tokens=1,
                top_p=0,
                logprobs=10,
            )
        except openai.error.AuthenticationError as e:
            self.log.error(self.class_name, error="OpenAI Authentication Failed")
            loop = asyncio.get_running_loop()
            loop.create_task(utils.log_error(f"OpenAI Authenication Failed"))
            loop.create_task(utils.log_exception(e))
            return 2
        except openai.error.RateLimitError as e:
            self.log.warning(self.class_name, error="OpenAI Rate Limit Exceeded")
            loop = asyncio.get_running_loop()
            loop.create_task(utils.log_error(f"OpenAI Rate Limit Exceeded"))
            loop.create_task(utils.log_exception(e))
            return 2

        output_label = response["choices"][0]["text"]

        # This is the probability at which we evaluate that a "2" is likely real
        # vs. should be discarded as a false positive
        toxic_threshold = -0.355

        if output_label == "2":
            # If the model returns "2", return its confidence in 2 or other output-labels
            logprobs = response["choices"][0]["logprobs"]["top_logprobs"][0]

            # If the model is not sufficiently confident in "2",
            # choose the most probable of "0" or "1"
            # Guaranteed to have a confidence for 2 since this was the selected token.
            if logprobs["2"] < toxic_threshold:
                logprob_0 = logprobs.get("0", None)
                logprob_1 = logprobs.get("1", None)

                # If both "0" and "1" have probabilities, set the output label
                # to whichever is most probable
                if logprob_0 is not None and logprob_1 is not None:
                    if logprob_0 >= logprob_1:
                        output_label = "0"
                    else:
                        output_label = "1"
                # If only one of them is found, set output label to that one
                elif logprob_0 is not None:
                    output_label = "0"
                elif logprob_1 is not None:
                    output_label = "1"

                # If neither "0" or "1" are available, stick with "2"
                # by leaving output_label unchanged.

        # if the most probable token is none of "0", "1", or "2"
        # this should be set as unsafe
        if output_label not in ["0", "1", "2"]:
            output_label = "2"

        self.log.info(self.class_name, msg=f"Prompt is risk level {output_label}")

        return int(output_label)

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
        if self.cf_risk_level(prompt) > 1:
            self.log.info(self.class_name, msg="OpenAI's GPT-3 content filter thought the prompt was risky")
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
