import re
import discord
from utilities import Utilities


class Module(object):
    utils = None

    def __init__(self):
        self.utils = Utilities.get_instance()

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
        return 0, ""

    async def process_message(self, message, client=None):
        """Handle the message, return a string which is your response.
        This is an async function so it can interact with the Discord API if it needs to"""
        return 0, ""

    async def process_reaction_event(
        self, reaction, user, event_type="REACTION_ADD", client=None
    ):
        """event_type can be 'REACTION_ADD' or 'REACTION_REMOVE'
        Use this to allow modules to handle adding and removing reactions on messages"""
        return 0, ""

    async def process_raw_reaction_event(self, event, client=None):
        """event is a discord.RawReactionActionEvent object
        Use this to allow modules to handle adding and removing reactions on messages"""
        return 0, ""

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
        text, subs = re.subn(
            "<@!?736241264856662038>|<@&737709107066306611>", "Stampy", text
        )
        if subs:
            at_me = True

        if (re_at_me.match(text) is not None) or re.search(r"^[sS][,:]? ", text):
            at_me = True
            print("X At me because re_at_me matched or starting with [sS][,:]? ")
            text = text.partition(" ")[2]
        elif re.search(",? @?[sS](tampy)?[.!?]?$", text):  # name can also be at the end
            text = re.sub(",? @?[sS](tampy)?$", "", text)
            at_me = True
            print("X At me because it ends with stampy")

        if type(message.channel) == discord.DMChannel:
            print("X At me because DM")
            at_me = True  # DMs are always at you

        if at_me:
            return text
        else:
            print("Message is Not At Me")
            return False
