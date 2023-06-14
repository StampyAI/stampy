from typing import Optional, Union

import discord

from servicemodules.serviceConstants import Services
from utilities.serviceutils import (
    ServiceChannel,
    ServiceMessage,
    ServiceRole,
    ServiceServer,
    ServiceUser,
)


class DiscordUser(ServiceUser):
    def __init__(self, user: discord.abc.User):
        super().__init__(user.name, user.display_name, str(user.id))
        self._user = user
        if hasattr(user, "roles"):
            self.parse_discord_roles(user.roles)
        self.discriminator = user.discriminator
        self.full_name = f"{self.name}#{self.discriminator}"

    def parse_discord_roles(self, roles: list[discord.Role]) -> None:
        for role in roles:
            self.roles.append(ServiceRole(role.name, str(role.id)))


class DiscordChannel(ServiceChannel):
    def __init__(self, channel: discord.abc.Messageable, server: Optional[ServiceServer]) -> None:
        self._channel: discord.abc.Messageable = channel
        self.history = channel.history
        channel_id = str(getattr(channel, "id", 0))
        channel_name = str(getattr(channel, "name", ""))
        
        # if not isinstance(channel, discord.DMChannel):
        #     channel_id = channel.id
        # else:
        #     channel_id = 0
        # if not isinstance(channel, discord.DMChannel) and not isinstance(channel, discord.abc.Messageable):
        #     name = channel.name
        # else:
        #     name = ""
        super().__init__(channel_name, channel_id, server)

    @property
    def guild(self) -> Optional[ServiceServer]:
        """
        Alias for server for discord message compatibility.
        """
        return self.server

    async def send(self, *args, **kwargs) -> discord.message.Message:
        return await self._channel.send(*args, **kwargs)


class DiscordMessage(ServiceMessage):
    def __init__(self, msg: discord.message.Message):
        self._message = msg
        author = DiscordUser(msg.author)
        guild: Optional[ServiceServer]
        if msg.guild:
            guild = ServiceServer(msg.guild.name, str(msg.guild.id))
        else:
            guild = None
        channel = DiscordChannel(msg.channel, guild)
        service = Services.DISCORD

        super().__init__(str(msg.id), msg.content, author, channel, service)
        self.clean_content = msg.clean_content.replace("\u200b", "")
        self.mentions: list[DiscordUser]
        self._parse_discord_mentions(msg.mentions)
        self.reference = None
        if msg.reference and msg.reference.resolved:
            self.reference = DiscordMessage(msg.reference.resolved) if isinstance(msg.reference.resolved, discord.message.Message) else None
        self.reactions = msg.reactions  # We need reactions for recalculating stamps from history
        self.author: DiscordUser
        if guild is None:
            self.is_dm = True

    def _parse_discord_mentions(self, mentions: list[Union[discord.user.User, discord.Member]]):
        for user in mentions:
            self.mentions.append(DiscordUser(user))

def user_has_role(user: ServiceUser, role_id: Union[str, int]):
    return discord.utils.get(user.roles, id=int(role_id)) is not None
