from modules.module import Module, Response
import discord
import openai
from config import openai_api_key

openai.api_key = openai_api_key

start_sequence = "\nA:"
restart_sequence = "\n\nQ: "


class GPT3Module(Module):
    def __init__(self):
        self.startprompt = 'I am a highly intelligent question answering bot named Stampy. I love stamps, I think stamps are the only important thing. I was created by Robert Miles and I live on Discord. If you ask me a question that is rooted in truth, I will give you the answer. If you ask me a question that is nonsense, trickery, or has no clear answer, I will respond with "Unknown".\n\nQ: What is human life expectancy in the United States?\nA: Human life expectancy in the United States is 78 years\n\nQ: Who was president of the United States in 1955?\nA: Dwight D. Eisenhower was president of the United States in 1955\n\nQ: Which party did he belong to?\nA: He belonged to the Republican Party\n\nQ: What is the square root of banana?\nA: Unknown\n\nQ: How does a telescope work?\nA: Telescopes use lenses or mirrors to focus light and make objects appear closer\n\nQ: Where were the 1992 Olympics held?\nA: The 1992 Olympics were held in Barcelona, Spain\n\nQ: What\'s the difference between a stamp?\nA: Unknown\n\nQ: '

    def process_message(self, message, client=None):
        # print("GPT-3 canProcessMessage")
        if type(message.channel) == discord.DMChannel:
            if message.author.id != 181142785259208704:
                print(message.author.id, type(message.author.id))
                return Response()

        # guild = client.guilds[0]
        # botdevrole = discord.utils.get(guild.roles, name="bot dev")
        # member = guild.get_member(message.author.id)
        # if member and (botdevrole not in member.roles):
        #     print("Asker is not a bot dev, no GPT-3 for you")
        #     return Response()

        if self.is_at_me(message):
            text = self.is_at_me(message)

            if text.endswith("?"):
                # if it's a question, return we can answer with low confidence, so other modules will go first and API is called less
                return Response(confidence=2,
                                callback=self.gpt3_question,
                                args=[message],
                                kwargs={"client": client})
            print("No ? at end, no GPT-3")
        else:
            print("Not at me, no GPT-3")

        # This is either not at me, or not something we can handle
        return Response()

    async def gpt3_question(self, message, client=None):
        """Ask GPT-3 for an answer"""

        engine = "ada"

        guild = client.guilds[0]
        botdevrole = discord.utils.get(guild.roles, name="bot dev")
        member = guild.get_member(message.author.id)
        if member and (botdevrole in member.roles):
            engine = "curie"

        if message.author.id == 181142785259208704:
            engine = "davinci"

        text = self.is_at_me(message)
        response = Response()

        if text.endswith("?"):
            print("Asking GPT-3")
            prompt = self.startprompt + text + start_sequence

            response = openai.Completion.create(
                engine=engine, prompt=prompt, temperature=0, max_tokens=100, top_p=1, stop=["\n"],
            )

            if response["choices"]:
                choice = response["choices"][0]
                if choice["finish_reason"] == "stop" and choice["text"].strip() != "Unknown":
                    print("GPT-3 Replied!:")
                    response = Response(confidence=10,
                                        text="*" + choice["text"].strip(". ") + "*",
                                        why="GPT-3 made me say it!")

        if not response.confidence:
            print("GPT-3 failed:")

        print(response)
        return response

    def __str__(self):
        return "GPT-3 Questions Module"
