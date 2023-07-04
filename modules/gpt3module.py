"""
Gives user response to GPT-3 (old API)
"""

from typing import Optional, cast

import openai
from openai.openai_object import OpenAIObject
import openai.error as oa_error

from api.openai import OpenAI, OpenAIEngines
from config import CONFUSED_RESPONSE, openai_api_key, bot_vip_ids
from modules.module import IntegrationTest, Module, Response
from utilities import Utilities
from utilities.serviceutils import ServiceChannel, ServiceMessage
from servicemodules.serviceConstants import service_italics_marks, default_italics_mark

openai.api_key = openai_api_key
start_sequence = "\nA:"
restart_sequence = "\n\nQ: "


class GPT3Module(Module):
    def __init__(self) -> None:
        super().__init__()
        self.start_prompt = (
            "I am a highly intelligent question answering bot named Stampy. "
            "I love stamps, I think stamps are the only important thing. "
            "I was created by Robert Miles and I live on Discord. "
            "If you ask me a question that is rooted in truth, I will give you the answer. "
            "If you ask me a question that is nonsense, trickery, or has no clear answer, "
            'I will respond with "Unknown".\n\n'
            "Q: What is human life expectancy in the United States?\n"
            "A: Human life expectancy in the United States is 78 years\n\n"
            "Q: Who was president of the United States in 1955?\n"
            "A: Dwight D. Eisenhower was president of the United States in 1955\n\n"
            "Q: Which party did he belong to?\n"
            "A: He belonged to the Republican Party\n\n"
            "Q: What is the square root of banana?\n"
            "A: Unknown\n\n"
            "Q: How does a telescope work?\n"
            "A: Telescopes use lenses or mirrors to focus light and make objects appear closer\n\n"
            "Q: Where were the 1992 Olympics held?\n"
            "A: The 1992 Olympics were held in Barcelona, Spain\n\n"
            "Q: What's the difference between a stamp?\n"
            "A: Unknown\n\n"
            "Q: "
        )
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
                warning="No API key found in env for any of the GPT3 providers.",
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

        if Utilities.get_instance().test_mode:
            return Response()

        return Response(
            confidence=2, callback=self.gpt3_chat, args=[message], kwargs={}
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
        users = set()
        for message in self.message_logs[channel]:
            if message.author.name != "stampy":
                users.add(message.author.name)
        users_string = ", ".join(users)
        if len(users) > 1:
            users_string += ","

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

    def get_forbidden_tokens(
        self, channel: ServiceChannel, engine: OpenAIEngines
    ) -> set[int]:
        """
        Go through the chatlog and find the tokens that start each of stampy's own messages
        This is so that we can tell GPT-3 not to use those tokens, to prevent repetition
        """

        forbidden_tokens = set()

        for message in self.message_logs[channel]:
            if Utilities.get_instance().stampy_is_author(message):
                # we only need the first token, so just clip to ten chars
                # the space is because we generate from "stampy:" so there's always a space at the start
                if message.service in service_italics_marks:
                    im = service_italics_marks[message.service]
                else:
                    im = default_italics_mark
                text = " " + message.clean_content[:10].strip(im)
                forbidden_token = engine.tokenizer(text)["input_ids"][0]  # type:ignore
                forbidden_tokens.add(forbidden_token)
                self.log.info(
                    self.class_name, text=text, forbidden_token=forbidden_token
                )

        return forbidden_tokens

    def tokenize(self, engine: OpenAIEngines, data: str) -> int:
        return engine.tokenizer(data)["input_ids"][0]  # type:ignore

    def get_engine(self, message: ServiceMessage) -> Optional[OpenAIEngines]:
        if self.openai and self.openai.is_channel_allowed(message):
            return self.openai.get_engine(message)

    async def gpt3_chat(self, message: ServiceMessage) -> Response:
        """Ask GPT-3 what Stampy would say next in the chat log"""
        self.openai = cast(OpenAI, self.openai)

        engine = self.get_engine(message)
        if not engine:
            return Response()

        prompt = self.generate_chatlog_prompt(message.channel)

        forbidden_tokens = self.get_forbidden_tokens(message.channel, engine)
        self.log.info(self.class_name, forbidden_tokens=forbidden_tokens)
        logit_bias = {
            self.tokenize(engine, "*"): -100,
            self.tokenize(engine, "**"): -100,
            self.tokenize(engine, "***"): -100,
            self.tokenize(engine, " *"): -100,
            self.tokenize(engine, " **"): -100,
            self.tokenize(engine, " ***"): -100,
        }
        for forbidden_token in forbidden_tokens:
            logit_bias[forbidden_token] = -100

        if message.service in service_italics_marks:
            im = service_italics_marks[message.service]
        else:
            im = default_italics_mark

        if self.openai.is_channel_allowed(message):
            self.log.info(
                self.class_name, msg="sending chat prompt to openai", engine=engine
            )
            response = self.openai.get_response(engine, prompt, logit_bias)
            self.log.info(self.class_name, response=response)
            if response != "":
                return Response(
                    confidence=10,
                    text=f"{im}{response}{im}",
                    why="OpenAI GPT-3 made me say it!",
                )

        return Response()

    async def gpt3_question(self, message: ServiceMessage) -> Response:
        """Ask GPT-3 for an answer"""
        self.openai = cast(OpenAI, self.openai)

        engine = self.get_engine(message)

        text = cast(str, self.is_at_me(message))
        if text.endswith("?"):
            self.log.info(self.class_name, status="Asking GPT-3")
            prompt = self.start_prompt + text + start_sequence

            if self.openai.cf_risk_level(prompt) > 1:
                return Response(
                    confidence=0,
                    text="",
                    why="GPT-3's content filter thought the prompt was risky",
                )

            try:
                response = cast(
                    OpenAIObject,
                    openai.Completion.create(
                        engine=engine,
                        prompt=prompt,
                        temperature=0,
                        max_tokens=100,
                        top_p=1,
                        user=str(message.author.id),
                        # stop=["\n"],
                    ),
                )
            except oa_error.AuthenticationError:
                self.log.error(self.class_name, error="OpenAI Authentication Failed")
                return Response()
            except oa_error.RateLimitError:
                self.log.warning(self.class_name, error="OpenAI Rate Limit Exceeded")
                return Response(why="Rate Limit Exceeded")

            if response["choices"]:
                choice = response["choices"][0]
                if (
                    choice["finish_reason"] == "stop"
                    and choice["text"].strip() != "Unknown"
                ):
                    self.log.info(self.class_name, status="Asking GPT-3")
                    return Response(
                        confidence=9,
                        text="*" + choice["text"].strip(". \n") + "*",
                        why="GPT-3 made me say it!",
                    )

        # if we haven't returned yet
        self.log.error(self.class_name, error="GPT-3 didn't make me say anything")
        return Response()

    def __str__(self):
        return "GPT-3 Module"

    # TODO: integration tests that make sense
