from modules.module import Module, Response
import re
from functools import partial
from utilities import Utilities


class WikiUpdate(Module):
    def __str__(self):
        return "Wiki Tag Update Module"

    def __init__(self):
        Module.__init__(self)

        tag_this_as_regex = r"(([Tt]ag|[Mm]ark) (that|this)( question| comment)?( as)?|[Tt]hat'?s|[Tt]h(is|at)( question| comment)? is)"
        # command_dict contains all the commands, which regex triggers them
        # and which function [signature async (*f)(self, message)] should be triggered when the regex matches
        # for simple commands that change a single property, get_simple_property_change_partial_function can be used
        # for more complicated commands, command should be a reference to a function or lambda function
        # [if a command is particularly important put it at the start of the dict, since matches are evaluated in order]
        # FIXME: for some reason, an partial asyncronous class function is not detected as asyncronous by iscoroutinefunction
        # FIXME: so the values of command can either be a partial class function or asynchronous partial fucntion, but not both
        # FIXME: a workaround does exist, where one defines a function outside of the class, but gives it a parameter fake_self
        # FIXME: hopefully in a future release of Python this issue with iscoroutinefunction is fixed
        self.command_dict = {
            "Not A Question": {
                "re": re.compile(tag_this_as_regex + r"(n'?t| '?not) (a )?question'?"),
                "command": self.get_simple_property_change_partial_function("notquestion", "Yes"),
            },
            "For Rob": {
                "re": re.compile(tag_this_as_regex + r" '?for ?rob'?"),
                "command": self.get_simple_property_change_partial_function("forrob", "Yes"),
            },
            "Rejected": {
                "re": re.compile(
                    tag_this_as_regex
                    + r" '?rejected'?|reject (that|this)"  # is it confusing that |option2 matches option2 alone, and not tag_this_as_regex+option2?
                ),
                "command": self.get_simple_property_change_partial_function("reviewed", "0"),
            },
            "Out of Scope": {
                "re": re.compile(tag_this_as_regex + r" '?(out of scope|not[- ]ai)'?"),
                "command": self.get_simple_property_change_partial_function("outofscope", "Yes"),
            },
            "Cannonical": {
                "re": re.compile(tag_this_as_regex + r" '?canonical'?"),
                "command": self.get_simple_property_change_partial_function("canonical", "Yes"),
            },
            "Technical": {
                "re": re.compile(tag_this_as_regex + r" '?(technical|difficult)'?"),
                "command": self.get_simple_property_change_partial_function("difficulty", "Technical"),
            },
            "Easy": {
                "re": re.compile(tag_this_as_regex + r" '?(easy|101)'?"),
                "command": self.get_simple_property_change_partial_function("difficulty", "Easy"),
            },
        }

    def process_message(self, message, client=None):
        text = self.is_at_me(message)
        if not text:
            return Response(confidence=0, text="We were not directly adressed", module=self)

        for v in self.command_dict.values():
            if v["re"].match(text):
                return Response(confidence=8, callback=v["command"], args=[message], module=self)

    def get_simple_property_change_partial_function(self, property_name, new_value):
        """returns a function that when executed given a specific message performs the appropriate property change"""
        return partial(
            process_simple_property_change,
            property_name=property_name,
            new_value=new_value,
        )


# Defined out of class by necesity
async def process_simple_property_change(message, property_name, new_value):
    """Changes just a single property from the referenced question (or the last question stampy posted)."""
    wiki_title = await get_wiki_title(message)
    if not wiki_title:
        return Response(
            confidence=5,
            text="It is not clear what question you are referring to",
            why="The message was directed at stampy and matched the regex to change property"
            + property_name
            + ". But the replied message was not a YT question from stampy."
            + "Or for some other reason the appropriate wiki page to change could not be found.",
        )

    Utilities.get_instance().wiki.set_question_property(wiki_title, property_name, new_value)

    return Response(
        confidence=8,
        text=f"Ok, setting {property_name} to {new_value} on '{wiki_title}",
        why="The message was directed at stampy and matched the regex to change property"
        + property_name
        + ". And so stampy went ahead and made that change, and reported to the chat that he did so.",
    )


async def get_wiki_title(message):
    """parses the message reference to get the wiki title of the referenced question"""
    if message.reference:
        # if this message is a reply
        reference = await message.channel.fetch_message(message.reference.message_id)
        reference_text = reference.clean_content
        question_url = reference_text.split("\n")[-1].strip("<> \n")

        question_user = "Unknown User"
        if reference_text:
            match = re.match(
                r"YouTube user (.*?)( just)? asked (a|this) question",
                reference_text,
            )
        if not match:
            return None
        question_user = match.group(1)  # YouTube user (.*) asked this question
    else:
        if not Utilities.get_instance().latest_question_posted:
            return None

        question_url = Utilities.get_instance().latest_question_posted["url"]
        question_user = Utilities.get_instance().latest_question_posted["username"]

    video_url, comment_id = question_url.split("&lc=")
    video_titles = Utilities.get_instance().get_title(video_url)
    if not video_titles:
        # this should actually only happen in dev
        video_titles = ["Video Title Unknown", "Video Title Unknown"]

    return f"{question_user}'s question on {video_titles[0]} id:{comment_id}"
