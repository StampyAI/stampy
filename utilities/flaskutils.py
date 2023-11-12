import json
import threading
import time
from typing import TYPE_CHECKING
from utilities.serviceutils import ServiceUser, ServiceServer, ServiceChannel, ServiceMessage
from servicemodules.serviceConstants import Services
from servicemodules.discordConstants import wiki_feed_channel_id

if TYPE_CHECKING:
    from servicemodules.flask import FlaskHandler


# Depending on how secret we want this, we may want to move it to an environment variable with a JSON dict.
server_keys = {
    "$bF*-6KJ2-K6aR-KB%F": "cli",
}


class FlaskUtilities:
    __instance = None

    @staticmethod
    def get_instance():
        if FlaskUtilities.__instance is None:
            FlaskUtilities()
        return FlaskUtilities.__instance

    def __init__(self):
        if FlaskUtilities.__instance is not None:
            raise Exception("this class is a singleton!")
        else:
            FlaskUtilities.__instance = self

    def stampy_is_author(self, message: "FlaskMessage") -> bool:
        return False  # Flask doesn't process Stampy's messages so it's always False

    def is_stampy(self, user: "FlaskUser") -> bool:
        return False  # Flask doesn't process Stampy's messages so it's always False

    def is_stampy_mentioned(self, message: "FlaskMessage") -> bool:
        return True  # Flask only process messages meant for stampy so assume True


def kill_thread(event: threading.Event, thread: "FlaskHandler"):
    event.wait()
    thread.stop()


class FlaskUser(ServiceUser):
    def __init__(self, key: str):
        super().__init__("User", "User", str(key))


class FlaskServer(ServiceServer):
    def __init__(self, key: str):
        if key not in server_keys:
            raise LookupError("Server is not registered.")
        super().__init__(server_keys[key], key)


class FlaskChannel(ServiceChannel):
    def __init__(self, server: FlaskServer, channel=None):
        super().__init__("Web Interface", channel or "flask_api", server)


class FlaskMessage(ServiceMessage):

    @staticmethod
    def from_dict(data):
        key = data.get('key')
        if not key:
            raise ValueError('No key provided')

        # FIXME: A very hacky way of allowing HTTP requests to claim to come from stampy
        author = data.get('author')
        if author == 'stampy':
            author = FlaskUser(wiki_feed_channel_id)
        else:
            author = FlaskUser(key)

        modules = data.get('modules')
        if not modules:
            raise ValueError('No modules provided')
        if isinstance(modules, str):
            modules = json.loads(modules)

        msg = FlaskMessage(
            content=data['content'],
            service=Services.FLASK,
            author=author,
            channel=FlaskChannel(FlaskServer(key), data.get('channel')),
            id=str(time.time()),
        )
        msg.modules = modules
        msg.clean_content = msg.content
        return msg
