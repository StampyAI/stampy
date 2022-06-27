import os
import sys
import inspect
import discord
import unicodedata
from utilities import (
    Utilities,
    get_question_id,
    is_test_response,
    is_test_message,
    is_test_question,
    get_git_branch_info,
)
from modules.module import Response
from modules.reply import Reply
from modules.questions import QQManager
from modules.wolfram import Wolfram
from modules.duckduckgo import DuckDuckGo
from modules.videosearch import VideoSearch
from modules.ANSearch import ANSearch
from modules.invitemanager import InviteManager
from modules.stampcollection import StampsModule
from modules.StampyControls import StampyControls
from modules.gpt3module import GPT3Module
from modules.Factoids import Factoids
from modules.wikiUpdate import WikiUpdate
from modules.wikiUtilities import WikiUtilities
from modules.testModule import TestModule
from modules.sentience import Sentience
from collections.abc import Iterable
from datetime import datetime, timezone, timedelta
from config import (
    discord_token,
    database_path,
    prod_local_path,
    ENVIRONMENT_TYPE,
    bot_dev_channel_id,
    TEST_RESPONSE_PREFIX,
    maximum_recursion_depth,
    acceptable_environment_types,
)

modules_dict = {
    "StampyControls": StampyControls(),
    "StampsModule": StampsModule(),
    "QQManager": QQManager(),
    "VideoSearch": VideoSearch(),
    "ANSearch": ANSearch(),
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


class MockAuthor:
    def __init__(self, name):
        self.name = name
        self.id = name
        self.display_name = name
        self.roles = []


class MockMessage:
    def __init__(self, content, author, channel):
        self.content = content
        self.author = MockAuthor(author)
        self.channel = MockChannel(author, channel)
        self.clean_content = content.lower()
        self.created_at = datetime.now(timezone.utc)
        self.id = get_question_id(self)
        self.mentions = []

    def __repr__(self):
        return f"MockMessage({self.content})"


class MockGuild:
    def __init__(self, name):
        self.id = name


class MockChannel:
    def __init__(self, author_name, name):
        self.id = name
        self.name = name
        self.guild = MockGuild(name)
        self.recipient = MockAuthor(author_name)

    def __repr__(self):
        return f"MockChannel({self.id})"


def stampy_response(text, author, channel):
    message = MockMessage(text, author, channel)
    if not modules[0].is_at_me(message):
        message = MockMessage("stampy " + text, author, channel)

    responses = [Response()]

    for module in modules:
        print(f"# Asking module: {module}")
        response = module.process_message(message)
        if response:
            response.module = module  # tag it with the module it came from, for future reference
            if response.callback:  # break ties between callbacks and text in favour of text
                response.confidence -= 0.001
            responses.append(response)
    print("#####################################")

    for i in range(maximum_recursion_depth):  # don't hang if infinite regress
        responses = sorted(responses, key=(lambda x: x.confidence), reverse=True)
        # print some debug
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
            print("Top response is a callback. Calling it")
            new_response = top_response.callback(*top_response.args, **top_response.kwargs)
            new_response.module = top_response.module
            responses.append(new_response)
        else:
            if top_response:
                print("Replying:", top_response.text)
                if isinstance(top_response.text, Iterable):
                    top_response.text = "".join(top_response.text)
                return top_response
            print("########################################################")
            sys.stdout.flush()
