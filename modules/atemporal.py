from modules.module import Module, Response
from datefinder import find_dates
import re
import pytz
from datetime import datetime, timedelta
import discord


class AtemporalModule(Module):
    timezones = []

    def __init__(self):
        Module.__init__(self)
        self.re_tz = re.compile(r"(UK)")
        self.add_tz()

    def __str__(self):
        return "A module outside of time"

    def process_message(self, message, client=None):
        text = message.clean_content
        likely_dates = find_dates(text)
        for date in likely_dates:
            # if it's just a date, we don't really care
            if date.hour > 0:
                tz = self.get_timezone(text)
                source_date = tz.localize(date)
                utc_date = source_date.astimezone(pytz.utc)
                embed = discord.Embed(title="Friendly Neighborhood Timezones:",
                                      timestamp=utc_date)
                #embed = discord.Embed(title="Friendly Neighborhood Timezones:",
                #                      timestamp=utc_date)
                embed = discord.Embed()
                for tz in self.timezones:
                    embed.add_field(name=tz.zone,
                                    value=source_date.astimezone(tz).strftime("%m/%d/%Y %I:%M %p"),
                                    inline=False)

                response = Response(confidence=4,
                                    embed=embed,
                                    why=f"{message.author.name} "
                                        f"asked mentioned a time, so I converted it into a local time embed")
                return response

    def add_tz(self):
        self.timezones.append(pytz.timezone("Australia/Sydney"))
        self.timezones.append(pytz.timezone("Europe/Berlin"))
        self.timezones.append(pytz.timezone("US/Central"))
        self.timezones.append(pytz.timezone("US/Pacific"))
        return

    def get_timezone(self, text):
        timezone_result = pytz.timezone("Europe/London")
        if self.re_tz.search(text):
            tz = self.re_tz.search(text).group(0)
            if tz == "UK":
                timezone_result = pytz.timezone("Europe/London")
        return timezone_result
