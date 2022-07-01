import sys
from modules.module import Response
from modules.reply import Reply
from modules.questions import QuestionQueManager
from modules.wolfram import Wolfram
from modules.duckduckgo import DuckDuckGo
from modules.videosearch import VideoSearch
from modules.AlignmentNewsletterSearch import AlignmentNewsletterSearch
from modules.stampcollection import StampsModule
from modules.StampyControls import StampyControls
from modules.gpt3module import GPT3Module
from modules.Factoids import Factoids
from modules.wikiUpdate import WikiUpdate
from modules.wikiUtilities import WikiUtilities
from modules.testModule import TestModule
from modules.sentience import Sentience
from collections.abc import Iterable
from test.discord_mocks import MockMessage
from config import maximum_recursion_depth
from structlog import get_logger

modules_dict = {
    "StampyControls": StampyControls(),
    "StampsModule": StampsModule(),
    "QQManager": QuestionQueManager(),
    "VideoSearch": VideoSearch(),
    "ANSearch": AlignmentNewsletterSearch(),
    "Wolfram": Wolfram(),
    "DuckDuckGo": DuckDuckGo(),
    "Reply": Reply(),
    "GPT3Module": GPT3Module(),
    "Factoids": Factoids(),
    "Sentience": Sentience(),
    "WikiUpdate": WikiUpdate(),
    "WikiUtilities": WikiUtilities(),
    "TestModule": TestModule(),
}
modules = list(modules_dict.values())
log_type = "stam.py"
log = get_logger()


def stampy_response(text, author, channel):
    message = MockMessage(text, author, channel)
    if not modules[0].is_at_me(message):
        message = MockMessage("stampy " + text, author, channel)

    responses = [Response()]

    for module in modules:
        log.info(log_type, msg=f"# Asking module: {module}")
        response = module.process_message(message)
        if response:
            response.module = module  # tag it with the module it came from, for future reference
            if response.callback:  # break ties between callbacks and text in favour of text
                response.confidence -= 0.001
            responses.append(response)

    for i in range(maximum_recursion_depth):  # don't hang if infinite regress
        responses = sorted(responses, key=(lambda x: x.confidence), reverse=True)
        # print some debug
        for response in responses:
            if response.callback:
                args_string = ", ".join([a.__repr__() for a in response.args])
                if response.kwargs:
                    args_string += ", " + ", ".join(
                        [f"{k}={v.__repr__()}" for k, v in response.kwargs.items()]
                    )
                log.info(
                    log_type,
                    msg=f"  {response.confidence}: {response.module}: `{response.callback.__name__}("
                    f"{args_string})`",
                )
            else:
                log.info(log_type, msg=f'  {response.confidence}: {response.module}: "{response.text}"')
                if response.why:
                    log.info(log_type, msg=f'       (because "{response.why}")')

        top_response = responses.pop(0)

        if top_response.callback:
            log.info(log_type, msg="Top response is a callback. Calling it")
            new_response = top_response.callback(*top_response.args, **top_response.kwargs)
            new_response.module = top_response.module
            responses.append(new_response)
        else:
            if top_response:
                log.info(log_type, msg="Replying:" + top_response.text)
                if isinstance(top_response.text, Iterable):
                    top_response.text = "".join(top_response.text)
                return top_response
            sys.stdout.flush()
