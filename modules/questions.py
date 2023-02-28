from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime as dt
from pprint import pformat
import random
import re
from string import punctuation
from textwrap import dedent
from typing import Any, Literal, Optional, TypedDict, cast

from dotenv import load_dotenv
import pandas as pd
import requests
from structlog import get_logger
from typing_extensions import Self

from modules.module import Module, Response
from utilities import Utilities
from utilities.serviceutils import ServiceMessage

log = get_logger()
load_dotenv()
utils = Utilities.get_instance()


class Questions(Module):
    """Fetches not started questions from
    [All Answers](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a)
    """

    def __init__(self) -> None:
        super().__init__()
        self.last_question_id: Optional[str] = None
        self.review_msg_id2question_id: dict[str, str] = {}

    #########################################
    # Core: processing and posting messages #
    #########################################

    def process_message(self, message: ServiceMessage) -> Response:
        """Process message"""
        # this one option is before `.is_at_me`
        # because it doesn't require calling Stampy explicitly
        if query := self.is_review_request(message):
            return Response(
                confidence=8,
                callback=self.message_set_status,
                args=[query, message],
                why=f"{message.author.name} asked for a review",
            )
        if query := self.is_response_to_review_request(message):
            return Response(
                confidence=8,
                callback=self.message_set_status,
                args=[query, message],
                why=f"{message.author.name} accepted the review",
            )
        if not (text := self.is_at_me(message)):
            return Response()
        if query := PostOrCountQuestionQuery.parse(text):
            if query.action == "count":
                return Response(
                    confidence=8,
                    callback=self.message_count_questions,
                    args=[query, message],
                    why="I was asked to count questions",
                )
            # get_question_query.action == "post":
            return Response(
                confidence=8,
                callback=self.message_post_question,
                args=[query, message],
                why="I was asked for next questions",
            )
        if query := QuestionInfoQuery.parse(text, self.last_question_id):
            return Response(
                confidence=8,
                callback=self.message_get_question_info,
                args=[query, message],
                why="I was asked to post info about a message",
            )
        if query := SetQuestionQuery.parse(text, self.last_question_id):
            return Response(
                confidence=8,
                callback=self.message_set_status,
                args=[query, message],
                why=f"I was asked to set status of question `{query.id}` to `{query.status}`",
            )
        return Response(why="Left QuestionManager without matching to any query")

    ##################
    # Review request #
    ##################

    def is_review_request(self, message: ServiceMessage) -> Optional[SetQuestionQuery]:
        """Is this message a review request with link do GDoc?"""
        text = message.clean_content
        if (gdoc_link := parse_gdoc_link(text)) is None:
            return
        if (question := self.get_question_by_gdoc_link(gdoc_link)) is None:
            return
        if "@reviewer" in text:
            new_status = "In review"
        elif "@feedback-sketch" in text:
            new_status = "Bulletpoint sketch"
        elif "@feedback" in text:
            new_status = "In progress"
        else:
            return
        self.review_msg_id2question_id[message.id] = question["id"]
        return SetQuestionQuery("review-request", question["id"], new_status)

    def is_response_to_review_request(
        self, message: ServiceMessage
    ) -> Optional[SetQuestionQuery]:
        """Is this message a response to review request?"""
        if (msg_ref := message.reference) is None:
            return
        if (
            msg_ref_id := str(getattr(msg_ref, "message_id", None))
        ) not in self.review_msg_id2question_id:
            return

        text = message.clean_content
        if any(s in text.lower() for s in ["approved", "accepted", "lgtm"]):
            return SetQuestionQuery(
                "review-request-approved",
                self.review_msg_id2question_id[cast(str, msg_ref_id)],
                "Live on site",
            )

    ####################
    # Post question(s) #
    ####################

    async def message_post_question(
        self, query: PostOrCountQuestionQuery, message: ServiceMessage
    ) -> Response:
        """Post message to Discord for least recently asked question.
        It will contain question title and GDoc url.
        """
        # get questions df
        questions = self.get_questions_df(query)

        # if tags were specified, filter questions on those which have at least one of the tags
        if query.tag:
            questions = query.filter_on_tag(questions)

        # get all the oldest ones and shuffle them
        questions = shuffle_questions(questions)
        questions = get_least_recently_asked_on_discord(questions)

        # get exactly n questions (default is 1)
        questions = query.filter_on_max_num_of_questions(questions)

        # make question message and return response
        msg = query.next_result_info(len(questions))
        if not questions.empty:
            msg += "\n\n" + "\n---\n".join(
                make_post_question_message(r) for _, r in questions.iterrows()
            )

        # if there is only one question, remember that one
        if len(questions) == 1:
            self.last_question_id = questions.iloc[0]["id"]

        # update Last Asked On Discord column
        current_time = dt.now().isoformat()
        for question_id in questions["id"].tolist():
            self.update_question_last_asked_date(question_id, current_time)

        return Response(
            confidence=8,
            text=msg,
            why=f"{message.author.name} asked me for next questions",
        )

    def update_question_last_asked_date(self, row_id: str, current_time: str) -> None:
        """Update the "Last Asked on Discord" field in table for the question"""
        payload = {
            "row": {
                "cells": [
                    {"column": "Last Asked On Discord", "value": current_time},
                ],
            },
        }
        uri = f"https://coda.io/apis/v1/docs/{utils.DOC_ID}/tables/{utils.ALL_ANSWERS_TABLE_ID}/rows/{row_id}"
        req = requests.put(uri, headers=utils.get_coda_auth_headers(), json=payload)
        # req.raise_for_status() # Throw if there was an error.
        log.info("Updated question with id %s to time %s", row_id, current_time)

    def reset_dates(self) -> None:
        """Reset all questions' dates (util, not to be used by Stampy)"""
        questions = self.get_questions_df()
        questions_with_dt_ids = questions[
            questions["last_asked_on_discord"] != DEFAULT_DATE
        ]["id"].tolist()
        for question_id in questions_with_dt_ids:
            self.update_question_last_asked_date(question_id, "")

    ###################
    # Count questions #
    ###################

    async def message_count_questions(
        self, query: PostOrCountQuestionQuery, message: ServiceMessage
    ) -> Response:
        """Post message to Discord about number of questions matching the query"""

        # get df with questions
        questions = self.get_questions_df(query)

        # if tags were specified, filter for questions which have at least one of these tags
        if query.tag:
            questions = query.filter_on_tag(questions)

        # Make message and respond
        msg = query.count_result_info(len(questions))

        return Response(
            confidence=8,
            text=msg,
            why=f"{message.author.name} asked me to count questions",
        )

    #####################
    # Get question info #
    #####################

    async def message_get_question_info(
        self, query: QuestionInfoQuery, message: ServiceMessage
    ) -> Response:
        if query.type == "last" and query.query is None:
            return Response(
                confidence=8,
                text="There is no last question ;/",
                why=dedent(
                    f"""\
                    {message.author.name} asked me for last question but I 
                    haven't been asked for (or posted) any questions since I've been started"""
                ),
            )
        questions = self.get_questions_df()
        msg = f"Here it is ({query.info()}):\n\n"
        question_row = next(
            (q for _, q in questions.iterrows() if query.matches(q)), None
        )
        if question_row is not None:
            self.last_question_id = question_row["id"]
            msg += pformat_to_codeblock(question_row.to_dict())
        else:
            msg = "Couldn't find a question matching " + query.info()
        return Response(
            confidence=8,
            text=msg,
            why=f"{message.author.name} asked me to get the question with "
            + query.info(),
        )

    ##############
    # Set status #
    ##############

    async def message_set_status(
        self, query: SetQuestionQuery, message: ServiceMessage
    ) -> Response:
        # If asked for setting status on last question but there is no last question
        if query.type == "last" and query.id is None:
            return Response(
                confidence=8,
                text='What do you mean by "it"?',
                why=dedent(
                    f"""\
                    {message.author.name} asked me to set last question's status 
                    to {query.status} but I haven't posted any questions yet"""
                ),
            )

        question_row = self.get_question_by_id(cast(str, query.id))
        # if couldn't find question
        if question_row is None:
            return Response(
                confidence=8,
                text=f'I couldn\'t find a question with id "{query.id}"',
                why=dedent(
                    f"""\
                    {message.author.name} asked me to set the status of question 
                    with id "{query.id}" to "{query.status}" but I couldn't find it"""
                ),
            )

        self.last_question_id = query.id

        # if somebody without `@reviewer` role tried setting question status to "Live on site"
        # case of unauthorized approval is handled separately in update_question_status
        if (
            response := unauthorized_set_los(query, question_row, message)
        ) and query.type != "review-request-approved":
            return response

        response_msg = self.update_question_status(query, question_row, message)
        why = dedent(
            f"""\
            {message.author.name} asked me to set the status of question
            with id "{query.id}" to "{query.status}"
            """
        )
        return Response(confidence=8, text=response_msg, why=why)

    def update_question_status(
        self, query: SetQuestionQuery, question_row: ParsedRow, message: ServiceMessage
    ) -> str:
        if query.type == "review-request-approved" and not is_from_reviewer(message):
            return f"You're not a `@reviewer` {message.author.name}"

        uri = f"https://coda.io/apis/v1/docs/{utils.DOC_ID}/tables/{utils.ALL_ANSWERS_TABLE_ID}/rows/{query.id}"
        payload = {
            "row": {
                "cells": [
                    {"column": "Status", "value": query.status},
                ],
            },
        }
        req = requests.put(uri, headers=utils.get_coda_auth_headers(), json=payload)
        if query.type == "review-request":
            msg = f"Thanks, {message.author.name}!\nI updated this question's status to `{query.status}`"
        elif query.type == "review-request-approved":
            msg = f"Question approved! Updated status to `{query.status}`"
        else:
            msg = f"Updated question's  status to `{query.status}`"
            msg += "\n\nPreviously:\n" + pformat_to_codeblock(cast(dict, question_row))

        log.info(msg)
        return msg

    ############
    # Coda API #
    ############

    @classmethod
    def send_all_answers_table_request(
        cls, query: Optional[PostOrCountQuestionQuery] = None
    ) -> dict:
        """Get rows from "All Answers" table in our coda"""
        params = {
            "valueFormat": "simple",
            "useColumnNames": True,
            "visibleOnly": False,
            "limit": 1000,
        }
        # optionally query by status
        if query and query.status:
            params["query"] = f'"Status":"{query.status}"'
        uri = f"https://coda.io/apis/v1/docs/{utils.DOC_ID}/tables/{utils.ALL_ANSWERS_TABLE_ID}/rows"
        response = requests.get(
            uri, headers=utils.get_coda_auth_headers(), params=params, timeout=16
        ).json()
        return response

    @classmethod
    def get_questions_df(
        cls, query: Optional[PostOrCountQuestionQuery] = None
    ) -> pd.DataFrame:
        """Get questions from with `status="Not started"`"""
        request_res = cls.send_all_answers_table_request(query)
        rows = [parse_row(row) for row in request_res["items"]]
        return pd.DataFrame(rows)

    def get_question_by_id(self, row_id: str) -> Optional[ParsedRow]:
        """Get question by id in "All Answers" table.
        Returns `ParsedRow` or `None` (if question with that id doesn't exist)
        """
        uri = f"https://coda.io/apis/v1/docs/{utils.DOC_ID}/tables/{utils.ALL_ANSWERS_TABLE_ID}/rows/{row_id}"
        params = {
            "valueFormat": "simple",
            "useColumnNames": True,
        }
        req = requests.get(uri, params=params, headers=utils.get_coda_auth_headers())
        if req.status_code == 200:
            return parse_row(req.json())

    def get_question_by_gdoc_link(self, url: str) -> Optional[ParsedRow]:
        """Get question by link to its GDoc.
        Returns `ParsedRow` or `None` (if question with that id doesn't exist)
        """
        questions = self.get_questions_df()
        questions_queried = questions[questions["url"].str.startswith(url)]
        if not questions_queried.empty:
            return cast(ParsedRow, questions_queried.iloc[0].to_dict())

    @classmethod
    def get_status_shorthand_dict(cls) -> dict[str, str]:
        """Get dictionary mapping statuses and status shorthands
        (e.g. "bs" for "Bulletpoint sketch") to valid Status labels.
        """
        # Workaround to make mock request during testing
        if cls.is_in_testing_mode():
            return {}

        statuses = cls.get_all_statuses()
        status_shorthand_dict = {}
        for status in statuses:
            status_shorthand_dict[status] = status
            status_shorthand_dict[status.lower()] = status
            shorthand = "".join(word[0].lower() for word in status.split())
            status_shorthand_dict[shorthand] = status
        return status_shorthand_dict

    @classmethod
    def get_all_tags(cls) -> list[str]:
        """Get all tags from "All Answers" table"""
        # Workaround to make mock request during testing
        if cls.is_in_testing_mode():
            return []

        response = cls.send_all_answers_table_request()
        tags = set()
        for row in response["items"]:
            if tag_string := row["values"]["Tags"]:
                tags.update(tag_string.split(","))
        return sorted(tags)

    @classmethod
    def get_all_statuses(cls) -> list[str]:
        """Get all valid Status values from table in admin panel"""
        params = {
            "valueFormat": "rich",
            "useColumnNames": True,
        }

        uri = f"https://coda.io/apis/v1/docs/{utils.DOC_ID}/tables/{utils.STATUSES_GRID_ID}/rows"
        res = requests.get(
            uri, params=params, headers=utils.get_coda_auth_headers()
        ).json()
        statuses = [r["name"] for r in res["items"]]
        return sorted(statuses)

    #########
    # Other #
    #########

    @classmethod
    def is_in_testing_mode(cls) -> bool:
        return utils.CODA_API_TOKEN == "testing"

    @property
    def test_cases(self):
        if self.is_in_testing_mode():
            return []
        return [
            self.create_integration_test(
                question="next q", expected_regex=r".+\n\nhttps:.+"
            ),
            self.create_integration_test(
                question="how many questions?",
                expected_regex=r"There are \d{3,4} questions",
            ),
            self.create_integration_test(
                question="what is the next question with status withdrawn and tagged doom",
                expected_regex=r"There are no",
            ),
        ]

    def __str__(self):
        return "Question Manager module"


class ParsedRow(TypedDict):
    """Dict representing one row parsed from coda "All Answers" table"""

    id: str
    title: str
    url: str
    status: str
    tags: list[str]
    last_asked_on_discord: dt


status_shorthands = Questions.get_status_shorthand_dict()
all_tags = Questions.get_all_tags()


##########################
# Question query classes #
##########################


@dataclass(frozen=True)
class PostOrCountQuestionQuery:
    """Post or count questions matching `status` and `tag`"""

    status: Optional[str]
    tag: Optional[str]
    max_num_of_questions: int
    """Maximum number of questions to be posted. Doesn't impact counting."""
    action: Literal["count", "post"]
    """Whether to count questions matching `status` and `tag` 
    or post `max_num_questions` of them
    """

    ###########
    # Parsing #
    ###########

    @classmethod
    def parse(cls, text: str) -> Optional[Self]:
        if re_count_questions.search(text):
            action = "count"
        elif re_next_question.search(text):
            action = "post"
        else:
            return
        status = parse_status(text)
        tag = cls.parse_tag(text)
        max_num_of_questions = cls.parse_max_num_of_questions(text)
        question_query = cls(
            status=status,
            tag=tag,
            max_num_of_questions=max_num_of_questions,
            action=action,
        )
        log.info(f"{question_query=}")
        return question_query

    @staticmethod
    def parse_tag(text: str) -> Optional[str]:
        """Parse string of tags extracted from message"""
        tag_group = (
            "(" + "|".join(all_tags).replace(" ", r"\s") + ")"
        )  # this \s may not be necessary (?)
        re_tag = re.compile(r"tag(?:s|ged(?:\sas)?)?\s+" + tag_group, re.I)
        if (match := re_tag.search(text)) is None:
            return None
        tag = match.group(1)
        tag_group = tag_group.replace(r"\s", " ")
        tag_idx = tag_group.lower().find(tag.lower())
        tag = tag_group[tag_idx : tag_idx + len(tag)]
        return tag

    @staticmethod
    def parse_max_num_of_questions(text: str) -> int:
        re_pre = re.compile(r"(\d{1,2})\sq(?:uestions?)?", re.I)
        re_post = re.compile(r"n\s?=\s?(\d{1,2})", re.I)
        if (match := re_pre.search(text)) or (match := re_post.search(text)):
            try:
                return int(match.group(1))
            except ValueError as exc:
                log.error(exc)
        return 1

    ################################
    # Filtering quetions DataFrame #
    ################################

    def _contains_tag(self, tags: list[str]) -> bool:
        return any(t.lower() == cast(str, self.tag).lower() for t in tags)

    def filter_on_tag(self, questions: pd.DataFrame) -> pd.DataFrame:
        if self.tag:
            return questions[questions["tags"].map(self._contains_tag)]
        return questions

    def filter_on_max_num_of_questions(self, questions: pd.DataFrame) -> pd.DataFrame:
        """Filter on number of questions"""
        if questions.empty:
            return questions
        questions = questions.sort_values(
            "last_asked_on_discord", ascending=False
        ).iloc[: min(self.max_num_of_questions, len(questions))]
        return questions

    ########
    # Info #
    ########

    def code_info(self, *, with_num: bool = False) -> str:
        """Print info about query in code block"""
        d: dict[str, Any] = {"status": self.status, "tag": self.tag}
        if with_num:
            d["max_num_of_questions"] = self.max_num_of_questions
        return pformat_to_codeblock(d)

    def count_result_info(self, num_found: int) -> str:
        """Print info about questions found for counting"""
        if num_found == 1:
            s = "There is 1 question"
        elif num_found > 1:
            s = f"There are {num_found} questions"
        else:  # n_questions == 0:
            s = "There are no questions"
        return s + self.status_and_tags_info()

    def next_result_info(self, num_found: int) -> str:
        """Print info about questions found for posting"""
        if self.max_num_of_questions == 1:
            s = "Here is a question"
        elif num_found == 0:
            s = "I found no questions"
        elif num_found < self.max_num_of_questions:
            s = f"I found only {num_found} questions"
        else:
            s = f"Here are {self.max_num_of_questions} questions"
        return s + self.status_and_tags_info()

    def status_and_tags_info(self) -> str:
        """Print info about query's status and/or tags inline"""
        if self.status and self.tag:
            return f" with status `{self.status}` and tagged as `{self.tag}`"
        if self.status:
            return f" with status `{self.status}`"
        if self.tag:
            return f" tagged as `{self.tag}`"
        return ""


@dataclass(frozen=True)
class QuestionInfoQuery:
    """Get info about particular question

    If `type` is "id", `query` also must be question's id.
    Same when type is `last`, although in that case, Stampy may have not
    interacted with any questions, since its most recent start, which means that
    `query` is `None`. Stampy handles that case gracefully. If `type` is "title",
    Stampy looks up the first question with title that `contains` `query`
    (`query` fuzzily matches some substring of `title`).
    """

    type: Literal["id", "title", "last"]
    query: Optional[str]

    @classmethod
    def parse(cls, text: str, last_question_id: Optional[str]) -> Optional[Self]:
        if "get" not in text and "info" not in text:
            return
        if question_id := parse_id(text):
            return cls("id", question_id)
        if match := re.search(r"(?:question):?\s+([-\w\s]+)", text, re.I):
            question_title = match.group(1)
            return cls("title", question_title)
        if "get last" in text or "get it" in text:
            return cls("last", last_question_id)

    def info(self) -> str:
        """Print info inline about this query"""
        if self.type == "id":
            return f"id `{self.query}`"
        if self.type == "title":
            return f"title: `{self.query}`"
        if self.query:
            return f"last, id: `{self.query}`"
        return "last, id: missing"

    def matches(self, question_row: pd.Series) -> bool:
        """Does this question (row from coda "All Answers" table)
        match this query?
        """
        if self.type == "id" or (self.type == "last" and self.query):
            return question_row["id"].startswith(cast(str, self.query))
        if self.type == "title":
            return contains(question_row["title"], cast(str, self.query))
        return False


@dataclass(frozen=True)
class SetQuestionQuery:
    """Change status of a particular question."""

    type: Literal["id", "last", "review-request", "review-request-approved"]
    """
    - "id" - specified by unique row identifier in "All Answers" table
    - "last" - ordered to get the last row that stampy interacted with
    (changed or posted) in isolation from other rows
    - "review-request" - somebody mentioned one of the roles and posted a link to GDoc,
    which triggered Stampy to change status of that question  
    - "review-request-approved" - a `@reviewer` responded to a review request with 
    "accepted" or "approved" -> questions's status changes to "Live on site"  
    """
    id: Optional[str]
    status: str

    @classmethod
    def parse(cls, text: str, last_question_id: Optional[str]) -> Optional[Self]:
        if "set it" in text or "set last" in text:
            query_type = "last"
            query_id = last_question_id
        elif "set i-" in text:
            query_type = "id"
            query_id = parse_id(text)
            if query_id is None:
                return
        else:
            return
        status = parse_status(text, require_status_prefix=False)
        if status is None:
            return
        return cls(query_type, query_id, status)


##################
# Util functions #
##################


def contains(container: str, contained: str) -> bool:
    """Fuzzy-ish version of `contained in container`.
    Disregards spaces, and punctuation.
    """
    return remove_punct(contained.casefold().replace(" ", "")) in remove_punct(
        container.casefold().replace(" ", "")
    )


def remove_punct(s: str) -> str:
    """Remove punctuation from string"""
    for p in punctuation:
        s = s.replace(p, "")
    return s


DEFAULT_DATE = dt(1, 1, 1, 0)


def adjust_date(date_str: str) -> dt:
    """If date is in isoformat, parse it.
    Otherwise, assign earliest date possible.
    """
    if not date_str:
        return DEFAULT_DATE
    return dt.fromisoformat(date_str.split("T")[0])


def shuffle_questions(questions: pd.DataFrame) -> pd.DataFrame:
    questions_inds = questions.index.tolist()
    shuffled_inds = random.sample(questions_inds, len(questions_inds))
    return questions.loc[shuffled_inds]


def get_least_recently_asked_on_discord(
    questions: pd.DataFrame,
) -> pd.DataFrame:
    """Get all questions with oldest date and shuffle them"""
    oldest_date = questions["last_asked_on_discord"].min()
    return questions.query("last_asked_on_discord == @oldest_date")


def make_post_question_message(question_row: pd.Series) -> str:
    """Make question message from questions DataFrame row

    <title>\n
    <url>
    """
    return question_row["title"] + "\n" + question_row["url"]


def parse_row(row: dict) -> ParsedRow:
    """Parse a raw row from "All answers" table"""
    title = row["values"]["Edit Answer"]
    url = row["values"]["Link"]
    status = row["values"]["Status"]
    tags = row["values"]["Tags"].split(",")
    last_asked_on_discord = adjust_date(row["values"]["Last Asked On Discord"])
    return {
        "id": row["id"],
        "title": title,
        "url": url,
        "status": status,
        "tags": tags,
        "last_asked_on_discord": last_asked_on_discord,
    }


def parse_status(text: str, *, require_status_prefix: bool = True) -> Optional[str]:
    re_status = re.compile(
        r"{status_prefix}({status_vals})".format(
            status_prefix=(r"status\s*" if require_status_prefix else ""),
            status_vals="|".join(rf"\b{s}\b" for s in status_shorthands).replace(
                " ", r"\s"
            ),
        ),
        re.I | re.X,
    )
    if (match := re_status.search(text)) is None:
        return None
    val = match.group(1)
    return status_shorthands[val.lower()]


def pformat_to_codeblock(d: dict) -> str:
    """`pformat` a dictionary and embed it in a code block
    (for nice display in discord message)
    """
    return "```\n" + pformat(d, sort_dicts=False) + "\n```"


def parse_gdoc_link(text: str) -> Optional[str]:
    """Extract a link to GDoc from message content.
    Returns `None` if message doesn't contain GDoc link.
    """
    match = re.search(
        r"https://docs\.google\.com/document/d/.+(?=\b)", text, re.I | re.S
    )
    if match:
        return match.group()


def parse_id(text: str) -> Optional[str]:
    """Parse question id from message content"""
    # matches: "id: <question-id>"
    if match := re.search(r"id:?\s+([-\w]+)", text, re.I):
        return match.group(1)
    # matches: "i-<letters-and-numbers-unitl-word-boundary>" (i.e. question id)
    if match := re.search(r"(i-[\w\d]+)\b", text, re.I):
        return match.group(1)


def is_from_reviewer(message: ServiceMessage) -> bool:
    """This message is from @reviewer"""
    return any(role.name == "reviewer" for role in message.author.roles)


def unauthorized_set_los(
    query: SetQuestionQuery, question_row: ParsedRow, message: ServiceMessage
) -> Optional[Response]:
    """Somebody tried set questions status "Live on site" but they're not a reviewer"""
    if "Live on site" not in (
        query.status,
        question_row["status"],
    ) or is_from_reviewer(message):
        return
    if query.status == "Live on site":
        response_msg = dedent(
            f"""\
            Sorry, {message.author.name}. 
            You can't set this question's status to `Live on site` 
            because you are not a `@reviewer`. 
            Only `@reviewer`s can change question status to `Live on site`."""
        )
        why = dedent(
            f"""\
            {message.author.name} wanted to change status to `Live on site` 
            but they're not a @reviewer"""
        )
    else:  # question_row["status"] == "Live on site":
        response_msg = dedent(
            f"""\
            Sorry, {message.author.name}. You can't set this question's status 
            to `{query.status}` because its current status is `Live on site` and you are not
            a `@reviewer`. Only `@reviewer`s can change status of questions that are already
            `Live on site`."""
        )
        why = f"{message.author.name} wanted to change status from `Live on site` but they're not a @reviewer"
    return Response(confidence=8, text=response_msg, why=why)


###############
# Big regexes #
###############

PAT_QUESTION_QUERY = r"(\d{,2}\s)?q(uestions?)?(\s?.{,128})"
re_next_question = re.compile(
    r"""
(
    (
        [wW]hat
        (’|'|\si)?s
    |
        ([Cc]an|[Mm]ay)\s
        (we|[iI])\s
        (have|get)
    |
        [Ll]et[’']?s\shave
    |
        [gG]ive\sus
    )?  # Optional: what's / can we have / let's have / give us
    (
        \s?[Aa](nother)? # a / another
    |
        (\sthe)?\s?
        [nN]ext
    |
        [pP]ost
    )
    \s
    ({question_query}),? # next question (please)
    (\splease)?\??
    |
    (
        [Dd]o\syou\shave
        |
        ([Hh]ave\syou\s)?
        [gG]ot
    )
    (
        \s?[Aa]ny(\smore|\sother)?
    |
        \sanother
    )
    \s({question_query})?
    (\sfor\sus)?\??
)
!?
""".format(
        question_query=PAT_QUESTION_QUERY
    ),
    re.I | re.X,
)
"""Exemplary questions that trigger this regex:
- Can you give us another question?
- Do you have any more questions for us?
- next 5 questions
- give us next 2 questions with status live on site and tagged as "decision theory"

Suggested:
- next N questions (with status X) (and tagged "Y" "Z")
"""

re_count_questions = re.compile(
    r"""
(   
    (count\s+({question_query}))
    |
    ( # how many questions are there left in ...
    how\s+many\s+({question_query})\s*
    (are\s*(there\s*)?)?
    (left\s*)?
    (in\s+(your\s+|the\s+)?queue\s*)?
    )
|
    ( # how long is/'s the/your questions queue now
    how\s+
    (long\s+is|long's)\s+
    (the\s+|your\s+)?
    (({question_query})\s+)?
    queue
    (\s+now)?
    )
|
    (
    (\#|n|num)\s+(of\s+)?({question_query})
    )
|
    (\#\s*q)|(nq) # shorthands, you can just ask "nq" for number of questions
)
\?* # optional question mark
$   # end
""".format(
        question_query=PAT_QUESTION_QUERY
    ),
    re.I | re.X,
)
"""Suggested:
- how many questions (with status X) (and tagged "Y" "Z")
"""
