import re
from modules.module import Module, Response
from utilities.serviceutils import ServiceMessage
from utilities.discordutils import DiscordMessage
from servicemodules.serviceConstants import Services


class Why(Module):
    AT_MODULE = re.compile(
        r"[Ww]h(?:(?:y did)|(?:at made)) you say th(?:(?:at)|(?:is))(?P<specific>,? specifically)?"
    )
    FORGOT = "I don't remember saying that."

    def process_message(self, message: ServiceMessage) -> Response:
        if message.service != Services.DISCORD:
            return Response(why="Only Discord is supported.")
        assert isinstance(message, DiscordMessage), "Only Discord is supported."
        text = self.is_at_me(message)
        if text:
            match = self.AT_MODULE.match(text)
            if match:
                specific = match.groups()[0] is not None
                if specific:
                    return Response(
                        confidence=10,
                        callback=self.specific,
                        kwargs={ "self": self, "prompt": message},
                        why="A stamp owner wants to know why I said something.",
                    )
                else:
                    return Response(
                        confidence=10,
                        callback=self.general,
                        kwargs={ "self": self, "prompt": message},
                        why="A stamp owner wants to know why I said something.",
                    )
            else:
                return Response()
        else:
            return Response()

    def __str__(self):
        return "Why"

    def _get_known_messages(self):
        return self.utils.service_modules_dict[Services.DISCORD].messages

    async def _get_message_about(self, message: DiscordMessage) -> str:
        if message.reference:
            return str(message.reference.id)
        async for msg in message.channel.history(oldest_first=False):
            m = DiscordMessage(msg)
            if self.utils.stampy_is_author(m):
                return str(m.id)
        raise Exception("No message from stampy found")

    async def specific(self, prompt: DiscordMessage) -> Response:
        message: DiscordMessage = prompt
        m_id = await self._get_message_about(message)
        messages = self._get_known_messages()
        if m_id not in messages:
            return Response(
                confidence=5, text=self.FORGOT, why="I either didn't say that, or I've restarted since then."
            )
        m = messages[m_id]
        why = m["why"]
        builder = f"In general, it was because {why}\n\nBut here is my traceback:\n\n"
        for step in m["traceback"]:
            builder += f"{step}\n"
        return Response(confidence=10, text=builder, why="I was asked why I said something.")

    async def general(self, prompt: DiscordMessage) -> Response:
        message: DiscordMessage = prompt
        m_id = await self._get_message_about(message)
        messages = self._get_known_messages()
        if m_id not in messages:
            return Response(
                confidence=5, text=self.FORGOT, why="I either didn't say that, or I've restarted since then."
            )
        return Response(confidence=10, text=messages[m_id]["why"], why="I was asked why I said something.")
