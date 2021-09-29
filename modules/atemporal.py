from modules.module import Module, Response
from datefinder import find_dates
import pytz
from datetime import datetime, timedelta, timezone
import discord


class AtemporalModule(Module):
    def __init__(self):
        Module.__init__(self)
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
            response = Response(
                confidence=4,
                text=f"Friendly Neighborhood Timezone: <t:{int(source_date.timestamp())}:F>",
                why=f"{message.author.name} "
                f" mentioned a time, so I converted it into a local time embed",
            )
            return response

    def get_timezone(self, author):
        factoid_str = "{0}'s timezone".format(author)
        factoid_str = "{{" + factoid_str + "}}"
        user_tz = self.utils.modules_dict["Factoids"].dereference(factoid_str)
        try:
            timezone_result = pytz.timezone(user_tz)
        except Exception:  # I don't know what kind of exception this throws when user_tz is None?
            timezone_result = pytz.timezone("Europe/London")
        return timezone_result
