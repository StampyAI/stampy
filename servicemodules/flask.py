from flask import Response as FlaskResponse
from collections.abc import Iterable
from config import TEST_RESPONSE_PREFIX, maximum_recursion_depth
from flask import Flask, request
from modules.module import Response
from structlog import get_logger
from utilities import (
    flaskutils,
    Utilities,
    is_test_message,
    is_test_question,
    is_test_response,
    get_question_id,
)
from utilities.flaskutils import FlaskMessage, FlaskUtilities
import asyncio
import inspect
import json
import sys
import threading

class_name = "FlaskHandler"
log = get_logger()
app = Flask(class_name)
app.logger = log


class FlaskHandler(threading.Thread):
    def __init__(self):
        super().__init__(name="Flask Handler", daemon=True)
        self.utils = Utilities.get_instance()
        self.flaskutils = FlaskUtilities.get_instance()
        self.service_utils = self.flaskutils
        self.modules = self.utils.modules_dict

    def process_event(self) -> FlaskResponse:
        """
        Message Structure:

        {
            "content": str,
            "key": str,
            "modules": list[str]
        }

        Keys are currently defined in utilities.flaskutils
        """
        if request.is_json:
            message = request.get_json()
            message[
                "content"
            ] += " s"  # This plus s should make it always trigger the is_at_me functions.
        else:
            content = (
                request.form.get("content") + " s"
            )  # This plus s should make it always trigger the is_at_me functions.
            key = request.form.get("key")
            modules = json.loads(
                request.form.get("modules", json.dumps(list(self.modules.keys())))
            )
            message = {"content": content, "key": key, "modules": modules}
        response = self.on_message(FlaskMessage(message))
        log.debug(class_name, response=response, type=type(response))
        return response

    def process_list_modules(self) -> FlaskResponse:
        return FlaskResponse(json.dumps(list(self.modules.keys())))

    def on_message(self, message: FlaskMessage) -> FlaskResponse:
        if is_test_message(message.content) and self.utils.test_mode:
            log.info(class_name, type="TEST MESSAGE", message_content=message.content)

        log.info(
            class_name,
            message_id=message.id,
            message_channel_name=message.channel.name,
            message_author_name=message.author.display_name,
            message_author_id=message.author.id,
            message_channel_id=message.channel.id,
            message_content=message.content,
        )

        responses = [Response()]
        for key in self.modules:
            if message.modules and key not in message.modules:
                log.info(class_name, msg=f"# Skipping module: {key}")
                continue  # Skip this module if it's not requested.
            module = self.modules[key]
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
                    response_text=response.text,
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
                    log.info(class_name, top_response=top_response.text)
                    if isinstance(top_response.text, str):
                        ret = FlaskResponse(top_response.text, 200)
                    elif isinstance(top_response.text, Iterable):
                        builder = ""
                        for chunk in top_response.text:
                            builder += chunk
                        ret = FlaskResponse(builder, 200)
                    else:
                        ret = FlaskResponse(
                            "I don't have anything to say about that.", 200
                        )
                else:
                    ret = FlaskResponse("I don't have anything to say about that.", 200)
                sys.stdout.flush()
                return ret
        # If we get here we've hit maximum_recursion_depth.
        return FlaskResponse(
            "[Stampy's ears start to smoke.  There is a strong smell of recursion]", 200
        )

    def run(self):
        app.add_url_rule("/", view_func=self.process_event, methods=["POST"])
        app.add_url_rule(
            "/list_modules", view_func=self.process_list_modules, methods=["GET"]
        )
        app.run(host="0.0.0.0", port=2300, debug=False)

    def stop(self):
        exit()
        raise SystemExit

    def start(self, event: threading.Event) -> threading.Thread:
        t = threading.Timer(1, flaskutils.kill_thread, args=[event, self])
        t.name = "Flask Killer"
        t.start()
        super().start()
        return self
