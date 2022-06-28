from datetime import datetime, timezone
from enum import Enum

class Services(Enum):
    DISCORD = "discord"
    CLI = "cli"


class SMAuthor:
    def __init__(self, name: str):
        self.name = name
        self.id = name
        self.display_name = name
        self.roles = []


class ServiceMessage:
    def __init__(self, content: str, author: str, channel: str,
                 service: Services):
        self.content = content
        self.author = SMAuthor(author)
        self.channel = SMChannel(author, channel)
        self.service = service
        self.clean_content = content.lower()
        self.service = service
        self.created_at = datetime.now(timezone.utc)
        self.id = author
        self.mentions = []

    def __repr__(self):
        return f"ServiceMessage({self.content})"


class SMGuild:
    def __init__(self, name: str):
        self.id = name


class SMChannel:
    def __init__(self, author_name: str, name: str):
        self.id = name
        self.name = name
        self.guild = SMGuild(name)
        self.recipient = SMAuthor(author_name)

    def __repr__(self):
        return f"SMChannel({self.id})"
