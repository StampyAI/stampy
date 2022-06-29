from utilities.serviceutils import *
from typing import List
import discord


class DiscordUser(ServiceUser):
    
    def __init__(self, user: discord.abc.User):
        super().__init__(user.name, user.display_name, str(user.id))
        self._user = user
        self.parse_discord_roles(user.roles)
        self.discriminator = user.discriminator
        self.full_name = f"{self.name}#{self.discriminator}"


    def parse_discord_roles(self, roles: List[discord.Role]) -> None:
        for role in roles:
            self.roles.append(ServiceRoles(role.name, str(role.id)))


class DiscordChannel(ServiceChannel):

    def __init__(self, channel: discord.abc.Messageable,
                 server: Optional[ServiceServer]):
        self._channel = channel
        if not isinstance(channel, discord.DMChannel):
            name = channel.name
        else:
            name = None
        super().__init__(name, str(channel.id), server)

        # Bring over functions
        self.send = channel.send

    @property
    def guild(self) -> ServiceServer:
        """
        Alias for server for discord message compatibility.
        """
        return self.server


class DiscordMessage(ServiceMessage):

    def __init__(self, msg: discord.message.Message):
        self._message = msg
        author = DiscordUser(msg.author)
        if msg.guild:
            guild = ServiceServer(msg.guild.name, str(msg.guild.id))
        else:
            guild = None
        channel = DiscordChannel(msg.channel, guild)
        service = Services.DISCORD

        super().__init__(str(msg.id), msg.content, author, channel, service)
        self.clean_content = msg.clean_content
        self._parse_discord_mentions(msg.mentions)
        self.reference = msg.reference

    def _parse_discord_mentions(self, mentions: List[discord.abc.User]):
        for user in mentions:
            self.mentions.append(DiscordUser(user.name, user.display_name,
                                             str(user.id)))
