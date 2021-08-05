from modules.module import Module, Response
import discord
import openai
from config import openai_api_key, rob_id

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

    def process_message(self, message, client=None):
        if type(message.channel) == discord.DMChannel:
            if message.author.id != rob_id:
                print(message.author.id, type(message.author.id))
                return Response()

        if self.is_at_me(message):
            text = self.is_at_me(message)

            if text.endswith("?"):
                # if it's a question, return we can answer with low confidence,
                # so other modules will go first and API is called less
                return Response(
                    confidence=2, callback=self.gpt3_question, args=[message], kwargs={"client": client}
                )
            else:
                print("No ? at end, no GPT-3")

        # This is either not at me, or not something we can handle
        return Response()

    async def gpt3_question(self, message, client=None):
        """Ask GPT-3 for an answer"""

        guild, _ = self.get_guild_and_invite_role()

        bot_dev_role = discord.utils.get(guild.roles, name="bot dev")
        member = guild.get_member(message.author.id)

        if message.author.id == rob_id:
            engine = "davinci"
        elif member and (bot_dev_role in member.roles):
            engine = "curie"
        else:
            engine = "ada"

        text = self.is_at_me(message)

        if text.endswith("?"):
            print("Asking GPT-3")
            prompt = self.start_prompt + text + start_sequence

            try:
                response = openai.Completion.create(
                    engine=engine,
                    prompt=prompt,
                    temperature=0,
                    max_tokens=100,
                    top_p=1,
                    stop=["\n"],
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
                        text="*" + choice["text"].strip(". ") + "*",
                        why="GPT-3 made me say it!",
                    )

        # if we haven't returned yet
        print("GPT-3 failed:")
        return Response()

    def __str__(self):
        return "GPT-3 Questions Module"
