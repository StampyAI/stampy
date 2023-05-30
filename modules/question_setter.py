"""
Changing status (in future perhaps also other attributes) of questions in Coda.

**Permissions:**

- All server members can contribute to AI Safety Questions and [ask for feedback](#review-request).
- Only `@bot dev`s, `@editor`s, and `@reviewer`s can change question status by other commands ([1](#marking-questions-for-deletion-or-as-duplicates) [2](#setting-question-status)).
- Only `@reviewers` can change status of questions to and from  `Live on site` (including [accepting](#review-acceptance) [review requests](#review-request)).

### Review request

On Rob Miles's Discord server, an `@editor` can ask other `@editor`s and `@reviewer`s to give them feedback or review their changes to AI Safety Info questions. You just put one or more links to appropriate GDocs and mention one of: `@reviewer`, `@feedback`, or `@feedback-sketch`. Stampy will spot this and update their statuses in the [coda table with answers](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a) appropriately.

- `@reviewer` -> `In review`
- `@feedback` -> `In progress`
- `@feedback-sketch` -> `Bulletpoint sketch`

![](images/help/QuestionsSetter-review-request.png)

Some remarks:

- Optimally, review requesting and approval should be mostly confined to the `#editing` forum-channel.
- You don't need to call Stampy explicitly to make him update question status. All that matters is that you include one or more valid links to GDocs with AI Safety Info questions and an appropriate at-mention.

### Review acceptance

A `@reviewer` can **accept** a question by (1) responding to a [review request](#review-request) with a keyword (listed below) or (2) posting one or more valid links to GDocs with AI Safety Info questions with a keyword. Stampy then reacts by changing status to `Live on site`.

The keywords are (case-insensitive):

- accepted
- approved
- lgtm
  - stands for "looks good to me"

![](images/help/QuestionsSetter-review-acceptance.png)

### Marking questions for deletion or as duplicates

Use `s, <del/dup>` (or `stampy, <del/dup>`) to change status of questions to `Marked for deletion` or `Duplicate`

![](images/help/QuestionsSetter-del-dup.png)

### Setting question status

Question status can be changed more flexibly, using the command: `<set/change> <status/to/status to> <status>`, followed by appropriate GDoc links.

Status name is case-insensitive and you can use status aliases.

![](images/help/QuestionsSetter-set-status.png)

### Adding and removing tags #TODO

### Adding and removing alternative question phrasings #TODO

"""
from __future__ import annotations

import re
from typing import Literal, Optional, Union

from api.coda import CodaAPI
from api.utilities.coda_utils import QuestionStatus
from config import ENVIRONMENT_TYPE
from modules.module import IntegrationTest, Module, Response
from utilities.discordutils import DiscordChannel
from utilities.question_query_utils import (
    QuestionSpecQuery,
    parse_gdoc_links,
    parse_question_spec_query,
    parse_tag,
)
from utilities.serviceutils import ServiceMessage
from utilities.utilities import has_permissions, is_from_reviewer, pformat_to_codeblock


coda_api = CodaAPI.get_instance()
status_shorthands = coda_api.get_status_shorthand_dict()
_status_pat = "|".join(status_shorthands)
re_status = re.compile(rf"(?:set|change) (?:status|to|status to) ({_status_pat})", re.I)

all_tags = coda_api.get_all_tags()

GDocLinks = list[str]
MsgRefId = str
ReviewStatus = Literal["In review", "Bulletpoint sketch", "In progress"]
MarkingStatus = Literal["Marked for deletion", "Duplicate"]


class QuestionSetter(Module):
    """Module for editing questions in [coda](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a)."""

    def __init__(self) -> None:
        super().__init__()
        self.msg_id2gdoc_links: dict[str, list[str]] = {}
        self.re_add_tag = re.compile(r"(add\s)?tag", re.I)
        self.re_remove_tag = re.compile(r"(delete|del|remove|rm)\stag", re.I)

    async def find_gdoc_links_in_msg(
        self, channel: DiscordChannel, msg_ref_id: str
    ) -> None:
        """Find gdoc links in message, which is missing from Stampy's cache."""

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
        questions = coda_api.get_questions_by_gdoc_links(gdoc_links)
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
                coda_api.update_question_status(q, status)
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
            why=f"{message.author.name} did something useful and I wanted coda to reflect that.",
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
        if not (msg_ref_id := getattr(msg_ref, "message_id", None)):
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

        questions = coda_api.get_questions_by_gdoc_links(gdoc_links)

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
                coda_api.update_question_status(q, "Live on site")
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

    ################################
    #   Adding and removing tags   #
    ################################

    def parse_edit_tag(self, text: str, message: ServiceMessage) -> Optional[Response]:
        if self.re_add_tag.match(text):
            mode = "add"
        elif self.re_remove_tag.match(text):
            mode = "remove"
        else:
            return
        tag = parse_tag(text)
        if tag is None:
            return
        query = parse_question_spec_query(text, return_last_by_default=True)
        return Response(
            confidence=10, callback=self.cb_edit_tag, args=[query, tag, message, mode]
        )

    async def cb_edit_tag(
        self,
        query: QuestionSpecQuery,
        tag: str,
        message: ServiceMessage,
        mode: Literal["add", "remove"],
    ) -> Response:
        if not has_permissions(message.author):
            return Response(
                confidence=10,
                text=f"You don't have permissions required to edit tags <@{message.author}>",
                why=f"{message.author.name} does not have permissions edit tags on questions",
            )
        questions = await coda_api.query_for_questions(query, message)
        if not questions:
            Response(
                confidence=10,
                text=f"I found no questions conforming to the query\n{pformat_to_codeblock(dict([query]))}",
                why=f"{message.author.name} asked me to tag some questions as `{tag}` but I found none",
            )

        if mode == "add":
            msg = f"Adding tag `{tag}` to "
        else:
            msg = f"Removing tag `{tag}` from "
        msg += f"{len(questions)}" if len(questions) > 1 else "one question"
        await message.channel.send(msg)

        n_edited = 0

        if mode == "add":
            for q in questions:
                if tag in q["tags"]:
                    await message.channel.send(f'"{q["title"]}" already has this tag')
                else:
                    coda_api.update_question_tags(q, q["tags"] + [tag])
                    n_edited += 1
        else:
            for q in questions:
                if tag not in q["tags"]:
                    await message.channel.send(f'"{q["title"]}" doesn\'t have this tag')
                else:
                    new_tags = [t for t in q["tags"] if t != tag]
                    coda_api.update_question_tags(q, new_tags)
                    n_edited += 1

        if n_edited == 0:
            response_text = "No questions were modified"
        else:
            if mode == "add":
                response_text = f"Added tag `{tag}` to "
            else:
                response_text = f"Removed tag `{tag}` from "
            response_text += f"{n_edited} questions" if n_edited > 1 else "one question"

        return Response(
            confidence=10,
            text=response_text,
            why=f"{message.author.name} asked me to tag these questions, so I did",
        )

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
        if not (match := re_status.search(text)):
            return
        status = status_shorthands[match.group(1).lower()]
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
                why=f"{message.author.name} tried changing question status, but I don't trust them.",
            )

        if status == "Live on site" and not is_from_reviewer(message):
            return Response(
                confidence=10,
                text=f"You're not a reviewer, <@{message.author}>. Only reviewers can change status of questions to `Live on site`",
                why=f"{message.author.name} wanted to set status to `Live on site` but they're not a reviewer.",
            )

        questions = await coda_api.query_for_questions(q_spec_query, message)
        if not questions:
            response_text, why = await coda_api.get_response_text_and_why(
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
                coda_api.update_question_status(q, status)
                msg = (
                    f"`\"{q['title']}\"` is now `{status}` (previously `{prev_status}`)"
                )
            await message.channel.send(msg)

        n_changed_status = len(questions) - n_already_los

        # if "to bs" in text:
        #     #breakpoint()
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
            why=f"{message.author.name} asked me to change status to `{status}`.",
        )

    @property
    def test_cases(self) -> list[IntegrationTest]:
        if ENVIRONMENT_TYPE != "development":
            return []
        return [
            ###############
            #   Tagging   #
            ###############
            self.create_integration_test(
                test_message="tag decision theory https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit",
                expected_regex="Added tag `Decision Theory` to one question",
            ),
            self.create_integration_test(
                test_message="tag decision theory https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit",
                expected_regex="No questions were modified",
            ),
            self.create_integration_test(
                test_message="rm tag decision theory from https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit",
                expected_regex="Removed tag `Decision Theory` from one question",
            ),
            self.create_integration_test(
                test_message="rm tag decision theory from https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit",
                expected_regex="No questions were modified",
            ),
            self.create_integration_test(
                test_message="rm tag open problem",
                expected_regex="Removed tag `Open Problem` from one question",
            ),
            self.create_integration_test(
                test_message="add tag open problem",
                expected_regex="Added tag `Open Problem` to one question",
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
            ),
            self.create_integration_test(
                test_message="set status to bs https://docs.google.com/document/d/1vg2kUNaMcQA2lB9zvJTn9npqVS-pkquLeODG7eVOyWE/edit https://docs.google.com/document/d/1KOHkRf1TCwB3x1OSUPOVKvUMvUDZPlOII4Ycrc0Aynk/edit",
                expected_regex="Changed status of 2 questions to `Bulletpoint sketch`",
            ),
        ]
