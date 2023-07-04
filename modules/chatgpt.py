"""
Gives user response to ChatGPT
"""

from openai.openai_object import OpenAIObject
import re
from typing import cast, TYPE_CHECKING

from api.openai import OpenAI
from api.utilities.openai import OpenAIEngines
from config import (
    CONFUSED_RESPONSE,
    openai_api_key,
    bot_vip_ids,
    use_helicone,
    llm_prompt,
)
from modules.module import IntegrationTest, Module, Response
from utilities.serviceutils import ServiceChannel, ServiceMessage
from utilities import Utilities, can_use_paid_service
from servicemodules.serviceConstants import service_italics_marks, default_italics_mark

if use_helicone:
    from helicone import openai
else:
    import openai

if TYPE_CHECKING:
    from openai.openai_object import OpenAIObject

openai.api_key = openai_api_key


class ChatGPTModule(Module):
    def __init__(self):
        super().__init__()

        self.message_logs: dict[
            ServiceChannel, list[ServiceMessage]
        ] = {}  # one message log per channel
        self.log_max_messages = 15  # don't store more than X messages back
        self.log_max_chars = 1500  # total log length shouldn't be longer than this
        self.log_message_max_chars = (
            1000  # limit message length to X chars (remove the middle part)
        )
        self.openai = OpenAI() if openai_api_key else None
        if not openai_api_key:
            self.log.info(
                self.class_name,
                warning="No OpenAI API key found in env",
            )

    def process_message(self, message: ServiceMessage) -> Response:
        self.message_log_append(message)

        if message.is_dm:
            if message.author.id not in bot_vip_ids:
                self.log.info(
                    self.class_name,
                    author=message.author.id,
                    author_type=type(message.author.id),
                )
                return Response()

        if not self.is_at_me(message):
            return Response()

        if not can_use_paid_service(message.author):
            self.log.info(self.class_name, warning="cannot use paid service")  # DEBUG
            return Response()

        if Utilities.get_instance().test_mode:
            return Response()

        return Response(
            confidence=3, callback=self.chatgpt_chat, args=[message], kwargs={}
        )

    def process_message_from_stampy(self, message) -> None:
        self.message_log_append(message)

    def message_log_append(self, message) -> None:
        """Store the message in the log"""

        # make sure we have a list in there for this channel
        self.message_logs[message.channel] = self.message_logs.get(message.channel, [])

        self.message_logs[message.channel].append(message)
        self.message_logs[message.channel] = self.message_logs[message.channel][-self.log_max_messages:]  # fmt:skip

    def generate_messages_list(self, channel) -> list[dict[str, str]]:
        messages = []
        chatlog = ""
        for message in self.message_logs[channel][::-1]:
            username = message.author.display_name
            text = message.clean_content

            if len(text) > self.log_message_max_chars:
                text = (
                    text[: self.log_message_max_chars // 2]
                    + " ... "
                    + text[-self.log_message_max_chars // 2 :]
                )
            chatline = f"{username} says: {text}"

            chatlog += chatline
            if len(chatlog) + len(chatline) > self.log_max_chars:
                break

            if Utilities.get_instance().stampy_is_author(message):
                messages.insert(0, {"role": "assistant", "content": text.strip("*")})
            else:
                messages.insert(0, {"role": "user", "content": chatline})

        messages.insert(
            0,
            {
                "role": "system",
                "content": llm_prompt,
            },
        )

        return messages

    async def chatgpt_chat(self, message: ServiceMessage) -> Response:
        """Ask ChatGPT what Stampy would say next in the chat log"""
        if self.openai is None:
            return Response()

        engine: OpenAIEngines = self.openai.get_engine(message)

        messages = self.generate_messages_list(message.channel)
        self.log.info(self.class_name, messages=messages)

        if message.service in service_italics_marks:
            im = service_italics_marks[message.service]
        else:
            im = default_italics_mark

        if self.openai.is_channel_allowed(message):
            self.log.info(
                self.class_name,
                msg=f"sending chat prompt to chatgpt, engine {engine} ({engine.description})",
            )
            chatcompletion = cast(
                OpenAIObject,
                openai.ChatCompletion.create(model=str(engine), messages=messages),
            )
            print(chatcompletion)
            if chatcompletion.choices:
                response = chatcompletion.choices[0].message.content

                # sometimes the response starts with "Stampy says:" or responds or replies etc, which we don't want
                response = re.sub(r"^[sS]tampy\ ?[a-zA-Z]{,15}:\s?", "", response)

                self.log.info(self.class_name, response=response)

                if response:
                    return Response(
                        confidence=10,
                        text=f"{im}{response}{im}",
                        why="ChatGPT made me say it!",
                    )
        else:
            self.log.info(self.class_name, msg="channel not allowed")
        return Response()

    def __str__(self):
        return "ChatGPT Module"

    # TODO: integration tests that make sense
