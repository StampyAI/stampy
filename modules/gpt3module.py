from api.gooseai import GooseAI
from api.openai import OpenAI
from config import (
    CONFUSED_RESPONSE,
    openai_api_key,
    rob_id,
    service_italics_marks,
    default_italics_mark,
)
from modules.module import Module, Response
from utilities.serviceutils import ServiceMessage
import openai

openai.api_key = openai_api_key
start_sequence = "\nA:"
restart_sequence = "\n\nQ: "


class GPT3Module(Module):
    def __init__(self):
        super().__init__()
        self.class_name = "GPT3Module"
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
        self.message_logs = {}  # one message log per channel
        self.log_max_messages = 10  # don't store more than X messages back
        self.log_max_chars = 1500  # total log length shouldn't be longer than this
        self.log_message_max_chars = 500  # limit message length to X chars (remove the middle part)
        self.OpenAI = OpenAI()
        self.GooseAI = GooseAI()

    def process_message(self, message: ServiceMessage) -> Response:
        self.message_log_append(message)

        if message.is_dm:
            if message.author.id != rob_id:
                self.log.info(self.class_name, author=message.author.id, author_type=type(message.author.id))
                return Response()

        if not self.is_at_me(message):
            return Response()

        return Response(confidence=2, callback=self.gpt3_chat, args=[message], kwargs={})

    def process_message_from_stampy(self, message):
        self.message_log_append(message)

    def message_log_append(self, message):
        """Store the message in the log"""

        # make sure we have a list in there for this channel
        self.message_logs[message.channel] = self.message_logs.get(message.channel, [])

        self.message_logs[message.channel].append(message)
        self.message_logs[message.channel] = self.message_logs[message.channel][-self.log_max_messages :]

    def generate_chatlog_prompt(self, channel):
        users = set([])
        for message in self.message_logs[channel]:
            if message.author.name != "stampy":
                users.add(message.author.name)
        users_string = ", ".join(users)
        if len(users) > 1:
            users_string += ","

        chatlog_string = self.generate_chatlog(channel)

        prompt = (
            f"The following is a transcript of a conversation between {users_string} and Stampy.\n"
            f"Stampy is helpful, intelligent, and sarcastic. He loves stamps, and always says something different every time.\n\n"
            f"{chatlog_string}stampy:"
        )

        self.log.info(self.class_name, prompt=prompt)
        return prompt

    def generate_chatlog(self, channel):
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

    def get_forbidden_tokens(self, channel, engine):
        """
        Go through the chatlog and find the tokens that start each of stampy's own messages
        This is so that we can tell GPT-3 not to use those tokens, to prevent repetition
        """

        forbidden_tokens = set([])

        for message in self.message_logs[channel]:
            if message.author.name == "stampy":
                # we only need the first token, so just clip to ten chars
                # the space is because we generate from "stampy:" so there's always a space at the start
                if message.service in service_italics_marks:
                    im = service_italics_marks[message.service]
                else:
                    im = default_italics_mark
                text = " " + message.clean_content[:10].strip(im)
                forbidden_token = engine.tokenizer(text)["input_ids"][0]
                forbidden_tokens.add(forbidden_token)
                self.log.info(self.class_name, text=text, forbidden_token=forbidden_token)

        return forbidden_tokens

    def tokenize(self, engine, data: str) -> int:
        return engine.tokenizer(data)["input_ids"][0]

    def get_engine(self, message: ServiceMessage, force_goose=False):
        if self.OpenAI.is_channel_allowed(message) and not force_goose:
            return self.OpenAI.get_engine(message)
        return self.GooseAI.get_engine()

    async def gpt3_chat(self, message):
        """Ask GPT-3 what Stampy would say next in the chat log"""

        engine = self.get_engine(message)
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

        if self.OpenAI.is_channel_allowed(message):
            response = self.OpenAI.get_response(engine, prompt, logit_bias)
            self.log.info(self.class_name, response=response)
            if response != "":
                return Response(confidence=10, text=f"{im}{response}{im}", why="OpenAI GPT-3 made me say it!")

            # If OpenAI Failed, redo work and try GooseAI.
            self.log.critical(self.class_name, msg="OpenAI Failed! Trying GooseAI!")
            engine = self.get_engine(message, force_goose=True)
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

        response = self.GooseAI.get_response(engine, prompt, logit_bias)
        self.log.info(self.class_name, response=response)
        if response != "":
            return Response(confidence=10, text=f"{im}{response}{im}", why="GooseAI GPT-3 made me say it!")

        return Response()

    async def gpt3_question(self, message):
        """Ask GPT-3 for an answer"""

        engine = self.get_engine(message)

        text = self.is_at_me(message)
        if text.endswith("?"):
            self.log.info(self.class_name, status="Asking GPT-3")
            prompt = self.start_prompt + text + start_sequence

            if self.cf_risk_level(prompt) > 1:
                return Response(
                    confidence=0,
                    text="",
                    why="GPT-3's content filter thought the prompt was risky",
                )

            try:
                response = openai.Completion.create(
                    engine=engine,
                    prompt=prompt,
                    temperature=0,
                    max_tokens=100,
                    top_p=1,
                    user=str(message.author.id),
                    # stop=["\n"],
                )
            except openai.error.AuthenticationError:
                self.log.error(self.class_name, error="OpenAI Authentication Failed")
                return Response()
            except openai.error.RateLimitError:
                self.log.warning(self.class_name, error="OpenAI Rate Limit Exceeded")
                return Response(why="Rate Limit Exceeded")

            if response["choices"]:
                choice = response["choices"][0]
                if choice["finish_reason"] == "stop" and choice["text"].strip() != "Unknown":
                    self.log.info(self.class_name, status="Asking GPT-3")
                    return Response(
                        confidence=10,
                        text="*" + choice["text"].strip(". \n") + "*",
                        why="GPT-3 made me say it!",
                    )

        # if we haven't returned yet
        self.log.error(self.class_name, error="GPT-3 didn't make me say anything")
        return Response()

    def __str__(self):
        return "GPT-3 Module"

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                question="GPT3 api is only hit in production because it is expensive?",
                expected_response=CONFUSED_RESPONSE,
            )  # TODO write actual test for this
        ]
