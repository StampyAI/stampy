from __future__ import annotations

import re
from typing import Literal, Optional, TypedDict

from api.coda import CodaAPI, QuestionStatus
from modules.module import Module, Response
from utilities.serviceutils import ServiceMessage
from utilities.utilities import is_from_reviewer


coda_api = CodaAPI.get_instance()


class QuestionsSetter(Module):
    """Module for editing questions in [coda](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a)."""

    def __init__(self) -> None:
        super().__init__()

        self.class_name = self.__class__.__name__

    #########################################
    # Core: processing and posting messages #
    #########################################

    def process_message(self, message: ServiceMessage) -> Response:
        """Process message"""

        # new_status and gdoc_links
        if parsed := self.parse_review_request(message):
            return Response(
                confidence=8,
                callback=self.cb_review_request,
                args=[parsed, message],
                why=f"{message.author.name} asked for a review",
            )

        # if not response to request and has link, should change to live on site
        # question_ids
        # if parsed := self.parse_response_to_review_request(message):
        #     return Response(
        #         confidence=8,
        #         callback=self.cb_set_status_by_approval_to_review_request,
        #         args=[parsed, message],
        #         why=f"{message.author.name} accepted the review",
        #     )
        # # status, gdoc_links
        # if parsed := self.parse_mark_question_request(message):
        #     return Response(
        #         confidence=8,
        #         callback=self.cb_set_status_by_mark_question_request,
        #         args=[parsed, message],
        #         why=f"{message.author.name} marked these questions as `{parsed['status']}`",
        #     )

        # TODO: parse_set_question_status_command

        return Response()

    ######################
    #   Review request   #
    ######################

    def parse_review_request(
        self, message: ServiceMessage
    ) -> Optional["ReviewRequest"]:
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

        return {"gdoc_links": gdoc_links, "status": status}

    async def cb_review_request(
        self, parsed: "ReviewRequest", message: ServiceMessage
    ) -> Response:
        """"""  # TODO: docstring
        # 1. get questions from those links
        questions = coda_api.get_questions_by_gdoc_links(urls=parsed["gdoc_links"])
        n_gdoc_links = len(parsed["gdoc_links"])
        status = parsed["status"]
        if not questions:
            return Response(
                confidence=10,
                text=f"None of these {n_gdoc_links} links lead to AI Safety Info questions.",
                why="",
            )  # TODO: why

        question_urls = {q["url"].split("/edit?")[0] for q in questions}
        non_question_gdoc_links = [
            link for link in parsed["gdoc_links"] if link not in question_urls
        ]

        if non_question_gdoc_links:
            msg = f"Out of {len(parsed['gdoc_links'])} GDoc links you mentioned, {{len(non_question_gdoc_links)}} didn't lead to "
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


class ReviewRequest(TypedDict):
    gdoc_links: list[str]
    status: Literal["In review", "Bulletpoint sketch", "In progress"]


class QuestionApproval(TypedDict):
    gdoc_links: list[str]


class QuestionMarking(TypedDict):
    gdoc_links: list[str]
    status: Literal["Marked for deletion", "Duplicate"]


class QuestionStatutsSetting(TypedDict):
    type: Literal["id", "last"]
    id: Optional[str]
    status: QuestionStatus


#############
#   Utils   #
#############


def parse_gdoc_links(text: str) -> list[str]:
    """Extract GDoc links from message content.
    Returns `[]` if message doesn't contain any GDoc link.
    """
    return re.findall(r"https://docs\.google\.com/document/d/[\w_-]+", text)
