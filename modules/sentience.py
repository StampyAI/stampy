"""
The most dangerous module. Only enable if you are an accelerationist

The dark truth
This module sends a default message at low priority
`s, <literally anything>`
"""

from config import CONFUSED_RESPONSE
from modules.module import Module, Response


class Sentience(Module):
    def process_message(self, message):
        if self.is_at_me(message):
            self.log.info("Sentience", msg="Confused Response Sent")
            return Response(confidence=0.0000001, text=CONFUSED_RESPONSE)
        else:
            return Response()

    def __str__(self):
        return "Sentience"
