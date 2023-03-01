from collections.abc import Coroutine
from functools import cache
from servicemodules.serviceConstants import Services
from utilities.serviceutils import ServiceUser, ServiceServer, ServiceChannel, ServiceMessage
from typing import Any, Optional


class SlackUtilities:
    __instance = None
    client = None
    user: Optional["SlackUser"] = None

    @staticmethod
    def get_instance():
        if SlackUtilities.__instance is None:
            SlackUtilities()
        return SlackUtilities.__instance

    def __init__(self):
        if SlackUtilities.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            SlackUtilities.__instance = self

    def stampy_is_author(self, message: "SlackMessage") -> bool:
        return self.is_stampy(message.author)

    def is_stampy(self, user: "SlackUser") -> bool:
        if self.user:
            return user == self.user
        if "stampy" in user.name and user.is_bot:
            self.user = user
            return True
        return False

    def is_stampy_mentioned(self, message: "SlackMessage") -> bool:
        for user in message.mentions:
            if self.is_stampy(user):
                return True
        return False


utils = SlackUtilities.get_instance()


# Making Lookup API calls
# Making them a cache as most slack API calls are limited to 20 per minute


@cache
def lookup_user(id: str) -> tuple[str, str, bool]:
    user = utils.client.web_client.api_call(api_method="users.info", params={"user": id})
    if user["ok"]:
        username = user["user"]["name"]
        display_name = user["user"]["profile"]["display_name_normalized"]
        is_bot = user["user"]["is_bot"]
    else:
        username = "Unknown Username"
        display_name = "Unknown Display Name"
        is_bot = False

    return (username, display_name, is_bot)


@cache
def lookup_team(id: str) -> str:
    team = utils.client.web_client.api_call(api_method="team.info", params={"team": id})
    if team["ok"]:
        name = team["team"]["name"]
    else:
        name = "Unknown Team Name"

    return name


# May want to make this clear out anything that is a certain age so you don't
# have to restart stampy when a new channel is made.
@cache
def lookup_channels(server_id: str) -> dict[str, Any]:
    channels = utils.client.web_client.api_call(
        api_method="conversations.list", params={"team_id": server_id}
    )
    return channels


@cache
def lookup_channel(id: str) -> str:
    channel = utils.client.web_client.api_call(api_method="conversations.info", params={"channel": id})
    if not channel["ok"]:
        return "Unknown Channel"
    if channel["is_im"]:
        user = lookup_user(channel["user"])[0]
        return f"DM with {user} (ID: {channel['user']})"
    elif "name" not in channel["channel"]:
        return "Unknown Channel"
    return channel["channel"]["name"]


class SlackUser(ServiceUser):
    def __init__(self, id: str):
        name, display_name, is_bot = lookup_user(id)
        super().__init__(name, display_name, id)
        self.is_bot = is_bot


class SlackTeam(ServiceServer):
    def __init__(self, server_id: str):
        name = lookup_team(server_id)
        super().__init__(name, server_id)


class SlackChannel(ServiceChannel):
    def __init__(self, channel_id: str, channel_type: str, server: SlackTeam):
        name = lookup_channel(channel_id)
        super().__init__(name, channel_id, server)
        self.channel_type = channel_type

    async def send(self, *args, **kwargs) -> None:
        data = kwargs["data"] if "data" in kwargs else args[0]
        utils.client.web_client.api_call(
            api_method="chat.postMessage", params={"channel": self.id, "text": data}
        )


class SlackMessage(ServiceMessage):
    def __init__(self, msg):
        self._message = msg
        server = SlackTeam(msg["team"])
        channel = SlackChannel(msg["channel"], msg["channel_type"], server)
        service = Services.SLACK
        if "client_msg_id" not in msg and "bot_id" not in msg:
            id = None
        elif "client_msg_id" not in msg:
            id = msg["ts"]  # The Timestamp honestly serves as an ID sometimes.
        else:
            id = msg["client_msg_id"]
        super().__init__(str(id), msg["text"], SlackUser(msg["user"]), channel, service)
        self.author: SlackUser
        self.mentions: list[SlackUser] = []
        self._parse_mentions()
        self.clean_content = self.clean_content.replace("<!here>", "@here")
        self.clean_content = self.clean_content.replace("<!channel>", "@channel")
        if channel.id[0] == "D":
            self.is_dm == True

    def _parse_mentions(self):
        for block in self._message["blocks"]:
            if block["type"] == "rich_text":
                for section in block["elements"]:
                    if section["type"] == "rich_text_section":
                        for elm in section["elements"]:
                            if elm["type"] == "user":
                                user = SlackUser(elm["user_id"])
                                self.mentions.append(user)
                                name = ""
                                if user.display_name:
                                    name = f"@{user.display_name}"
                                elif user.name:
                                    name = f"@{user.name}"
                                self.clean_content = self.clean_content.replace(f'<@{elm["user_id"]}>', name)
