import asyncio
import sys
import inspect
import threading
from utilities import (
    Utilities,
    is_test_message,
    is_test_question,
    is_test_response,
    get_question_id,
)
from utilities.slackutils import SlackUtilities, SlackMessage
from modules.module import Response
from collections.abc import Iterable
from datetime import datetime
from config import (
    TEST_RESPONSE_PREFIX,
    maximum_recursion_depth,
    slack_app_token,
    slack_bot_token,
)
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.web import WebClient
from structlog import get_logger
from typing import Generator

log = get_logger()
class_name = "SlackHandler"


class SlackHandler:
    def __init__(self):
        self.utils = Utilities.get_instance()
        self.slackutils = SlackUtilities.get_instance()
        self.service_utils = self.slackutils
        self.modules = self.utils.modules_dict.values()

    def process_event(self, client: SocketModeClient, req: SocketModeRequest) -> None:
        if req.type == "events_api":
            # Acknowledge the request
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)

            if (
                req.payload["event"]["type"] == "message"
                and req.payload["event"].get("subtype") is None
            ):
                self.on_message(SlackMessage(req.payload["event"]))

                """
                client.web_client.reactions_add(
                    name="eyes",
                    channel=req.payload["event"]["channel"],
                    timestamp=req.payload["event"]["ts"],
                )
                """

    def on_message(self, message: SlackMessage):
        from_stampy = self.slackutils.stampy_is_author(message)

        if is_test_message(message.content) and self.utils.test_mode:
            log.info(
                class_name, type="TEST MESSAGE", message_content=message.clean_content
            )
        elif from_stampy:
            for module in self.modules:
                module.process_message_from_stampy(message)
            return

        message_is_dm = True
        if message.channel.channel_type != "im":  # If not a DM.
            message_is_dm = False
        log.info(
            class_name,
            message_id=message.id,
            message_channel_name=message.channel.name,
            message_author_name=message.author.display_name,
            message_author_id=message.author.id,
            message_channel_id=message.channel.id,
            message_is_dm=message_is_dm,
            message_content=message.content,
        )

        responses = [Response()]
        for module in self.modules:
            log.info(class_name, msg=f"# Asking module: {module}")
            response = module.process_message(message)
            if response:
                response.module = module
                if response.callback:
                    response.confidence -= 0.001
                responses.append(response)

        for i in range(maximum_recursion_depth):
            responses = sorted(responses, key=(lambda x: x.confidence), reverse=True)

            for response in responses:
                args_string = ""
                if response.callback:
                    args_string = ", ".join([a.__repr__() for a in response.args])
                    if response.kwargs:
                        args_string += ", " + ", ".join(
                            [f"{k}={v.__repr__()}" for k, v in response.kwargs.items()]
                        )
                log.info(
                    class_name,
                    response_module=response.module,
                    response_confidence=response.confidence,
                    response_is_callback=bool(response.callback),
                    response_callback=response.callback,
                    response_args=args_string,
                    response_text=(
                        response.text
                        if not isinstance(response.text, Generator)
                        else "[Generator]"
                    ),
                    response_reasons=response.why,
                )

            top_response = responses.pop(0)

            if top_response.callback:
                log.info(class_name, msg="top response is a callback.  Calling it")
                if inspect.iscoroutinefunction(top_response.callback):
                    new_response = asyncio.run(
                        top_response.callback(*top_response.args, **top_response.kwargs)
                    )
                else:
                    new_response = top_response.callback(
                        *top_response.args, **top_response.kwargs
                    )

                new_response.module = top_response.module
                responses.append(new_response)
            else:
                if top_response:
                    if self.utils.test_mode:
                        if is_test_response(message.content):
                            return
                        if is_test_question(message.content):
                            top_response.text = (
                                TEST_RESPONSE_PREFIX
                                + str(get_question_id(message))
                                + ": "
                                + (
                                    top_response.text
                                    if not isinstance(top_response.text, Generator)
                                    else "".join(list(top_response.text))
                                )
                            )
                    log.info(class_name, top_response=top_response.text)
                    if isinstance(top_response.text, str):
                        asyncio.run(message.channel.send(top_response.text))
                    elif isinstance(top_response.text, Iterable):
                        for chunk in top_response.text:
                            asyncio.run(message.channel.send(chunk))
                sys.stdout.flush()
                return
        # If we get here we've hit maximum_recursion_depth.
        asyncio.run(
            message.channel.send(
                "[Stampy's ears start to smoke.  There is a strong smell of recursion]"
            )
        )

    def _start(self, event: threading.Event):
        import logging

        logging.basicConfig()
        log = logging.getLogger("Slack")
        log.setLevel(logging.INFO)
        self.slackutils.client = SocketModeClient(
            app_token=slack_app_token,
            web_client=WebClient(token=slack_bot_token),
            trace_enabled=True,
            all_message_trace_enabled=False,
            ping_pong_trace_enabled=False,
            logger=log,
        )

        self.slackutils.client.socket_mode_request_listeners.append(self.process_event)

        self.slackutils.client.connect()
        # Keep Alive
        event.wait()

    def start(self, event: threading.Event) -> threading.Timer:
        t = threading.Timer(1, self._start, args=[event])
        t.name = "Slack Thread"
        if slack_app_token and slack_bot_token:
            t.start()
        else:
            log.info(
                class_name, msg="Skipping Slack since our token's aren't configured!"
            )
        return t
