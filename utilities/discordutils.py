from serviceutils import *
from typing import List
import discord


class DiscordUser(ServiceUser):
    
    def __init__(self, name: str, display_name: str, id: int):
        super().__init__(name, display_name, id)

    def parse_discord_roles(roles: List[discord.Roles]) -> None:
        for role in roles:
            self.roles.append(ServiceRoles(role.name, role.id))


class DiscordChannel(ServiceChannel):

    def __init__(self, name: str, id: int, server: Optional[ServiceServer]):
        super().__init__(name, id, server)

    @property
    def guild(self) -> ServiceServer:
        """
        Alias for server for discord message compatibility.
        """
        return self.server


class DiscordMessage(ServiceMessage)

    def __init__(self, msg: discord.message.Message):
        self._message = msg
        a = msg.author
        author = DiscordUser(a.name, a.display_name, a.id)
        author.parse_discord_roles(a.roles)
        if msg.guild:
            guild = ServiceServer(msg.guild.name, msg.guild.id)
        else:
            guild = None
        if not isinstance(msg.channel, discord.DMChannel):
            c_name = msg.channel.name
        else:
            c_name = None
        channel = DiscordChannel(c_name, msg.channel.id, guild)
        service = serviceutils.Services.DISCORD
        super(msg.id, msg.content, author, channel, service)
        self.clean_content = msg.clean_content
        self._parse_discord_mentions(msg.mentions)

    def _parse_discord_mentions(self, mentions: List[discord.abc.User]):
        for user in mentions:
            self.mentions.append(DiscordUser(user.name, user.display_name,
                                             user.id))
