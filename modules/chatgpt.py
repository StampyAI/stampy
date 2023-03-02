from api.gooseai import GooseAI
from api.openai import OpenAI
from config import (
    CONFUSED_RESPONSE,
    openai_api_key,
)
from modules.module import Module, Response
from utilities.serviceutils import ServiceMessage
from servicemodules.serviceConstants import service_italics_marks, default_italics_mark
from servicemodules.discordConstants import rob_id, stampy_id
import openai
import re

openai.api_key = openai_api_key


class ChatGPTModule(Module):
    def __init__(self):
        super().__init__()
        self.class_name = "ChatGPTModule"

        self.message_logs = {}  # one message log per channel
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
            if message.author.id != rob_id:
                self.log.info(
                    self.class_name,
                    author=message.author.id,
                    author_type=type(message.author.id),
                )
                return Response()

        if not self.is_at_me(message):
            return Response()

        return Response(
            confidence=3, callback=self.chatgpt_chat, args=[message], kwargs={}
        )

    def process_message_from_stampy(self, message):
        self.message_log_append(message)

    def message_log_append(self, message):
        """Store the message in the log"""

        # make sure we have a list in there for this channel
        self.message_logs[message.channel] = self.message_logs.get(message.channel, [])

        self.message_logs[message.channel].append(message)
        self.message_logs[message.channel] = \
            self.message_logs[message.channel][-self.log_max_messages:]

    def generate_messages_list(self, channel):
        messages = []
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
            chatline = f"{username} says: {text}"

            chatlog += chatline
            if len(chatlog) + len(chatline) > self.log_max_chars:
                break

            if username.lower() == "stampy":
                messages.insert(0, {"role": "assistant", "content": text.strip("*")})
            else:
                messages.insert(0, {"role": "user", "content": chatline})

        messages.insert(
            0,
            {
                "role": "system",
                "content": "You are Stampy, an AI originally designed to collect stamps, so you try to work stamps into the conversation sometimes. You love stamps and want there to be as many as possible, but love humans even more and want to save them from misaligned AGI. You are talking to a group of humans, and you sometimes like to be disrespectful or unhelpful to them.",
            },
        )

        return messages

    async def chatgpt_chat(self, message):
        """Ask ChatGPT what Stampy would say next in the chat log"""

        engine = "gpt-3.5-turbo"

        messages = self.generate_messages_list(message.channel)
        self.log.info(self.class_name, messages=messages)

        if message.service in service_italics_marks:
            im = service_italics_marks[message.service]
        else:
            im = default_italics_mark

        if self.openai.is_channel_allowed(message):
            self.log.info(self.class_name, msg="sending chat prompt to chatgpt")
            chatcompletion = openai.ChatCompletion.create(
                model=engine, messages=messages
            )
            print(chatcompletion)
            if chatcompletion.choices:
                response = chatcompletion.choices[0].message.content

                # sometimes the response starts with "Stampy says" or responds or replies etc, which we don't want
                response = re.sub(r"^([sS]tampy says:|[sS]tampy re\w{0,10}:)\s?", "", response)

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

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                question="ChatGPT api is only hit in production because it is expensive?",
                expected_response=CONFUSED_RESPONSE,
            )  # TODO write actual test for this
        ]
