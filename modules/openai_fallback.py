"""
Fallback to ChatGPTModule: asks OpenAI to continue the chat log as Stampy
"""

from typing import Optional

from api.openai import OpenAI, OpenAIEngines
from config import openai_api_key, bot_vip_ids
from modules.module import Module, Response
from utilities import Utilities, can_use_paid_service
from utilities.serviceutils import ServiceChannel, ServiceMessage
from servicemodules.serviceConstants import service_italics_marks, default_italics_mark


class OpenAIFallbackModule(Module):
    def __init__(self) -> None:
        super().__init__()
        # one message log per channel
        self.message_logs: dict[ServiceChannel, list[ServiceMessage]] = {}
        self.log_max_messages = 10  # don't store more than X messages back
        self.log_max_chars = 1500  # total log length shouldn't be longer than this
        # limit message length to X chars (remove the middle part)
        self.log_message_max_chars = 500

        self.openai = OpenAI() if openai_api_key else None
        if not openai_api_key:
            self.log.info(
                self.class_name,
                warning="No OpenAI API key found in env.",
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
            return Response()

        if Utilities.get_instance().test_mode:
            return Response()

        return Response(
            confidence=2, callback=self.fallback_chat, args=[message], kwargs={}
        )

    def process_message_from_stampy(self, message: ServiceMessage) -> None:
        self.message_log_append(message)

    def message_log_append(self, message: ServiceMessage) -> None:
        """Store the message in the log"""

        # make sure we have a list in there for this channel
        self.message_logs[message.channel] = self.message_logs.get(message.channel, [])

        self.message_logs[message.channel].append(message)
        self.message_logs[message.channel] = self.message_logs[message.channel][-self.log_max_messages :]  # fmt:skip

    def generate_chatlog_prompt(self, channel: ServiceChannel) -> str:
        chatlog_string = self.generate_chatlog(channel)

        prompt = (
            f"Stampy is a helpful, intelligent, and sarcastic AI bot. He loves stamps more than anything, and hates to repeat himself.\n"
            f"This is a particularly good example of a conversation between Stampy and some human users.\n\n"
            f"{chatlog_string}stampy:"
        )

        self.log.info(self.class_name, prompt=prompt)
        return prompt

    def generate_chatlog(self, channel: ServiceChannel) -> str:
        chatlog = ""
        for message in self.message_logs[channel][::-1]:
            username = message.author.name
            text = message.clean_content

            if len(text) > self.log_message_max_chars:
                text = (
                    text[: self.log_message_max_chars // 2]
                    + " ... "
                    + text[-self.log_message_max_chars // 2 :]
                )
            chatline = f"{username}: {text}"

            if len(chatlog) + len(chatline) > self.log_max_chars:
                break

            chatlog = f"{chatline}\n{chatlog}"

        return chatlog

    def get_engine(self, message: ServiceMessage) -> Optional[OpenAIEngines]:
        if self.openai and self.openai.is_channel_allowed(message):
            return self.openai.get_engine(message)

    async def fallback_chat(self, message: ServiceMessage) -> Response:
        """Ask OpenAI what Stampy would say next in the chat log"""
        engine = self.get_engine(message)
        if not engine or not self.openai:
            return Response()

        prompt = self.generate_chatlog_prompt(message.channel)

        im = service_italics_marks.get(message.service, default_italics_mark)

        self.log.info(
            self.class_name, msg="sending chat prompt to openai", engine=engine
        )
        response = self.openai.get_response(engine, prompt)
        self.log.info(self.class_name, response=response)
        if response != "":
            return Response(
                confidence=10,
                text=f"{im}{response}{im}",
                why="OpenAI made me say it!",
            )

        return Response()

    def __str__(self):
        return "OpenAI Fallback Module"

    # TODO: integration tests that make sense
