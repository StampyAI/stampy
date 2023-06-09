from servicemodules.serviceConstants import Services
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional, Union
import discord

@dataclass
class ServiceRole:
    name: str
    id: str
    _role: object = field(default=None, init=False)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.id == other
        if self._role is not None and type(self._role) == type(other):
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


@dataclass
class ServiceUser:
    name: str
    display_name: str
    id: str
    roles: list[ServiceRole] = field(default_factory=list, init=False)
    _user: object = field(default=None, init=False)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.id == other
        if self._user is not None and type(self._user) == type(other):
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

    def __str__(self):
        return str(self.id)


@dataclass
class ServiceServer:
    name: str
    id: str
    _server: object = field(default=None, init=False)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.id == other
        if self._server is None and type(self._server) == type(other):
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


@dataclass
class ServiceChannel:
    name: str
    id: str
    server: Optional[ServiceServer]
    _channel: object = field(default=None, init=False)

    def __repr__(self):
        return f"ServiceChannel({self.id})"

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.id == other
        if self._channel and type(self._channel) == type(other):
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

    SendReturnType = Union[discord.message.Message, None]

    async def send(self, *args, **kwargs) -> SendReturnType: ...


@dataclass
class ServiceMessage:
    id: str
    content: str
    author: ServiceUser
    channel: ServiceChannel
    service: Services
    clean_content: str = field(default="", init=False)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc), init=False)
    mentions: list[ServiceUser] = field(default_factory=list, init=False)
    reference: Optional["ServiceMessage"] = field(default=None, init=False)
    is_dm: bool = field(default=False, init=False)
    _message: object = field(default=None, init=False)
    
    def __repr__(self) -> str:
        content = self.content.replace('"', r'\"')
        return f'ServiceMessage("{content}")'

    def __eq__(self, other: object) -> bool:
        if isinstance(other, int):
            return self.id == other
        if self._message is not None and type(self._message) == type(other):
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
