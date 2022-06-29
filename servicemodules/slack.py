import asyncio
import sys
import inspect
import threading
from utilities import (
    Utilities,
    is_test_message,
    is_test_question,
    is_test_response,
    get_question_id
)
from utilities.slackutils import SlackUtilities, SlackMessage
from modules.module import Response
from collections.abc import Iterable
from datetime import datetime
from config import (
    TEST_RESPONSE_PREFIX,
    maximum_recursion_depth,
    slack_app_token,
    slack_bot_token
)
from slack_sdk.socket_mode import SocketModeClient
from slack_sdk.socket_mode.response import SocketModeResponse
from slack_sdk.socket_mode.request import SocketModeRequest
from slack_sdk.web import WebClient


class SlackHandler():

    def __init__(self):
        self.utils = Utilities.get_instance()
        self.slackutils = SlackUtilities.get_instance()
        self.modules = self.utils.modules_dict.values()

    def process_event(self, client: SocketModeClient,
                      req: SocketModeRequest) -> None:
        if req.type == "events_api":
            # Acknowledge the request
            response = SocketModeResponse(envelope_id=req.envelope_id)
            client.send_socket_mode_response(response)

            if (req.payload["event"]["type"] == "message"
               and req.payload["event"].get("subtype") is None):
                # import json
                # with open("output.json", "w") as f:
                #     f.write(json.dumps(req.payload))
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
            print("TESTING" + message.content)
        elif from_stampy:
            for module in self.modules:
                module.process_message_from_stampy(message)
            return

        print("#######################################################")
        print("SLACK MESSAGE")
        print(datetime.now().isoformat(sep=" "))
        if message.channel.channel_type != "im":  # If not a DM.
            print(f"Message: id={message.id} in '{message.channel.name}' (id={message.channel.id})")
        else:
            print(f"DM: id={message.id}")
        print(f"from {message.author.name} (id={message.author.id})")
        print(f"    {message.content}")
        print("####################################")

        responses = [Response()]
        for module in self.modules:
            print(f"# Asking module: {module}")
            response = module.process_message(message)
            if response:
                response.module = module
                if response.callback:
                    response.confidence -= 0.001
                responses.append(response)
        print("####################################")

        for i in range(maximum_recursion_depth):
            responses = sorted(responses, key=(lambda x: x.confidence), reverse=True)

            print("Responses:")
            for response in responses:
                if response.callback:
                    args_string = ", ".join([a.__repr__() for a in response.args])
                    if response.kwargs:
                        args_string += ", " + ", ".join(
                            [f"{k}={v.__repr__()}" for k, v in response.kwargs.items()]
                        )
                    print(
                        f"  {response.confidence}: {response.module}: `{response.callback.__name__}("
                        f"{args_string})`"
                    )
                else:
                    print(f'  {response.confidence}: {response.module}: "{response.text}"')
                    if response.why:
                        print(f'       (because "{response.why}")')

            top_response = responses.pop(0)

            if top_response.callback:
                print("top response is a callback.  Calling it")
                if inspect.iscoroutinefunction(top_response.callback):
                    new_response = asyncio.run(top_response.callback(*top_response.args, **top_response.kwargs))
                else:
                    new_response = top_response.callback(*top_response.args, **top_response.kwargs)

                new_response.module = top_response.module
                responses.append(new_response)
            else:
                if top_response:
                    if self.utils.test_mode:
                        if is_test_response(message.content):
                            return
                        if is_test_question(message.content):
                            assert isinstance(top_response.text, str)
                            top_response.text = (
                                TEST_RESPONSE_PREFIX + str(get_question_id(message)) + ": " + top_response.text
                            )
                    print("Replying:", top_response.text)
                    if isinstance(top_response.text, str):
                        asyncio.run(message.channel.send(top_response.text))
                    elif isinstance(top_response.text, Iterable):
                        for chunk in top_response.text:
                            asyncio.run(message.channel.send(chunk))
                print("#######################################################")
                sys.stdout.flush()
                return
        # If we get here we've hit maximum_recursion_depth.
        asyncio.run(message.channel.send("[Stampy's ears start to smoke.  There is a strong smell of recursion]"))

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
            logger=log
        )

        self.slackutils.client.socket_mode_request_listeners.append(
            self.process_event
        )

        self.slackutils.client.connect()
        # Keep Alive
        event.wait()

    def start(self, event: threading.Event) -> threading.Timer:
        t = threading.Timer(1, self._start, args=[event])
        t.name = "Slack Thread"
        if slack_app_token != "null" and slack_bot_token != "null":
            t.start()
        else:
            print("Skipping Slack since our token's aren't configured!")
        return t
