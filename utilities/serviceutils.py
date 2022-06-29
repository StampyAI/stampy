from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional


class Services(Enum):
    DISCORD = "discord"
    CLI = "cli"
    SLACK = "slack"


class ServiceRoles():

    def __init__(self, name: str, id: str):
        self.name = name
        self.id = id


class ServiceUser:
    def __init__(self, name: str, display_name: str, id: str):
        self.name = name
        self.id = id
        self.display_name = display_name
        self.roles: List[ServiceRoles] = []


class ServiceServer:
    def __init__(self, name: str, id: str):
        self.name = name
        self.id = id


class ServiceChannel:
    def __init__(self, name: str, id: str, server: Optional[ServiceServer]):
        self.id = id
        self.name = name
        self.server = server

    def __repr__(self):
        return f"ServiceChannel({self.id})"

    async def send(self, content):
        raise NotImplementedError()


class ServiceMessage:
    def __init__(self, id: str, content: str, author: ServiceUser,
                 channel: ServiceChannel, service: Services):
        self.content = content
        self.author = author
        self.channel = channel
        self.service = service
        self.clean_content = content.lower()
        self.service = service
        self.created_at = datetime.now(timezone.utc)
        self.id = id
        self.mentions = []

    def __repr__(self):
        return f"ServiceMessage({self.content})"
