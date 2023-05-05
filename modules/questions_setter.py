from __future__ import annotations

from typing import Literal, Optional, Union, cast

from api.coda import CodaAPI, QuestionStatus
from api.utilities.coda_utils import QuestionRow
from modules.module import Module, Response
from utilities.discordutils import DiscordChannel
from utilities.questions_utils import parse_gdoc_links, parse_status
from utilities.serviceutils import ServiceMessage
from utilities.utilities import is_from_editor, is_from_reviewer, is_bot_dev


coda_api = CodaAPI.get_instance()
status_shorthands = coda_api.get_status_shorthand_dict()
all_tags = coda_api.get_all_tags()

GDocLinks = list[str]
MsgRefId = str
ReviewStatus = Literal["In review", "Bulletpoint sketch", "In progress"]
MarkingStatus = Literal["Marked for deletion", "Duplicate"]


class QuestionsSetter(Module):
    """Module for editing questions in [coda](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a)."""

    def __init__(self) -> None:
        super().__init__()
        self.review_request_id2gdoc_links: dict[str, list[str]] = {}

    async def restore_review_msg_cache(
        self, channel: DiscordChannel, limit: int = 2000
    ) -> None:
        """Restore the `review_request_id2gdoc_links` cache."""

        await channel.send("Wait a sec, I'm restoring my cache...")

        self.log.info(
            self.class_name,
            msg="Empty `review_request_id2gdoc_links` cache after reboot, restoring",
        )

        async for msg in channel.history(limit=limit):
            text = msg.clean_content
            if gdoc_links := parse_gdoc_links(text):
                self.review_request_id2gdoc_links[str(msg.id)] = gdoc_links

        self.log.info(
            self.class_name,
            msg=(
                f"Found {len(self.review_request_id2gdoc_links)} "
                f"in the last {limit} messages in channel {channel.name}",
            ),
        )

    #########################################
    # Core: processing and posting messages #
    #########################################

    def process_message(self, message: ServiceMessage) -> Response:
        """Process message"""

        # new_status and gdoc_links
        if response := self.parse_review_request(message):
            return response
        if response := self.parse_question_approval(message):
            return response

        if not (text := self.is_at_me(message)):
            return Response()

        # status, gdoc_links
        if response := self.parse_mark_question_del_dup(text, message):
            return response
        if response := self.parse_set_question_status(text, message):
            return response

        if gdoc_links := parse_gdoc_links(text):
            self.review_request_id2gdoc_links[str(message.id)] = gdoc_links

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
        self.review_request_id2gdoc_links[message.id] = gdoc_links

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
        n_gdoc_links = len(gdoc_links)
        if not questions:
            return Response(
                confidence=10,
                text=f"None of these {n_gdoc_links} links lead to AI Safety Info questions.",
                why=f"{message.author.name} sent some GDoc links but I couldn't find them in the database. Maybe they're `Marked for deletion`/`Duplicate`s/`Withdrawn`?",
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
                coda_api.update_question_status(q["id"], status)
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

        if not (
            msg_ref_id := cast(Optional[int], getattr(msg_ref, "message_id", None))
        ):
            return

        # if msg_ref_id is missing, then it will need to be retrieved
        msg_ref_id = str(msg_ref_id)
        if msg_ref_id in self.review_request_id2gdoc_links:
            gdoc_links = self.review_request_id2gdoc_links[msg_ref_id]
            response_arg = gdoc_links
        else:
            response_arg = msg_ref_id
        return Response(
            confidence=10,
            callback=self.cb_question_approval,
            args=[response_arg, message],
        )

    async def cb_question_approval(
        self, parsed: Union[GDocLinks, MsgRefId], message: ServiceMessage
    ) -> Response:
        """Obtain GDoc links to approved questions and change their status in coda
        to `Live on site`.
        """
        if isinstance(parsed, list):
            gdoc_links = parsed
        else:
            msg_ref_id = parsed
            assert isinstance(message.channel, DiscordChannel)
            await self.restore_review_msg_cache(message.channel)
            gdoc_links = self.review_request_id2gdoc_links.get(msg_ref_id, [])

        questions = coda_api.get_questions_by_gdoc_links(gdoc_links)

        if not questions:
            return Response(confidence=10, text="Nothing found ")  # TODO: elaborate

        if not is_from_reviewer(message):
            return Response(
                confidence=10, text=f"You're not a reviewer, <@{message.author}> -_-"
            )

        await message.channel.send(f"Approved by <@{message.author}>!")

        n_new_los = 0

        for q in questions:
            if q["status"] == "Live on site":
                await message.channel.send(
                    f"`\"{q['title']}\"` is already `Live on site`"
                )
            else:
                coda_api.update_question_status(q["id"], "Live on site")
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

    ###############################
    #   Setting question status   #
    ###############################

    def parse_mark_question_del_dup(
        self, text: str, message: ServiceMessage
    ) -> Optional[Response]:
        """Somebody is tring to mark one or more questions for deletion
        or as duplicates.
        """
        # TODO: check if this works with text from is_at_me
        if text.startswith("del"):
            status = "Marked for deletion"
        elif text.startswith("dup"):
            status = "Duplicate"
        else:
            return
        if not (gdoc_links := parse_gdoc_links(text)):
            return
        return Response(
            confidence=10,
            callback=self.cb_set_question_status,
            args=[gdoc_links, status, "mark", message],
        )

    def parse_set_question_status(
        self, text: str, message: ServiceMessage
    ) -> Optional[Response]:
        """Somebody is tring to change status of one or more questions."""
        if not ("set" in text.lower() or "status" in text.lower()):
            return
        if not (status := parse_status(text, require_status_prefix=False)):
            return
        if not (gdoc_links := parse_gdoc_links(text)):
            return
        return Response(
            confidence=10,
            callback=self.cb_set_question_status,
            args=[gdoc_links, status, "set", message],
        )

    async def cb_set_question_status(
        self,
        gdoc_links: list[str],
        status: QuestionStatus,
        message: ServiceMessage,
    ) -> Response:
        """Change status of one or more questions.
        Only bot devs, editors, and reviewers can do that.
        Additionally, only reviewers can change status to and from `Live on site`.
        """
        if not (
            is_from_editor(message)
            or is_from_reviewer(message)
            or is_bot_dev(message.author)
        ):
            return Response(
                confidence=10,
                text=f"You don't have permissions to change question status, <@{message.author}>",
                why=f"{message.author.name} tried changing questions status, but I don't trust them.",
            )

        if status == "Live on site" and not is_from_reviewer(message):
            return Response(
                confidence=10,
                text=f"You're not a reviewer, <@{message.author}>. Only reviewers can change status of questions to `Live on site`",
                why=f"{message.author.name} wanted to set status to `Live on site` but they're not a reviewer.",
            )

        questions = coda_api.get_questions_by_gdoc_links(gdoc_links)
        if not questions:
            return Response(
                confidence=10,
                text="These GDoc links don't lead to any AI Safety Info questions.",
                why=f"{message.author.name} gave me some GDoc links to change their status to `{status}` but I couldn't find those links in our database",
            )

        msg = (
            f"Ok, <@{message.author}>, setting status of "
            + ("1 question" if len(questions) == 1 else f"{len(questions)} questions")
            + f" to `{status}`"
        )
        await message.channel.send(msg)

        n_already_los = 0

        for q in questions:
            prev_status = q["status"]
            if prev_status == "Live on site" and not is_from_reviewer(message):
                msg = f"`\"{q['title']}\"` is already `Live on site`."
                n_already_los += 1
            else:
                coda_api.update_question_status(q["id"], status)
                msg = (
                    f"`\"{q['title']}\"` is now `{status}` (previously `{prev_status}`)"
                )
            await message.channel.send(msg)

        n_changed_status = len(questions) - n_already_los
        # TODO: nicer handling of different numberings
        msg = f"Changed status of {n_changed_status} questions to `{status}`."
        if n_already_los:
            msg += f" {n_already_los} were already `Live on site`"

        return Response(
            confidence=10,
            text=msg,
            why=f"{message.author.name} asked me set status to `{status}`",
        )


# TODO: reuse it here
def unauthorized_set_los(
    status: QuestionStatus,
    question: QuestionRow,
    message: ServiceMessage,
) -> Optional[Response]:
    """Somebody tried set questions status "Live on site" but they're not a reviewer"""
    if "Live on site" not in (
        status,
        question["status"],
    ) or is_from_reviewer(message):
        return
    if status == "Live on site":
        response_msg = NOT_FROM_REVIEWER_TO_LIVE_ON_SITE.format(
            author_name=message.author.name
        )
        why = (
            f"{message.author.name} wanted to change question status "
            "to `Live on site` but they're not a @reviewer"
        )
    else:  # "Live on site" in question_statuses:
        response_msg = NOT_FROM_REVIEWER_FROM_LIVE_ON_SITE.format(
            author_name=message.author.name, query_status=status
        )
        why = (
            f"{message.author.name} wanted to change status from "
            "`Live on site` but they're not a @reviewer"
        )
    return Response(confidence=8, text=response_msg, why=why)


NOT_FROM_REVIEWER_TO_LIVE_ON_SITE = """\
Sorry, {author_name}. You can't set question status to `Live on site` because you are not a `@reviewer`. 
Only `@reviewer`s can do thats."""

NOT_FROM_REVIEWER_FROM_LIVE_ON_SITE = """\
Sorry, {author_name}. You can't set status  to `{query_status}` because at least one of them is already `Live on site`. 
Only `@reviewer`s can change status of questions that are already `Live on site`."""
