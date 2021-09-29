from modules.module import Module, Response
from datefinder import find_dates
import pytz
from datetime import datetime, timedelta, timezone
import discord
import re


class AtemporalModule(Module):

    def __init__(self):
        Module.__init__(self)
        self.re_iso8601 = re.compile(
            r'([\+-]?\d{4}(?!\d{2}\b))((-?)((0[1-9]|1[0-2])(\3([12]\d|0[1-9]|3[01]))?|W([0-4]\d|5[0-2])(-?[1-7])?|(00[1-9]|0[1-9]\d|[12]\d{2}|3([0-5]\d|6[1-6])))([T\s]((([01]\d|2[0-3])((:?)[0-5]\d)?|24\:?00)([\.,]\d+(?!:))?)?(\17[0-5]\d([\.,]\d+)?)?([zZ]|([\+-])([01]\d|2[0-3]):?([0-5]\d)?)?)?)?'
        )
        return

    def __str__(self):
        return "A module outside of time"

    def process_message(self, message, client=None):
        text = message.clean_content
        likely_dates = find_dates(text)
        author = message.author.name

        for date in likely_dates:
            tz = self.get_timezone(author)
            source_date = tz.localize(date)
            potential_response = Response(
                confidence=8,
                text=f"Friendly Neighborhood Time: <t:{int(source_date.timestamp())}:F>",
                why=f"{message.author.name} "
                    f" mentioned a time, so I converted it into a localize timestamp",
            )
            if (("<@&892821821739634709>" in message.content and "office hours" in message.content)
                    or self.re_iso8601.search(text) is not None) and date.hour > 0:
                return potential_response

    def get_timezone(self, author):
        factoid_str = "{0}'s timezone".format(author)
        factoid_str = "{{" + factoid_str + "}}"
        user_tz = self.utils.modules_dict["Factoids"].dereference(factoid_str)
        try:
            timezone_result = pytz.timezone(user_tz)
        except Exception:  # I don't know what kind of exception this throws when user_tz is None?
            timezone_result = pytz.timezone("Europe/London")
        return timezone_result
