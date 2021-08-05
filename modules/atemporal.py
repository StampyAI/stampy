from modules.module import Module, Response
from datefinder import find_dates
import re
import pytz
import discord


class AtemporalModule(Module):
    pst = pytz.timezone("US/Pacific")

    def __init__(self):
        Module.__init__(self)
        self.re_tz = re.compile(r"(UK)")

    def __str__(self):
        return "A module outside of time"

    def can_process_message(self, message, client=None):
        text = message.clean_content
        likely_dates = find_dates(text)
        for date in likely_dates:
            # if it's just a date, we don't really care
            if date.hour > 0:
                tz = self.get_timezone(text)
                source_date = tz.localize(date)
                response = "That's {0} in real people time!".format(
                    source_date.astimezone(self.pst).strftime("%m/%d/%Y %I:%M %p")
                )
                return 4, response

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

    def get_timezone(self, text):
        if self.re_tz.search(text):
            tz = self.re_tz.search(text).group(0)
            if tz == "UK":
                return pytz.timezone("Europe/London")