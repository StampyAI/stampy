from functools import cache
from utilities.serviceutils import (
    ServiceUser,
    ServiceServer,
    ServiceChannel,
    ServiceMessage,
    Services
)
from typing import Any


class SlackUtilities:
    __instance = None
    client = None

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

    def stampy_is_author(self, message):
        return "stampy" in message.author.name and message.author.is_bot


utils = SlackUtilities.get_instance()


# Making Lookup API calls
# Making them a cache as most slack API calls are limited to 20 per minute

@cache
def lookup_user(id: str) -> tuple[str, str, bool]:
    user = utils.client.web_client.api_call(
        api_method="users.info",
        params={"user": id}
    )
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
    team = utils.client.web_client.api_call(
        api_method="team.info",
        params={"team": id}
    )
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
        api_method="conversations.list",
        params={"team_id": server_id}
    )
    return channels


@cache
def lookup_channel(id: str) -> str:
    channel = utils.client.web_client.api_call(
        api_method="conversations.info",
        params={"channel": id}
    )
    if not channel["ok"]:
        return "Unknown Channel"
    if channel["is_im"]:
        user = lookup_user(channel['user'])[0]
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

    async def send(self, data: str):
        utils.client.web_client.api_call(
            api_method="chat.postMessage",
            params={"channel": self.id, "text": data}
        )


class SlackMessage(ServiceMessage):

    def __init__(self, msg):
        self._message = msg
        author = SlackUser(msg["user"])
        server = SlackTeam(msg["team"])
        channel = SlackChannel(msg["channel"], msg["channel_type"], server)
        service = Services.SLACK
        if "client_msg_id" not in msg and "bot_id" not in msg:
            id = None
        elif "client_msg_id" not in msg:
            id = msg["ts"]  # The Timestamp honestly serves as an ID sometimes.
        else:
            id = msg["client_msg_id"]
        super().__init__(str(id),
                         msg["text"], author, channel, service)
