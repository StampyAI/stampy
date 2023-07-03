"""
Gives basic responses in the style of a therapy bot. Lower priority than LLM modules.
"""

import re
import random
from modules.module import Module, Response
from database.eliza_db import psychobabble, reflections
from utilities.serviceutils import ServiceMessage


class Eliza(Module):
    def __init__(self):
        super().__init__()
        self.psychobabble = psychobabble
        self.reflections = reflections

    def __str__(self) -> str:
        return "Eliza"

    def reflect(self, fragment: str) -> str:
        """
        Convert a string to parrot it back
        'I am your friend' -> 'You are my friend' etc.
        """
        tokens = fragment.lower().split()
        for i, token in enumerate(tokens):
            if token in self.reflections:
                tokens[i] = self.reflections[token]
        return " ".join(tokens)

    def analyze(self, statement: str) -> str:
        # self.log(self.class_name, msg="analyzing with ELIZA")
        for pattern, responses in self.psychobabble:
            match = re.match(pattern, statement.lower().rstrip(".!"))
            if match:
                response = random.choice(responses)
                return response.format(*[self.reflect(g) for g in match.groups()])
        return ""

    def process_message(self, message: ServiceMessage) -> Response:
        if text := self.is_at_me(message):
            # ELIZA can respond to almost anything, so it only talks if nothing else has, hence 1 confidence
            if (
                text.startswith("is ") and text[-1] != "?"
            ):  # stampy is x becomes "you are x"
                text = "you are " + text.partition(" ")[2]
            result = self.dereference(
                self.analyze(text).replace("<<", "{{").replace(">>", "}}"),
                message.author.display_name,
            )
            if result:
                return Response(
                    confidence=1,
                    text=result,
                    why=f"{message.author.display_name} said '{text}', and ELIZA responded '{result}'",
                )
        return Response()
