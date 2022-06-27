import openai
import discord
from modules.module import Module, Response
from config import CONFUSED_RESPONSE
from config import openai_api_key, rob_id
from transformers import GPT2TokenizerFast

openai.api_key = openai_api_key

start_sequence = "\nA:"
restart_sequence = "\n\nQ: "


class GPT3Module(Module):
    def __init__(self):
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
        self.message_logs = {}  # one message log per channel
        self.log_max_messages = 10  # don't store more than X messages back
        self.log_max_chars = 1500  # total log length shouldn't be longer than this
        self.log_message_max_chars = 500  # limit message length to X chars (remove the middle part)

        self.tokenizer = GPT2TokenizerFast.from_pretrained("gpt2")

    def process_message(self, message):
        self.message_log_append(message)

        if type(message.channel) == discord.DMChannel:
            if message.author.id != rob_id:
                print(message.author.id, type(message.author.id))
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
            f"Stampy is helpful, intelligent, and sarcastic. He loves stamps, and always say something different every time.\n\n"
            f"{chatlog_string}stampy:"
        )

        print(prompt)
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

    def get_forbidden_tokens(self, channel):
        """Go through the chatlog and find the tokens that start each of stampy's own messages
        This is so that we can tell GPT-3 not to use those tokens, to prevent repetition"""

        forbidden_tokens = set([])

        for message in self.message_logs[channel]:
            if message.author.name == "stampy":
                # we only need the first token, so just clip to ten chars
                # the space is because we generate from "stampy:" so there's always a space at the start
                text = " " + message.clean_content[:10].strip("*")
                forbidden_token = self.tokenizer(text)["input_ids"][0]
                forbidden_tokens.add(forbidden_token)
                print(text, forbidden_token)

        return forbidden_tokens

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
        except openai.error.AuthenticationError:
            print("OpenAI Authentication Failed")
            return

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

        print(f"Prompt is risk level {output_label}")

        return int(output_label)

    def get_engine(self, message):
        """Pick the appropriate engine to respond to a message with"""

        guild, _ = self.get_guild_and_invite_role()

        bot_dev_role = discord.utils.get(guild.roles, name="bot dev")
        member = guild.get_member(message.author.id)

        if message.author.id == rob_id:
            return "text-davinci-001"
        elif member and (bot_dev_role in member.roles):
            return "text-curie-001"
        else:
            return "text-babbage-001"

    async def gpt3_chat(self, message):
        """Ask GPT-3 what Stampy would say next in the chat log"""

        engine = self.get_engine(message)
        prompt = self.generate_chatlog_prompt(message.channel)

        if self.cf_risk_level(prompt) > 1:
            return Response(
                confidence=0,
                text="",
                why=f"GPT-3's content filter thought the prompt was risky",
            )

        forbidden_tokens = self.get_forbidden_tokens(message.channel)
        print(forbidden_tokens)
        logit_bias = {
            9: -100,  # "*"
            1174: -100,  # "**"
            8162: -100,  # "***"
            1635: -100,  # " *"
            12429: -100,  # " **"
            17202: -100,  # " ***"
        }
        for forbidden_token in forbidden_tokens:
            logit_bias[forbidden_token] = -100

        try:
            response = openai.Completion.create(
                engine=engine,
                prompt=prompt,
                temperature=0,
                max_tokens=100,
                top_p=1,
                # stop=["\n"],
                logit_bias=logit_bias,
                user=str(message.author.id),
            )
        except openai.error.AuthenticationError:
            print("OpenAI Authentication Failed")
            return Response()

        if response["choices"]:
            choice = response["choices"][0]
            if choice["finish_reason"] == "stop" and choice["text"].strip() != "Unknown":
                text = choice["text"].strip(". \n").split("\n")[0]
                print("GPT-3 Replied!:", text)
                return Response(
                    confidence=10,
                    text=f"*{text}*",
                    why="GPT-3 made me say it!",
                )

        return Response()

    async def gpt3_question(self, message):
        """Ask GPT-3 for an answer"""

        engine = self.get_engine(message)

        text = self.is_at_me(message)
        if text.endswith("?"):
            print("Asking GPT-3")
            prompt = self.start_prompt + text + start_sequence

            if self.cf_risk_level(prompt) > 1:
                return Response(
                    confidence=0,
                    text="",
                    why=f"GPT-3's content filter thought the prompt was risky",
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
                print("OpenAI Authentication Failed")
                return Response()

            if response["choices"]:
                choice = response["choices"][0]
                if choice["finish_reason"] == "stop" and choice["text"].strip() != "Unknown":
                    print("GPT-3 Replied!:")
                    return Response(
                        confidence=10,
                        text="*" + choice["text"].strip(". \n") + "*",
                        why="GPT-3 made me say it!",
                    )

        # if we haven't returned yet
        print("GPT-3 failed:")
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
