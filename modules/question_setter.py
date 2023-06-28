"""
Changing status (in future perhaps also other attributes) of questions in Coda.
**Permissions:**
- All server members can contribute to AI Safety Questions and ask for feedback.
- Only `@bot dev`s, `@editor`s, and `@reviewer`s can change question status by other commands.
- Only `@reviewers` can change status of questions to and from  `Live on site` (including accepting review requests).

Review request, @reviewer, @feedback, @feedback-sketch
Request a review on an answer you wrote/edited
On Rob Miles's Discord server, an `@editor` can ask other `@editor`s and `@reviewer`s to give them feedback or review their changes to AI Safety Info questions. You just put one or more links to appropriate GDocs and mention one of: `@reviewer`, `@feedback`, or `@feedback-sketch`. Stampy will spot this and update their statuses in the coda table with answers appropriately.
`@reviewer <gdoc-link(s)>` - change status to `In review`
`@feedback <gdoc-link(s)>` - change status to `In progress`
`@feedback-sketch <gdoc-link(s)>` - change status to `Bulletpoint sketch`

Review acceptance, accepted, approved, lgtm
Accept a review, setting question status to `Live on Site`
A `@reviewer` can **accept** a question by (1) responding to a review request with a keyword (listed below) or (2) posting one or more valid links to GDocs with AI Safety Info questions with a keyword. Stampy then reacts by changing status to `Live on site`.
The keywords are (case-insensitive):
- accepted
- approved
- lgtm
  - stands for "looks good to me"


Mark for deletion or as duplicate, del, dup, deletion, duplicate
Change status of questions to `Marked for deletion` or `Duplicate`
`s, del <gdoc-link(s)>` - change status to `Marked for deletion`
`s, dup <gdoc-link(s)>` - change status to `Duplicate`

Set question status, Status
Change status of a question
`s, <set/change> <status/to/status to> <status>` - change status of the last question
`s, <set/change> <status/to/status to> <status> <gdoc-link(s)>`
`s, <set/change> <status/to/status to> <status> question <question-title>` - change status of a question fuzzily matching that title

Editing tags or alternate phrasings, Tags, Alternate phrasings, Altphr
Add a tag or an alternate phrasing to a question (specified by title, GDocLink, or the last one)
`s, <add/add tag> <tag-name> <gdoc-link(s)/question-title>` - specified by gdoc-links or question title (doesn't matter whether you put `<tag-name>` or `<gdoc-links/question-title>` first)
`s, <tag/add tag> <tag-name>` - if you don't specify the question, Stampy assumes you refer to the last one
`s, <delete/del/remove/rm> <tag-name> <gdoc-links/question-title>` - removing tags
`s, clear tags <gdoc-links/question-title>` - clear all tags on a question
`s, <altphr> "<alternate-phrasing>" <gdoc-link/question-title>` - you must put the alternate phrasing in double quotes and can do it only on one question at a time
`s <delete/del/remove/rm> <alternate phrasing/alt> "<alternate-phrasing>" <gdoc-link/question-title>` - analogously
`s, clear altphr` - here, on last question
"""
from __future__ import annotations

import re
from typing import Callable, Literal, Optional, Union, cast

from api.coda import CodaAPI
from api.utilities.coda_utils import QuestionRow, QuestionStatus
from config import ENVIRONMENT_TYPE, coda_api_token
from modules.module import IntegrationTest, Module, Response
from utilities.discordutils import DiscordChannel
from utilities.serviceutils import ServiceMessage
from utilities.utilities import (
    has_permissions,
    is_from_reviewer,
    pformat_to_codeblock,
    is_in_testing_mode,
)

if coda_api_token is not None:
    from utilities.question_query_utils import (
        QuestionSpecQuery,
        parse_alt_phr,
        parse_gdoc_links,
        parse_question_spec_query,
        parse_tag,
    )


GDocLinks = list[str]
MsgRefId = str
ReviewStatus = Literal["In review", "Bulletpoint sketch", "In progress"]
MarkingStatus = Literal["Marked for deletion", "Duplicate"]
EditAction = Literal["add", "remove", "clear"]


class QuestionSetter(Module):
    """Module for editing questions in [coda](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a)."""

    @staticmethod
    def is_available() -> bool:
        return coda_api_token is not None and not is_in_testing_mode()

    def __init__(self) -> None:
        if not self.is_available():
            exc_msg = f"Module {self.class_name} is not available."
            if coda_api_token is None:
                exc_msg += " CODA_API_TOKEN is not set in `.env`."
            if is_in_testing_mode():
                exc_msg += " Stampy is in testing mode right now."
            raise Exception(exc_msg)

        super().__init__()
        self.coda_api = CodaAPI.get_instance()

        self.msg_id2gdoc_links: dict[str, list[str]] = {}

        # tag
        self.re_add_tag = re.compile(r"(add\s)?tag", re.I)
        self.re_remove_tag = re.compile(r"(delete|del|remove|rm)\stag", re.I)

        # altphr
        alt_phr_pat = "(alt|alternate|alt phrasing|alternate phrasing|alias)"
        self.re_add_alt_phr = re.compile(r"(add )?" + alt_phr_pat, re.I)
        self.re_remove_alt_phr = re.compile(
            r"(delete|del|remove|rm) " + alt_phr_pat, re.I
        )

        # status
        status_pat = "|".join(self.coda_api.status_shorthand_dict)
        self.re_status = re.compile(
            rf"(?:set|change) (?:status|to|status to) ({status_pat})", re.I
        )

    async def find_gdoc_links_in_msg(
        self, channel: DiscordChannel, msg_ref_id: str
    ) -> None:
        """Find GDoc links in message, which is missing from Stampy's cache."""

        self.log.info(
            self.class_name,
            msg="Looking for GDoc links in message in channel",
            msg_ref_id=msg_ref_id,
            channel=channel,
        )

        async for msg in channel.history(limit=2000):
            if str(msg.id) == msg_ref_id:
                if gdoc_links := parse_gdoc_links(msg.clean_content):
                    self.msg_id2gdoc_links[str(msg.id)] = gdoc_links
                    log_msg = f"Found {len(gdoc_links)} in message with ID"
                else:
                    log_msg = "Found no GDoc links in message with ID"
                self.log.info(
                    self.class_name,
                    msg=log_msg,
                    gdoc_links=gdoc_links,
                    msg_ref_id=msg_ref_id,
                    channel=channel,
                )
                return
        self.log.info(
            self.class_name,
            msg="Couldn't find a message with ID in the channel",
            msg_ref_id=msg_ref_id,
            channel=channel,
        )

    #########################################
    # Core: processing and posting messages #
    #########################################

    def process_message(self, message: ServiceMessage) -> Response:
        # review request and approval
        if response := self.parse_review_request(message):
            return response
        if response := self.parse_question_approval(message):
            return response

        if not (text := self.is_at_me(message)):
            return Response()

        # setting question status
        if response := self.parse_mark_question_del_dup(text, message):
            return response
        if response := self.parse_set_question_status(text, message):
            return response

        # tagging
        if response := self.parse_edit_tag(text, message):
            return response

        # alternate phrasings
        if response := self.parse_edit_altphr(text, message):
            return response

        # even if message is not `at me`, it may contain GDoc links
        if gdoc_links := parse_gdoc_links(text):
            self.msg_id2gdoc_links[str(message.id)] = gdoc_links

        return Response()

    ######################
    #   Review request   #
    ######################

    def parse_review_request(self, message: ServiceMessage) -> Optional[Response]:
        """Is this message a review request with a link or many links do GDoc?
        If it is, return the list of parsed GDoc links and a new status
        to set these questions to.
        If it isn't, return `None`.
        """
        text = message.clean_content

        # get new status for questions
        if "@reviewer" in text:
            status = "In review"
        elif "@feedback-sketch" in text:
            status = "Bulletpoint sketch"
        elif "@feedback" in text:
            status = "In progress"
        else:  # if neither of these three roles is mentioned, this is not a review request
            return

        # try parsing gdoc links and questions that have these gdoc links
        # if you fail, assume this is not a review request
        if not (gdoc_links := parse_gdoc_links(text)):
            return
        self.msg_id2gdoc_links[message.id] = gdoc_links

        return Response(
            confidence=10,
            callback=self.cb_review_request,
            args=[gdoc_links, status, message],
        )

    async def cb_review_request(
        self, gdoc_links: list[str], status: ReviewStatus, message: ServiceMessage
    ) -> Response:
        """Change status of questions for which an editor requested review or feedback."""
        questions = self.coda_api.get_questions_by_gdoc_links(gdoc_links)
        if not questions:
            return Response(
                confidence=10,
                text="These links don't seem to lead to any AI Safety Info questions",
                why="I queried my database for these GDoc links and none matched any question",
            )

        msg = (
            f"Thanks, <@{message.author}>!\nI'll update "
            + ("its" if len(questions) == 1 else "their")
            + f" status to `{status}`"
        )

        await message.channel.send(msg)

        n_already_los = 0

        for q in questions:
            if q["status"] == "Live on site" and not is_from_reviewer(message):
                n_already_los += 1
                msg = f"`\"{q['title']}\"` is already `Live on site`."
            else:
                self.coda_api.update_question_status(q, status)
                msg = f"`\"{q['title']}\"` is now `{status}`"
            await message.channel.send(msg)

        n_updated = len(questions) - n_already_los

        if n_updated == 0:
            msg = "I didn't update any questions."
        elif n_updated == 1:
            msg = "I updated 1 question."
        else:
            msg = f"I updated {n_updated} questions."

        if n_already_los == 1:
            msg += " One question was already `Live on site`."
        elif n_already_los:
            msg += f" {n_already_los} questions were already `Live on site` (only reviewers can modify questions that are `Live on site`.)"

        return Response(
            confidence=10,
            text=msg,
            why=f"{message.author.display_name} did something useful and I wanted coda to reflect that.",
        )

    #########################
    #   Question approval   #
    #########################

    def parse_question_approval(self, message: ServiceMessage) -> Optional[Response]:
        """Is this a reviewer approving a question?
        If it is, return GDoc links to the questions being accepted
        or the ID of the original message that contains them.
        """
        text = message.clean_content
        if not any(s in text.lower() for s in ("approved", "accepted", "lgtm")):
            return
        if gdoc_links := parse_gdoc_links(text):
            return Response(
                confidence=10,
                callback=self.cb_question_approval,
                args=[gdoc_links, message],
            )

        if not (msg_ref := message.reference):
            return
        if not (msg_ref_id := getattr(msg_ref, "id", None)):
            return

        # if msg_ref_id is missing, then it will need to be retrieved
        msg_ref_id = str(msg_ref_id)
        if msg_ref_id in self.msg_id2gdoc_links:
            gdoc_links = self.msg_id2gdoc_links[msg_ref_id]
            parsed = gdoc_links
        else:
            parsed = msg_ref_id
        return Response(
            confidence=10,
            callback=self.cb_question_approval,
            args=[parsed, message],
        )

    async def cb_question_approval(
        self, parsed: Union[GDocLinks, MsgRefId], message: ServiceMessage
    ) -> Response:
        """Obtain GDoc links to approved questions and change their status in coda
        to `Live on site`.
        """
        if not is_from_reviewer(message):
            return Response(
                confidence=10,
                text=f"You're not a reviewer, <@{message.author}> -_-",
                why="Only, reviewers can accept questions",
            )

        if isinstance(parsed, list):  # is GDocLinks (list of strings)
            gdoc_links = parsed
        else:  # is MsgRefId (string)
            msg_ref_id = parsed
            assert isinstance(message.channel, DiscordChannel)
            await self.find_gdoc_links_in_msg(message.channel, msg_ref_id)
            gdoc_links = self.msg_id2gdoc_links.get(msg_ref_id, [])

        if not gdoc_links:
            return Response()

        questions = self.coda_api.get_questions_by_gdoc_links(gdoc_links)

        if not questions:
            return Response(
                confidence=10,
                text="These links don't seem to lead to any AI Safety Info questions",
                why="I queried my database for these GDoc links and none matched any question",
            )

        await message.channel.send(f"Approved by <@{message.author}>!")

        n_new_los = 0

        for q in questions:
            if q["status"] == "Live on site":
                await message.channel.send(
                    f"`\"{q['title']}\"` is already `Live on site`"
                )
            else:
                self.coda_api.update_question_status(q, "Live on site")
                n_new_los += 1
                await message.channel.send(f"`\"{q['title']}\"` goes `Live on site`!")

        if n_new_los == 0:
            msg = "No new `Live on site` questions."
        elif n_new_los == 1:
            msg = "One more question `Live on site`!"
        else:
            msg = f"{n_new_los} more questions `Live on site`!"
        return Response(
            confidence=10,
            text=msg,
            why=f"I set {n_new_los} questions to `Live on site` because {message.author} approved them.",
        )

    #######################################################
    #   Adding/removing tags and alternative phrasings    #
    #######################################################

    def parse_edit_tag(self, text: str, message: ServiceMessage) -> Optional[Response]:
        if self.re_add_tag.match(text):
            edit_action: EditAction = "add"
        elif self.re_remove_tag.match(text):
            edit_action = "remove"
        elif text.startswith("clear tags"):
            edit_action = "clear"
        else:
            return

        if edit_action == "clear":
            tag = None
        elif not (tag := parse_tag(text)):
            return

        query = parse_question_spec_query(text, return_last_by_default=True)
        return Response(
            confidence=10,
            callback=self.cb_edit_tag_or_altphr,
            args=[query, tag, message, edit_action, "tag"],
        )

    def parse_edit_altphr(
        self, text: str, message: ServiceMessage
    ) -> Optional[Response]:
        if self.re_add_alt_phr.match(text):
            edit_action: EditAction = "add"
        elif self.re_remove_alt_phr.match(text):
            edit_action = "remove"
        elif text.startswith("clear alt"):
            edit_action = "clear"
        else:
            return

        if edit_action == "clear":
            alt_phr = None
        elif not (alt_phr := parse_alt_phr(text)):
            return

        query = parse_question_spec_query(text, return_last_by_default=True)
        return Response(
            confidence=10,
            callback=self.cb_edit_tag_or_altphr,
            args=[query, alt_phr, message, edit_action, "alternate phrasing"],
        )

    async def cb_edit_tag_or_altphr(
        self,
        query: QuestionSpecQuery,
        val: Optional[str],  # tag or altphr (None only if edit_action == "clear")
        message: ServiceMessage,
        edit_action: EditAction,
        tag_or_altphr: Literal["tag", "alternate phrasing"],
    ) -> Response:
        if not has_permissions(message.author):
            return Response(
                confidence=10,
                text=f"You don't have permissions required to edit {tag_or_altphr}s <@{message.author}>",
                why=f"{message.author.display_name} does not have permissions edit {tag_or_altphr}s on questions",
            )

        # inserts for generating messages
        to_from_on = {"add": "to", "remove": "from", "clear": "on"}[edit_action]
        verb_gerund = {"add": "Adding", "remove": "Removing", "clear": "Clearing"}[edit_action]  # fmt:skip
        field = "tags" if tag_or_altphr == "tag" else "alternate_phrasings"
        questions = await self.coda_api.query_for_questions(query, message)

        if not questions:
            Response(
                confidence=10,
                text=f"I found no questions conforming to the query\n{pformat_to_codeblock(dict([query]))}",
                why=f"{message.author.display_name} asked me to {edit_action} {tag_or_altphr} `{val}` {to_from_on} some question(s) but I found nothing",
            )
        # adding/removing one altphr per many questions is not allowed
        if (
            len(questions) > 1
            and edit_action != "clear"
            and tag_or_altphr == "alternate phrasing"
        ):
            return Response(
                confidence=10,
                text=f"I don't think you want to {edit_action} the same alternate phrasing {to_from_on} {len(questions)} questions. Please, choose one.",
                why=f"{message.author.display_name} asked me to more than one question at once which is not the way to go",
            )

        if edit_action != "clear":
            msg = f"{verb_gerund} {tag_or_altphr} `{val}` {to_from_on} "
        else:
            msg = f"Clearing {tag_or_altphr}s on "
        msg += f"{len(questions)} questions" if len(questions) > 1 else "one question"
        await message.channel.send(msg)

        n_edited = 0
        update_method: Callable[[QuestionRow, list[str]], None] = (
            self.coda_api.update_question_tags
            if tag_or_altphr == "tag"
            else self.coda_api.update_question_altphr
        )

        if edit_action == "add":
            val = cast(str, val)
            for q in questions:
                if val in q[field]:
                    await message.channel.send(
                        f'"{q["title"]}" already has this {tag_or_altphr}'
                    )
                else:
                    update_method(q, q[field] + [val])
                    n_edited += 1
                    await message.channel.send(
                        f'Added {tag_or_altphr} `{val}` to "{q["title"]}"'
                    )
        elif edit_action == "remove":
            for q in questions:
                if val not in q[field]:
                    await message.channel.send(
                        f'"{q["title"]}" doesn\'t have this {tag_or_altphr}'
                    )
                else:
                    new_tags = [t for t in q[field] if t != val]
                    update_method(q, new_tags)
                    n_edited += 1
                    await message.channel.send(
                        f'Removed {tag_or_altphr} `{val}` from "{q["title"]}"'
                    )
        else:  # clear
            for q in questions:
                if not q[field]:
                    await message.channel.send(
                        f'"{q["title"]}" already has no {tag_or_altphr}s'
                    )
                else:
                    update_method(q, [])
                    n_edited += 1
                    await message.channel.send(
                        f'Cleared {tag_or_altphr}s on "{q["title"]}"'
                    )

        if n_edited == 0:
            response_text = "No questions were modified"
        elif edit_action == "clear":
            response_text = f"Cleared {tag_or_altphr}s on {n_edited} questions"
        else:
            response_text = "Added" if edit_action == "add" else "Removed"
            response_text += f" {tag_or_altphr} `{val}` {to_from_on} "
            response_text += f"{n_edited} questions" if n_edited > 1 else "one question"

        why = f"{message.author.display_name} asked me to {edit_action} "
        if edit_action == "clear":
            why += f"{tag_or_altphr}s"
        elif tag_or_altphr == "tag":
            why += "a tag"
        else:
            why += "an alternate question"

        return Response(confidence=10, text=response_text, why=why)

    ###############################
    #   Setting question status   #
    ###############################

    def parse_mark_question_del_dup(
        self, text: str, message: ServiceMessage
    ) -> Optional[Response]:
        """Somebody is tring to mark one or more questions for deletion
        or as duplicates.
        """
        if text.startswith("del "):
            status = "Marked for deletion"
        elif text.startswith("dup "):
            status = "Duplicate"
        else:
            return
        if not (spec := parse_question_spec_query(text)):
            return

        return Response(
            confidence=10,
            callback=self.cb_set_question_status,
            args=[spec, status, text, message],
        )

    def parse_set_question_status(
        self, text: str, message: ServiceMessage
    ) -> Optional[Response]:
        """Somebody is tring to change status of one or more questions."""
        if not (match := self.re_status.search(text)):
            return
        status = self.coda_api.status_shorthand_dict[match.group(1).lower()]
        if not (q_spec_query := parse_question_spec_query(text)):
            return

        return Response(
            confidence=10,
            callback=self.cb_set_question_status,
            args=[q_spec_query, status, text, message],
        )

    async def cb_set_question_status(
        self,
        q_spec_query: QuestionSpecQuery,
        status: QuestionStatus,
        text: str,
        message: ServiceMessage,
    ) -> Response:
        """Change status of one or more questions.
        Only bot devs, editors, and reviewers can do that.
        Additionally, only reviewers can change status to and from `Live on site`.
        """
        if not has_permissions(message.author):
            return Response(
                confidence=10,
                text=f"You don't have permissions to changing question status, <@{message.author}>",
                why=f"{message.author.display_name} tried changing question status, but I don't trust them.",
            )

        if status == "Live on site" and not is_from_reviewer(message):
            return Response(
                confidence=10,
                text=f"You're not a reviewer, <@{message.author}>. Only reviewers can change status of questions to `Live on site`",
                why=f"{message.author.display_name} wanted to set status to `Live on site` but they're not a reviewer.",
            )

        questions = await self.coda_api.query_for_questions(q_spec_query, message)
        if not questions:
            response_text, why = await self.coda_api.get_response_text_and_why(
                questions, q_spec_query, message
            )
            return Response(confidence=10, text=response_text, why=why)

        # Different response if triggered with `s, del` or `s, dup`
        if text[:3] in ("del", "dup"):
            msg = f"Ok, <@{message.author}>, I'll mark " + (
                "it" if len(questions) == 1 else "them"
            )
            if status == "Marked for deletion":
                msg += " for deletion."
            else:
                if len(questions) == 1:
                    msg += " as a duplicate."
                else:
                    msg += " as duplicates."
        else:
            msg = (
                f"Ok, <@{message.author}>, setting status of "
                + (
                    "1 question"
                    if len(questions) == 1
                    else f"{len(questions)} questions"
                )
                + f" to `{status}`"
            )
        await message.channel.send(msg)

        n_already_los = 0

        for q in questions:
            prev_status = q["status"]
            if prev_status == "Live on site" and not is_from_reviewer(message):
                msg = f'`"{q["title"]}"` is already `Live on site`.'
                n_already_los += 1
            else:
                self.coda_api.update_question_status(q, status)
                msg = (
                    f"`\"{q['title']}\"` is now `{status}` (previously `{prev_status}`)"
                )
            await message.channel.send(msg)

        n_changed_status = len(questions) - n_already_los

        # if "to bs" in text:
        #     #()
        msg = (
            f"Changed status of {n_changed_status} question"
            + ("s" if n_changed_status > 1 else "")
            + f" to `{status}`."
        )
        if n_already_los == 1:
            msg += " One question was already `Live on site`."
        elif n_already_los > 1:
            msg += f" {n_already_los} questions were already `Live on site`."
        return Response(
            confidence=10,
            text=msg,
            why=f"{message.author.display_name} asked me to change status to `{status}`.",
        )

    def __str__(self):
        return "Question Setter Module"

    @property
    def test_cases(self) -> list[IntegrationTest]:
        # these tests modify coda so they should be run only in development
        if ENVIRONMENT_TYPE != "development":
            return []

        test_altphr = "TEST_ALTERNATE_PHRASING"
        return [
            ############
            #   Tags   #
            ############
            # some of these tests have increased wait times because sometimes a test requires its predecessor to be evaluated successfully
            self.create_integration_test(
                test_message="tag decision theory https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit",
                expected_regex="Added tag `Decision Theory` to one question",
                test_wait_time=2,
            ),
            self.create_integration_test(
                test_message="tag decision theory https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit",
                expected_regex="No questions were modified",
                test_wait_time=2,
            ),
            self.create_integration_test(
                test_message="rm tag decision theory from https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit",
                expected_regex="Removed tag `Decision Theory` from one question",
                test_wait_time=2,
            ),
            self.create_integration_test(
                test_message="rm tag decision theory from https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit",
                expected_regex="No questions were modified",
                test_wait_time=2,
            ),
            self.create_integration_test(
                test_message="rm tag open problem",
                expected_regex="Removed tag `Open Problem` from one question",
                test_wait_time=1,
            ),
            self.create_integration_test(
                test_message="add tag open problem",
                expected_regex="Added tag `Open Problem` to one question",
            ),
            ###########################
            #   Alternate phrasings   #
            ###########################
            self.create_integration_test(
                test_message=f'alt "{test_altphr}" https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit',
                expected_regex=f"Added alternate phrasing `{test_altphr}` to one question",
                test_wait_time=1,
            ),
            self.create_integration_test(
                test_message=f'alt "{test_altphr}" https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit',
                expected_regex="No questions were modified",
                test_wait_time=1,
            ),
            self.create_integration_test(
                test_message=f'rm alt "{test_altphr}" from https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit',
                expected_regex=f"Removed alternate phrasing `{test_altphr}` from one question",
                test_wait_time=2,
            ),
            self.create_integration_test(
                test_message=f'rm alt "{test_altphr}" from https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit',
                expected_regex="No questions were modified",
                test_wait_time=2,
            ),
            self.create_integration_test(
                test_message="clear alt https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit",
                expected_regex="No questions were modified",
                test_wait_time=1,
            ),
            self.create_integration_test(
                test_message='add alt "XYZ" https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit https://docs.google.com/document/d/1KOHkRf1TCwB3x1OSUPOVKvUMvUDZPlOII4Ycrc0Aynk/edit',
                expected_regex="I don't think you want",
            ),
            self.create_integration_test(
                test_message='rm alt "XYZ" https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit https://docs.google.com/document/d/1KOHkRf1TCwB3x1OSUPOVKvUMvUDZPlOII4Ycrc0Aynk/edit',
                expected_regex="I don't think you want",
            ),
            self.create_integration_test(
                test_message="clear alt https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit https://docs.google.com/document/d/1KOHkRf1TCwB3x1OSUPOVKvUMvUDZPlOII4Ycrc0Aynk/edit",
                expected_regex="No questions were modified",
            ),
            ##############
            #   Status   #
            ##############
            self.create_integration_test(
                test_message="del https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit https://docs.google.com/document/d/1KOHkRf1TCwB3x1OSUPOVKvUMvUDZPlOII4Ycrc0Aynk/edit",
                expected_regex="Changed status of 2 questions to `Marked for deletion`",
            ),
            self.create_integration_test(
                test_message="dup https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit https://docs.google.com/document/d/1KOHkRf1TCwB3x1OSUPOVKvUMvUDZPlOII4Ycrc0Aynk/edit",
                expected_regex="Changed status of 2 questions to `Duplicate`",
            ),
            self.create_integration_test(
                test_message="lgtm https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit https://docs.google.com/document/d/1KOHkRf1TCwB3x1OSUPOVKvUMvUDZPlOII4Ycrc0Aynk/edit",
                expected_regex="2 more questions `Live on site`!",
                test_wait_time=2,
            ),
            self.create_integration_test(
                test_message="set status to bs https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit https://docs.google.com/document/d/1KOHkRf1TCwB3x1OSUPOVKvUMvUDZPlOII4Ycrc0Aynk/edit",
                expected_regex="Changed status of 2 questions to `Bulletpoint sketch`",
                test_wait_time=2,
            ),
        ]
