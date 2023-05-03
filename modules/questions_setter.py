from __future__ import annotations

import re
from typing import Literal, Optional, TypedDict, cast

from api.coda import CodaAPI, QuestionStatus
from modules.module import Module, Response
from utilities.discordutils import DiscordChannel
from utilities.serviceutils import ServiceMessage
from utilities.utilities import is_from_reviewer


coda_api = CodaAPI.get_instance()

GDocLinks = list[str]
MsgRefId = str
ReviewStatus = Literal["In review", "Bulletpoint sketch", "In progress"]
MarkingStatus = Literal["Marked for deletion", "Duplicate"]
class QuestionsSetter(Module):
    """Module for editing questions in [coda](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a)."""

    def __init__(self) -> None:
        super().__init__()

        self.class_name = self.__class__.__name__
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
        if parsed := self.parse_review_request(message):
            gdoc_links, review_status = parsed
            return Response(
                confidence=10,
                callback=self.cb_review_request,
                args=[gdoc_links, review_status, message],
                why=f"{message.author.name} asked for review",
            )

        if parsed := self.parse_question_approval(message):
            return Response(
                confidence=10,
                callback=self.cb_question_approval,
                args=[parsed, message],
                why=f"{message.author.name} approved the question",
            )
        # # status, gdoc_links
        # if parsed := self.parse_mark_question_request(message):
        #     return Response(
        #         confidence=8,
        #         callback=self.cb_set_status_by_mark_question_request,
        #         args=[parsed, message],
        #         why=f"{message.author.name} marked these questions as `{parsed['status']}`",
        #     )

        # TODO: parse_set_question_status_command

        if gdoc_links := parse_gdoc_links(message.clean_content):
            self.review_request_id2gdoc_links[str(message.id)] = gdoc_links

        return Response()

    ######################
    #   Review request   #
    ######################

    def parse_review_request(
        self, message: ServiceMessage
    ) -> Optional[tuple[GDocLinks, ReviewStatus]]:
        """Is this message a review request with link do GDoc?
        If it is, return `SetQuestionStatusByAtCommand`.
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

        return gdoc_links, status

    async def cb_review_request(
        self, 
        gdoc_links: list[str],
        status: ReviewStatus,
        message: ServiceMessage
    ) -> Response:
        """"""  # TODO: docstring
        # 1. get questions from those links
        questions = coda_api.get_questions_by_gdoc_links(gdoc_links)
        n_gdoc_links = len(gdoc_links)
        if not questions:
            return Response(
                confidence=10,
                text=f"None of these {n_gdoc_links} links lead to AI Safety Info questions.",
                why="",
            )  # TODO: why

        question_urls = {q["url"].split("/edit?")[0] for q in questions}
        non_question_gdoc_links = [
            link for link in gdoc_links if link not in question_urls
        ]

        if non_question_gdoc_links:
            msg = f"Out of {len(gdoc_links)} GDoc links you mentioned, {{len(non_question_gdoc_links)}} didn't lead to "
            if len(non_question_gdoc_links) == 1:
                msg += "an AI Safety Info question."
            else:
                msg += "AI Safety Info questions."
            await message.channel.send(msg)

        msg = (
            f"Thanks, <@{message.author}>!\nSetting "
            + ("1 question" if len(questions) == 1 else f"{len(questions)} questions")
            + f" to `{status}`"
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

        if n_updated == 1:
            msg = "1 question updated."
        else:
            msg = "{n_updated} questions updated."
        
        if n_already_los == 1:
            msg += " 1 was already `Live on site`."
        elif n_already_los:
            msg += f" {n_already_los} were already `Live on site` (only reviewers can modify questions that are `Live on site`.)"

        return Response(confidence=10, text=msg, why="")  # TODO: why

    #########################
    #   Question approval   #
    #########################
    
    def parse_question_approval(self, message: ServiceMessage) -> Optional[tuple[GDocLinks, Optional[MsgRefId]]]:
        text = message.clean_content
        if not any(s in text.lower() for s in ("approved", "accepted", "lgtm")):
            return
        
        if gdoc_links := parse_gdoc_links(text):
            return gdoc_links, None
        
        if not (msg_ref := message.reference):
            return
        
        if not (msg_ref_id := cast(Optional[int], getattr(msg_ref, "message_id", None))):
            return

        # if msg_ref_id is missing, then it will need to be retrieved
        gdoc_links = self.review_request_id2gdoc_links.get(str(msg_ref_id), [])
        return gdoc_links, str(msg_ref_id)
    
    async def cb_question_approval(self, gdoc_links: list[str], msg_ref_id: Optional[str], message: ServiceMessage) -> Response:
        """"""#TODO: docstring
        
        if not gdoc_links and isinstance(message.channel, DiscordChannel):
            assert msg_ref_id is not None
            await self.restore_review_msg_cache(message.channel)
            gdoc_links = self.review_request_id2gdoc_links.get(msg_ref_id, [])
        
        questions = coda_api.get_questions_by_gdoc_links(gdoc_links)
        
        if not questions:
            return Response(confidence=10, text="Nothing found ") #TODO: elaborate
        
        if not is_from_reviewer(message):
            return Response(confidence=10, text=f"You're not a reviewer, <@{message.author}> -_-")
        
        await message.channel.send(f"Approved by <@{message.author}>!")
        
        n_new_los = 0
        
        for q in questions:
            if q["status"] == "Live on site":
                await message.channel.send(f"`\"{q['title']}\"` is already `Live on site`")
            else:
                coda_api.update_question_status(q["id"], "Live on site")
                n_new_los += 1
                await message.channel.send(f"`\"{q['title']}\"` goes `Live on site`!")
        
        if n_new_los == 0:
            msg = "No new questions `Live on site`, they were already there."
        elif n_new_los == 1:
            msg = "1 more question `Live on site`!"
        else:        
            msg = f"{n_new_los} more questions `Live on site`!"
        return Response(confidence=10, text=msg, why=f"I set {n_new_los} questions to `Live on site` because {message.author} approved them.")
        
        
# class QuestionStatutsSetting(TypedDict):
#     type: Literal["id", "last"]
#     id: Optional[str]
#     status: QuestionStatus


#############
#   Utils   #
#############


def parse_gdoc_links(text: str) -> list[str]:
    """Extract GDoc links from message content.
    Returns `[]` if message doesn't contain any GDoc link.
    """
    return re.findall(r"https://docs\.google\.com/document/d/[\w_-]+", text)
