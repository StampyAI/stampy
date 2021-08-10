import re
from modules.module import Module, Response


class WikiUpdate(Module):
    UNCLEAR_REQUEST_MESSAGE = "It is not clear what question you are referring to"

    def __str__(self):
        return "Wiki Tag Update Module"

    def __init__(self):
        Module.__init__(self)

        tag_this_as_regex = (
            r"(([Tt]ag|[Mm]ark) (that|this)( question| comment)?( as)?|"
            + r"[Tt]hat'?s|[Tt]h(is|at)( question| comment)? is)"
        )
        # command_dict contains all the commands, which regex triggers them
        # and which function [signature async (*f)(self, message)] should be triggered when the regex matches
        # for simple commands that change a single property, get_simple_property_change_partial_function can be used
        # for more complicated commands, command should be a reference to a function or lambda function
        # [if a command is particularly important put it at the start of the dict, since matches are evaluated in order]
        self.command_dict = {
            "Not A Question": {
                "re": re.compile(tag_this_as_regex + r"(n'?t| '?not) (a )?question'?"),
                "args": ["notquestion", "Yes"],
            },
            "For Rob": {
                "re": re.compile(tag_this_as_regex + r" '?for ?rob'?"),
                "args": ["forrob", "Yes"],
            },
            "Rejected": {
                "re": re.compile(tag_this_as_regex + r" '?rejected'?|reject (that|this)"),
                "args": ["reviewed", "0"],
            },
            "Out of Scope": {
                "re": re.compile(tag_this_as_regex + r" '?(out of scope|not[- ]ai)'?"),
                "args": ["outofscope", "Yes"],
            },
            "Canonical": {
                "re": re.compile(tag_this_as_regex + r" '?canonical'?"),
                "args": ["canonical", "Yes"],
            },
            "Technical": {
                "re": re.compile(tag_this_as_regex + r" '?(technical|difficult)'?"),
                "args": ["difficulty", "Technical"],
            },
            "Easy": {
                "re": re.compile(tag_this_as_regex + r" '?(easy|101)'?"),
                "args": ["difficulty", "Easy"],
            },
        }

    async def process_simple_property_change(self, message, property_name, new_value):
        """
        Changes just a single property from the referenced question (or the last question stampy posted).
        """
        wiki_title = await self.get_wiki_title(message)
        if not wiki_title:
            return Response(
                confidence=5,
                text="It is not clear what question you are referring to",
                why="The message was directed at stampy and matched the regex to change property"
                + property_name
                + ". But the replied message was not a YT question from stampy."
                + "Or for some other reason the appropriate wiki page to change could not be found.",
            )

        self.utils.wiki.set_question_property(wiki_title, property_name, new_value)

        return Response(
            confidence=8,
            text=f"Ok, setting {property_name} to {new_value} on '{wiki_title}'",
            why="The message was directed at stampy and matched the regex to change property"
            + property_name
            + ". And so stampy went ahead and made that change, and reported to the chat that he did so.",
        )

    async def get_wiki_title(self, message):
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

    def process_message(self, message, client=None):
        text = self.is_at_me(message)
        if not text:
            return Response(confidence=0, text="We were not directly addressed", module=self)

        for command in self.command_dict.values():
            if command["re"].match(text):
                return Response(
                    confidence=8,
                    callback=self.process_simple_property_change,
                    args=[message] + command["args"],
                    module=self,
                )

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                question="mark this question as rejected",
                expected_response=self.UNCLEAR_REQUEST_MESSAGE,
            )  # TODO create more meaningful test here
        ]
