from modules.module import Module
import re
from functools import partial


class WikiUpdate(Module):
    def __str__(self):
        return "Wiki Tag Update Module"

    def __init__(self):
        Module.__init__(self)

        # command_dict contains all the commands, which regex triggers them
        # and which function [signature (*f)(self, message)] should be triggered when the regex matches
        # for simple commands that change a single property, get_simple_property_change_partial_function can be used
        # for more complicated commands, command should be a reference to a function or lambda function
        # [if a command is particularly important put it at the start of the dict, since matches are evaluated in order]
        self.command_dict = {
            "Not A Question": {
                "re": re.compile(
                    r"((Stampy )?[Tt]ag (that|this)( as)?|[Tt](hat|his) is|[Tt]hat'?s|[Tt](his|at) (question|comment) is) (not (a )?question)(,? [Ss]tampy)?"
                ),
                "command": self.get_simple_property_change_partial_function(
                    "notquestion", "Yes"
                ),
            },
            "For Rob": {
                "re": re.compile(
                    r"((Stampy )?[Tt]ag (that|this)( as)?|[Tt](hat|his) is|([Tt]hat'?s)|[Tt](his|at) (question|comment) is) (for rob)(,? [Ss]tampy)?"
                ),
                "command": self.get_simple_property_change_partial_function(
                    "forrob", "Yes"
                ),
            },
            "Rejected": {
                "re": re.compile(
                    r"(Stampy )?((([Tt]ag (that|this)( as)?|[Tt](hat|his) is|[Tt]hat'?s|[Tt](his|at) (question|comment) is) rejected)|reject (that|this))(,? [Ss]tampy)?"
                ),
                "command": self.get_simple_property_change_partial_function(
                    "reviewed", "0"
                ),
            },
        }

        self.command = None

    def can_process_message(self, message, client=None):
        """From the Module() Interface. Is this a message we can process?"""

        for k, v in self.command_dict.items():
            if v["re"].match(message.clean_content):
                self.command = v["command"]
                break

        if self.command:
            return 8, ""

        return 0, ""

    async def process_message(self, message, client=None):
        """From the Module() Interface. Handle a reply posting request message"""
        if self.command:
            return await self.command(message)
        return 0, ""

    def get_simple_property_change_partial_function(self, property_name, new_value):
        """returns a function that when executed given a specific message performs the appropriate property change"""
        return partial(
            self.process_simple_property_change,
            property_name=property_name,
            new_value=new_value,
        )

    async def process_simple_property_change(self, message, property_name, new_value):
        """Changes just a single property from the referenced question (or the last question stampy posted)"""
        wiki_title = await self.get_wiki_title(message)
        if not wiki_title:
            return 6, "It is not clear what question you are referring to"

        self.utils.wiki.set_question_property(wiki_title, property_name, new_value)

        return (
            8,
            "Processing "
            + property_name
            + "="
            + new_value
            + " request on "
            + wiki_title,
        )

    async def get_wiki_title(self, message):
        """parses the message reference to get the wiki title of the referenced question"""
        if message.reference:
            # if this message is a reply
            reference = await message.channel.fetch_message(
                message.reference.message_id
            )
            reference_text = reference.clean_content
            question_url = reference_text.split("\n")[-1].strip("<> \n")

            question_user = "Unknown User"
            if reference_text:
                match = re.match(
                    r"YouTube user (.*?)( just)? asked (a|this) question",
                    reference_text,
                )
            if match:
                question_user = match.group(1)  # YouTube user (.*) asked this question
        else:
            if not self.utils.latest_question_posted:
                return None

            question_url = self.utils.latest_question_posted["url"]
            question_user = self.utils.latest_question_posted["username"]

        video_url, comment_id = question_url.split("&lc=")
        video_titles = self.utils.get_title(video_url)
        if not video_titles:
            # this should actually only happen in dev
            video_titles = ["Video Title Unknown", "Video Title Unknown"]

        return f"{question_user}'s question on {video_titles[0]} id:{comment_id}"
