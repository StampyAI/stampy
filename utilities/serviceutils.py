from datetime import datetime, timezone
from typing import List, Optional
from enum import Enum


class Services(Enum):
    DISCORD = "Discord"
    FLASK = "Flask"
    SLACK = "Slack"


class ServiceRole:
    def __init__(self, name: str, id: str):
        self.name = name
        self.id = id

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.id == other
        if hasattr(self, "_role"):
            if type(self._role) == type(other):
                return self._role == other
        if not isinstance(other, ServiceRole):
            return False
        return (self.id == other.id) and type(self) == type(other)

    def __hash__(self):
        """
        This was the discord.User hashing method.  This is required for stamps collection/utilities.
        The hash was added around self.id to handle alphanumerics.
        """
        return hash(self.id) >> 22


class ServiceUser:
    def __init__(self, name: str, display_name: str, id: str):
        self.name = name
        self.id = id
        self.display_name = display_name
        self.roles: List[ServiceRole] = []

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.id == other
        if hasattr(self, "_user"):
            if type(self._user) == type(other):
                return self._user == other
        if not isinstance(other, ServiceUser):
            return False
        return (self.id == other.id) and type(self) == type(other)

    def __hash__(self):
        """
        This was the discord.User hashing method.  This is required for stamps collection/utilities.
        The hash was added around self.id to handle alphanumerics.
        """
        return hash(self.id) >> 22


class ServiceServer:
    def __init__(self, name: str, id: str):
        self.name = name
        self.id = id

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.id == other
        if hasattr(self, "_server"):
            if type(self._server) == type(other):
                return self._server == other
        if not isinstance(other, ServiceServer):
            return False
        return (self.id == other.id) and type(self) == type(other)

    def __hash__(self):
        """
        This was the discord.User hashing method.  This is required for stamps collection/utilities.
        The hash was added around self.id to handle alphanumerics.
        """
        return hash(self.id) >> 22


class ServiceChannel:
    def __init__(self, name: str, id: str, server: Optional[ServiceServer]):
        self.id = id
        self.name = name
        self.server = server

    def __repr__(self):
        return f"ServiceChannel({self.id})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.id == other
        if hasattr(self, "_channel"):
            if type(self._channel) == type(other):
                return self._channel == other
        if not isinstance(other, ServiceChannel):
            return False
        return (self.id == other.id) and type(self) == type(other)

    def __hash__(self):
        """
        This was the discord.User hashing method.  This is required for stamps collection/utilities.
        The hash was added around self.id to handle alphanumerics.
        """
        return hash(self.id) >> 22

    async def send(self, content):
        raise NotImplementedError()


class ServiceMessage:
    def __init__(
        self, id: str, content: str, author: ServiceUser, channel: ServiceChannel, service: Services
    ):
        self.content = content
        self.author = author
        self.channel = channel
        self.service = service
        self.clean_content = content
        self.service = service
        self.created_at = datetime.now(timezone.utc)
        self.id = id
        self.mentions: List[ServiceUser] = []
        self.reference: Optional[ServiceMessage] = None

    def __repr__(self):
        return f"ServiceMessage({self.content})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.id == other
        if hasattr(self, "_message"):
            if type(self._message) == type(other):
                return self._message == other
        if not isinstance(other, ServiceMessage):
            return False
        return (self.id == other.id) and type(self) == type(other)

    def __hash__(self):
        """
        This was the discord.User hashing method.  This is required for stamps collection/utilities.
        The hash was added around self.id to handle alphanumerics.
        """
        return hash(self.id) >> 22
