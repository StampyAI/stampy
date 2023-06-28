from __future__ import annotations

from dataclasses import dataclass, field
import inspect
import re
import random
from typing import Callable, Iterable, Literal, Optional, TypedDict, Union

import discord
from structlog import get_logger

from config import TEST_MESSAGE_PREFIX
from utilities.help_utils import ModuleHelp
from utilities.utilities import (
    Utilities,
    is_stampy_mentioned,
    stampy_is_author,
    get_guild_and_invite_role,
    get_question_id,
)
from utilities.serviceutils import ServiceMessage

log = get_logger()


@dataclass
class Response:
    """The response a module gives.
    Two types of response are possible:
        1. Text responses, with a string and a confidence rating, and
        2. Callback responses, with a (possibly async) function, args/kwargs for the function,
           and the *optimistic expected confidence of the function's response*
    Set `text` or `callback`, not both.

    For example, suppose the incoming message says "What is AIXI?"
    One module may spot that this is a question, and generate a quick joke as a text response:

        Response(text="https://www.google.com/search?q=AIXI", confidence=2)

    This means "This module suggests Stampy give the user a link to a google search for 'AIXI',
    but only with confidence 2/10, because that's a weak response"
    If no other module responds with confidence 2 or more, Stampy will give the google link response.

    If a module needs to respond with multiple Discord messages (e.g. for messages over 2000 characters
    that need manual splitting, or for asynchronous operations over multiple items like wiki edits), it
    can use a list, a generator, or another iterable:

        Response(text=["a", "b", "c"], confidence=9)

    Another module may spot that "What is AIXI?" is a question it may be able to actually answer well,
    but it doesn't know without slow/expensive operations that we don't want to do if we don't have to,
    like hitting a remote API or running a large language model. So it generates a callback response:

        Response(callback=self.search_alignment_forum_tags,
                 args=["AIXI"],
                 kwargs={'type'='exact_match'},
                 confidence=8
                )

    This means "This module has the potential for a confidence 8 response (in this case, if the
    Alignment Forum has a tag with the exact string the user asked about), but do check that there are
    no better options first, before we hit the Alignment Forum API.
    If another module responds with confidence 9 or 10, the callback function is never called,
    but if the callback response's given confidence is the highest of any response, we call

        await search_alignment_forum_tags("AIXI", type='exact_match')

    This function will return a Response object in exactly the same way.
    For example, if the search finds a hit:

        Response(text="AIXI is a mathematical formalism for a hypothetical (super)intelligence, "
                      "developed by Marcus Hutter.\n"
                      "See <https://www.alignmentforum.org/tag/aixi> for more",
                 confidence=8
                )

    Or if there's no match for the search:

        Response(text="I don't know, there's no alignment forum tag for that", confidence=1)

    Callback functions can also return callback responses, so the process can be recursive.
    Please do not do anything stupid with this.

    Picking confidence levels to give for callbacks is kind of subtle. You're effectively saying

    "What confidence of response would another module have to give, such that it would be not worth
    running this callback?". This will vary depending on: how good the response could be, how likely
    a good response is, and how slow/expensive the callback function is.
    """

    embed: Optional[discord.Embed] = None
    confidence: float = 0.0
    text: Union[str, Iterable[str]] = ""
    callback: Optional[Callable] = None
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)

    module: object = None

    why: str = ""

    def __bool__(self):
        return bool(self.text) or bool(self.callback) or bool(self.confidence)

    def __repr__(self) -> str:
        embed = self.embed
        confidence = self.confidence
        text = self.text
        callback = self.callback.__name__ if self.callback else None
        args = self.args
        kwargs = self.kwargs
        module = str(self.module)
        why = self.why
        return (
            "Response("
            + (f"{embed=} " if embed else "")
            + f"{confidence=} "
            + (f"{text=} " if text else "")
            + (f"{callback=} " if callback else "")
            + (f"{args=} " if args else "")
            + (f"{kwargs=} " if kwargs else "")
            + (f"{module=} " if module else "")
            + (f"{why=}" if why else "")
            + ")"
        )


class Module:
    """Informal Interface specification for modules
    These represent packets of functionality. For each message,
    we show it to each module and ask if it can process the message,
    then give it to the module that's most confident"""

    def __init__(self):
        self.utils = Utilities.get_instance()
        self.log = get_logger()
        self.re_replace = re.compile(r".*?({{.+?}})")
        module_docstring = inspect.getmodule(self).__doc__
        self.help = ModuleHelp.from_docstring(self.class_name, module_docstring)

    def process_message(self, message: ServiceMessage) -> Response:
        """Handle the message, return a string which is your response.
        This is an async function so it can interact with the Discord API if it needs to.
        If confidence is more than zero, and the message is empty, `processMessage` may be called
        `can_process_message` should contain only operations which can be executed safely even if
        another module reports a higher confidence and ends up being the one to respond.If your
        module is going to do something that only makes sense if it gets to respond, put that in
        `process_message` instead

        Rough Guide:
        0 -> "This message isn't meant for this module, I have no idea what to do with it"
        1 -> "I could give a generic reply if I have to, as a last resort"
        2 -> "I can give a slightly better than generic reply, if I have to. e.g. I realise this is a question
              but don't know what it's asking"
        3 -> "I can probably handle this message with ok results, but I'm a frivolous/joke module"
        4 ->
        5 -> "I can definitely handle this message with ok results, but probably other modules could too"
        6 -> "I can definitely handle this message with good results, but probably other modules could too"
        7 -> "This is a valid command specifically for this module, and the module is 'for fun' functionality"
        8 -> "This is a valid command specifically for this module, and the module is medium importance functionality"
        9 -> "This is a valid command specifically for this module, and the module is important functionality"
        10 -> "This is a valid command specifically for this module, and the module is critical functionality"

        Ties are broken in module priority order. You can also return a float if you really want
        """
        return Response()

    def process_message_from_stampy(self, message):
        """By default, messages posted by stampy himself are not sent to modules' `process_message`
        Use this method to do something whenever Stampy says anything
        This method should not return anything, and should not try to send messages unless you really know what you're doing
        """
        pass

    async def process_raw_reaction_event(self, event) -> Response:
        """event is a discord.RawReactionActionEvent object
        Use this to allow modules to handle adding and removing reactions on messages"""
        return Response()

    async def tick(self):
        """This function will be called all the time, whenever anything happens on the discord.
        Use it for things that need to happen regularly, but RATE LIMIT IT!
        ALWAYS call self.utils.rate_limit() first thing in the function, so it doesn't happen too much.
        For example:

        if self.utils.rate_limit("check youtube API", seconds=30):
            return"""
        pass

    def __str__(self):
        return "Base Module"

    @staticmethod
    def create_integration_test(
        test_message="",
        expected_response="",
        expected_regex=None,
        test_wait_time=0.5,
        minimum_allowed_similarity=1.0,
    ) -> IntegrationTest:
        return {
            "test_message": test_message,
            "expected_response": expected_response,
            "received_response": "NEVER RECEIVED A RESPONSE",
            "expected_regex": expected_regex,
            "test_wait_time": test_wait_time,
            "minimum_allowed_similarity": minimum_allowed_similarity,
            "result": None,
        }

    @staticmethod
    def clean_test_prefixes(message, prefix):
        text = message.clean_content
        prefix_number = get_question_id(message)
        prefix_with_number = prefix + str(prefix_number) + ": "
        if prefix_with_number == text[: len(prefix_with_number)]:
            return text[len(prefix_with_number) :]
        return text

    def is_at_me(self, message: ServiceMessage) -> Union[str, Literal[False]]:
        """
        Determine if the message is directed at Stampy
        If it's not, return False. If it is, strip away the
        name part and return the remainder of the message
        """
        text = message.clean_content
        if self.utils.test_mode:
            if stampy_is_author(message):
                if TEST_MESSAGE_PREFIX in message.clean_content:
                    text = "stampy " + self.clean_test_prefixes(
                        message, TEST_MESSAGE_PREFIX
                    )
        at_me = is_stampy_mentioned(message)
        re_at_me = re.compile(r"^@?[Ss]tampy\W? ")

        if (re_at_me.match(text) is not None) or re.search(r"^[sS][,:]? ", text):
            at_me = True
            text = text.partition(" ")[2]
        elif re.search(
            r",? @?[sS](tampy)?[.!?]?$", text
        ):  # name can also be at the end
            text = re.sub(
                r",? @?[sS](tampy)?(?P<punctuation>[.!?]*)$", r"\g<punctuation>", text
            )
            at_me = True

        if message.is_dm:
            # DMs are always at you
            at_me = True

        if Utilities.get_instance().client.user in message.mentions:
            # regular mentions are already covered above, this covers the case that someone reply @'s Stampy
            self.log.info(
                self.class_name, msg="Classified as 'at stampy' because of mention"
            )
            at_me = True

        if at_me:
            return text
        else:
            return False

    def get_guild_and_invite_role(self):
        return get_guild_and_invite_role()

    def dereference(self, string, who):
        """Dereference any template variables given in {{double curly brackets}}"""

        countdown = 30  # don't carry out more than this many lookups total. No infinite recursions
        while countdown >= 0:
            countdown -= 1

            # first handle the dummy/custom factoids
            string = string.replace("{{$who}}", who)  # who triggered this response?

            # $someone is a random person from the chat
            # only make 1 replace per iteration, so a message can have more than one person chosen
            string = string.replace(
                "{{$someone}}", random.choice(list(self.utils.people)), 1
            )

            if not self.re_replace.match(
                string
            ):  # If there are no more {{}} to sub, break out
                break

            tag = self.re_replace.match(string).group(1)
            key = tag[2:-2]  # strip the surrounding {{}}
            try:
                verb, value, by = self.db.getrandom(key)
                string = string.replace(tag, value, 1)
            except Exception:
                string = string.replace(tag, "{notfound:%s}" % key, 1)

        return string

    @property
    def class_name(self) -> str:
        """Name of the class inheriting from Module"""
        if self.__class__ is Module:
            return "BaseModule"
        return self.__class__.__name__


class IntegrationTest(TypedDict):
    """Integration test for testing Stampy modules"""

    test_message: str
    expected_response: str
    received_response: str
    expected_regex: Optional[str]
    test_wait_time: float
    minimum_allowed_similarity: float
    result: Literal["PASSED", "FAILED", None]
