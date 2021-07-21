import re
import discord
from utilities import Utilities
from dataclasses import dataclass, field
from typing import Callable


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

    confidence: float = 0.0

    text: str = ""

    callback: Callable = None
    args: list = field(default_factory=list)
    kwargs: dict = field(default_factory=dict)

    module: object = None

    why: str = ""

    def __bool__(self):
        return bool(self.text) or bool(self.callback) or bool(self.confidence)


class Module(object):
    utils = None

    def __init__(self):
        self.utils = Utilities.get_instance()
        self.guild = self.utils.client.guilds[0]

    """Informal Interface specification for modules
    These represent packets of functionality. For each message,
    we show it to each module and ask if it can process the message,
    then give it to the module that's most confident"""

    def can_process_message(self, message, client=None):
        """Look at the message and decide if you want to handle it
        Return a pair of values: (confidence rating out of 10, message)
        Including a response message is optional, use an empty string to just indicate a confidence
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
        # By default, we have 0 confidence that we can answer this, and our response is ""
        return Response()

    def process_message(self, message, client=None):
        """Handle the message, return a string which is your response.
        This is an async function so it can interact with the Discord API if it needs to"""
        return Response()

    async def process_reaction_event(self, reaction, user, event_type="REACTION_ADD", client=None):
        """event_type can be 'REACTION_ADD' or 'REACTION_REMOVE'
        Use this to allow modules to handle adding and removing reactions on messages"""
        return Response()

    async def process_raw_reaction_event(self, event, client=None):
        """event is a discord.RawReactionActionEvent object
        Use this to allow modules to handle adding and removing reactions on messages"""
        return Response()

    def __str__(self):
        return "Dummy Module"

    @staticmethod
    def is_at_me(message):
        """
        Determine if the message is directed at Stampy
        If it's not, return False. If it is, strip away the
        name part and return the remainder of the message
        """

        text = message.clean_content
        at_me = False
        re_at_me = re.compile(r"^@?[Ss]tampy\W? ")
        text, subs = re.subn("<@!?736241264856662038>|<@&737709107066306611>", "Stampy", text)
        if subs:
            at_me = True

        if (re_at_me.match(text) is not None) or re.search(r"^[sS][,:]? ", text):
            at_me = True
            text = text.partition(" ")[2]
        elif re.search(",? @?[sS](tampy)?[.!?]?$", text):  # name can also be at the end
            text = re.sub(",? @?[sS](tampy)?$", "", text)
            at_me = True
            # print("X At me because it ends with stampy")

        if type(message.channel) == discord.DMChannel:
            # DMs are always at you
            at_me = True

        if Utilities.get_instance().client.user in message.mentions:
            # regular mentions are already covered above, this covers the case that someone reply @'s Stampy
            print("X At me because of mention")
            at_me = True

        if at_me:
            return text
        else:
            return False
