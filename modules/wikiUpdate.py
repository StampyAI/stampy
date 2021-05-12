from modules.module import Module
import re

class WikiUpdate(Module):
    def __str__(self):
        return "Wiki Tag Update Module"

    def __init__(self):
        Module.__init__(self)
        self.command_not_a_question_re = re.compile(
            r"((Stampy )?[Tt]ag (that|this)( as)?|[Tt](hat|his) is|[Tt]hat'?s|[Tt](his|at) (question|comment) is) (not (a )?question)(,? [Ss]tampy)?"
        )
        self.command_for_rob_re = re.compile(
            r"((Stampy )?[Tt]ag (that|this)( as)?|[Tt](hat|his) is|([Tt]hat'?s)|[Tt](his|at) (question|comment) is) (for rob)(,? [Ss]tampy)?"
        )
        self.command_rejected = re.compile(
            r"(Stampy )?((([Tt]ag (that|this)( as)?|[Tt](hat|his) is|[Tt]hat'?s|[Tt](his|at) (question|comment) is) rejected)|reject (that|this))(,? [Ss]tampy)?"
        )
        self.command = None

# "Tag that as not a question", or "that's not question" etc
# "tag that as for rob", or "this question is for rob" etc
# "tag that as rejected" or "reject that"

    def can_process_message(self, message, client=None):
        """From the Module() Interface. Is this a message we can process?"""

        if re.match(self.command_not_a_question_re, message.clean_content):
            self.command = self.process_not_a_qestion
        elif re.match(self.command_for_rob_re, message.clean_content):
            self.command = self.process_for_rob
        elif re.match(self.command_rejected, message.clean_content):
            self.command = self.process_rejected
        else:
            self.command = None

        if self.command:
            return 8, ""

        return 0, ""

    async def process_message(self, message, client=None):
        """From the Module() Interface. Handle a reply posting request message"""
        if self.command:
            return await self.command(message)
        return 0, ""

    async def process_not_a_qestion(self, message):
        wiki_title = await self.get_wiki_title(message)
        if not wiki_title:
            return 6, "It is not clear what question you are referring to"

        self.utils.wiki.set_question_property(wiki_title, "notquestion", "Yes")
        return 8, "Processing not a question request for " + wiki_title

    async def process_for_rob(self, message):
        wiki_title = await self.get_wiki_title(message)
        if not wiki_title:
            return 6, "It is not clear what question you are referring to"

        self.utils.wiki.set_question_property(wiki_title, "forrob", "Yes")
        return 8, "Processing for rob request" + wiki_title

    async def process_rejected(self, message):
        wiki_title = await self.get_wiki_title(message)
        if not wiki_title:
            return 6, "It is not clear what question you are referring to"

        self.utils.wiki.set_question_property(wiki_title, "reviewed", "0")

        return 8, "Processing rejected request" + wiki_title

    async def get_wiki_title(self, message):
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
                    r"YouTube user (.*?)( just)? asked (a|this) question", reference_text
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
