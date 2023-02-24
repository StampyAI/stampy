"""#TODO NEXT:
1. Post questions to Discord automatically when nobody says anything for (e.g.) 12 hours
2. "s, change this question's status to "Not Started"
3. See if it can be made faster (e.g. by doing more of the querying in coda rather than in pandas)

Nice to have:
- Nicer/more extensive querying
- Stampy, when was this question last asked on Discord?
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime as dt
from functools import reduce
from operator import add
import os
import random
import re
from string import punctuation
from typing import Literal, Optional, TypedDict, cast

from dotenv import load_dotenv
import pandas as pd
import requests
from structlog import get_logger
from typing_extensions import Self

from modules.module import Module, Response
from utilities.serviceutils import ServiceMessage

log = get_logger()
load_dotenv()


class Questions(Module):
    """Fetches not started questions from
    [All Answers](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a)
    """

    DOC_ID = "fau7sl2hmG"
    TABLE_ID = "table-YvPEyAXl8a"
    CODA_API_TOKEN = os.environ["CODA_API_TOKEN"]
    last_question_id: Optional[str] = None

    def __init__(self) -> None:
        super().__init__()
    
    #########################################
    # Core: processing and posting messages #
    #########################################
    
    def process_message(self, message: ServiceMessage) -> Response:
        """Process message"""
        if not (text := self.is_at_me(message)):
            return Response()
        if get_question_query := GetQuestionQuery.parse(text):
            if get_question_query.action == "count":
                return Response(
                    confidence=8,
                    callback=self.post_count_questions_message,
                    args=[get_question_query, message],
                    why="I was asked to count questions",
                )
            else: # get_question_query.action == "next":
                return Response(
                    confidence=8,
                    callback=self.post_next_question_messages,
                    args=[get_question_query, message],
                    why="I was asked for next questions",
                )
        return Response(why="Left QuestionManager without matching to any Regex")

    @classmethod
    def get_questions_df(cls, qq: GetQuestionQuery | None = None) -> pd.DataFrame:
        """Get questions from with `status="Not started"`"""
        request_res = cls.request_get_questions(qq)
        rows = [cls.parse_row(row) for row in request_res["items"]]
        return pd.DataFrame(rows)

    @classmethod
    def parse_row(cls, row: dict) -> ParsedRow:
        """Parse row from "All answers" table"""
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

    ####################
    # Posting messages #
    ####################

    async def post_next_question_messages(
        self, query: GetQuestionQuery, message: ServiceMessage
    ) -> Response:
        """Post message to Discord for least recently asked question.
        It will contain question title and GDoc url.
        """
        # get questions df
        questions = self.get_questions_df(query)

        # if tags were specified, filter questions on those which have at least one of the tags
        if query.tag:
            questions = query.filter_on_tag(questions)
        # otherwise, get all the oldest ones and shuffle them
        else:
            questions = shuffle_questions(questions)
            questions = get_least_recently_asked_on_discord(questions)

        # get exactly n questions (default is 1)
        questions = query.filter_on_max_num_of_questions(questions)

        # make question message and return response
        msg = query.next_result_info(len(questions))
        if not questions.empty:
            msg += "\n\n" + "\n---\n".join(
                make_next_question_message(r) for _, r in questions.iterrows()
            )
        return Response(
            confidence=8,
            text=msg,
            why=f"{message.author} asked me for next questions",
        )

    async def post_count_questions_message(
        self, query: GetQuestionQuery, message: ServiceMessage
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
            why=f"{message.author} asked me to count questions",
        )

    # async def post_tag_question_message(
    #     self, match: re.Match[str], message: ServiceMessage
    # ) -> Response:
    #     matched_question_title = match.group()
    #     row = self.get_row_by_question_title(matched_question_title)
    #     if row is None:
    #         return Response(
    #             confidence=8,
    #             text=f"Now question with title matching {matched_question_title}",
    #             why="Couldn't find question with title matching that",
    #         )
    #     row_id = row["id"]
    #     title = row["title"]
    #     uri = f"https://coda.io/apis/v1/docs/{self.DOC_ID}/tables/{self.TABLE_ID}/rows/{row_id}"
    #     payload = {
    #     "row": {
    #         "cells": [
    #         {'column': '<column ID>', 'value': 'Get groceries from Whole Foods'},
    #         ],
    #     },
    #     }
    #     req = requests.put(uri, headers=self.get_headers(), json=payload)
    #     req.raise_for_status() # Throw if there was an error.
    #     res = req.json()

    ############
    # Coda API #
    ############

    @classmethod
    def request_get_questions(cls, query: GetQuestionQuery | None = None) -> dict:
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
        uri = f"https://coda.io/apis/v1/docs/{cls.DOC_ID}/tables/{cls.TABLE_ID}/rows"
        response = requests.get(uri, headers=cls.get_headers(), params=params, timeout=16).json()
        return response

    
    # def request_get_question_info(self, q: )

    # @classmethod
    # def get_row_by_question_title(cls, title: str) -> ParsedRow | None:
    #     """Get ID of that questions' row"""
    #     df = cls.get_questions_df()
    #     for _, r in df.iterrows():
    #         if contains(container=r["title"], contained=title):
    #             return cast(ParsedRow, r.to_dict())

    @classmethod
    def get_status_shorthand_dict(cls) -> dict[str, str]:
        """Get dictionary mapping statuses and shorthands for statuses
        to actual status labels as appear in coda
        """
        # Workaround to make mock request during testing
        if cls.is_in_testing_mode():
            return {}

        response = cls.request_get_questions()
        status_vals = {row["values"]["Status"] for row in response["items"]}
        shorthand_dict = {}
        for status_val in status_vals:
            shorthand_dict[status_val] = status_val
            shorthand_dict[status_val.lower()] = status_val
            shorthand = "".join(word[0].lower() for word in status_val.split())
            shorthand_dict[shorthand] = status_val
        return shorthand_dict

    @classmethod
    def get_all_tags(cls) -> list[str]:
        """Get all tags from "All Answers" table"""
        if cls.is_in_testing_mode():
            return []

        response = cls.request_get_questions()
        all_tags: set[str] = set(#TODO: make it more readable
            filter(
                bool,
                reduce(
                    add, [row["values"]["Tags"].split(",") for row in response["items"]]
                ),
            )
        )
        return sorted(all_tags)

    #########
    # Other #
    #########

    @classmethod
    def is_in_testing_mode(cls) -> bool:
        return cls.CODA_API_TOKEN == "testing"

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
                question="what is the next question with status withdrawn and tagged 'doom'",
                expected_regex=r"There are no",
            ),
        ]

    @classmethod
    def get_headers(cls) -> dict:
        return {"Authorization": f"Bearer {cls.CODA_API_TOKEN}"}
    
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


_status_shorthands = Questions.get_status_shorthand_dict()
_all_tags = Questions.get_all_tags()


##########################
# Question query classes #
##########################

@dataclass(frozen=True)
class GetQuestionQuery:
    status: Optional[str]
    tag: Optional[str]
    max_num_of_questions: int
    action: Literal["count", "next"]

    def code_info(self, *, with_num: bool = False) -> str:
        """Print info about query in code block"""
        s = f"""```\nstatus: {self.status}\ntags: {self.tag}\n"""
        if with_num:
            s += f"max_num_of_questions: {self.max_num_of_questions}\n"
        s += "```"
        return s
    
    def count_result_info(self, num_found: int) -> str:
        if num_found == 1:
            s = "There is 1 question"
        elif num_found > 1:
            s = f"There are {num_found} questions"
        else:  # n_questions == 0:
            s = "There are no questions"
        return s + self.status_and_tags_info()

                
    def next_result_info(self, num_found: int) -> str:
        #TODO: test/assert?
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
        if self.status and not self.tag:
            return f' with status "{self.status}"'
        if self.status and self.tag:
            return f' with status "{self.status}" and tagged as "{self.tag}"'
        if not self.status and self.tag:
            return f' tagged as "{self.tag}"'
        return ""


    ##############################
    # Parsing query from message #
    ##############################

    @classmethod
    def parse(cls, text: str) -> Optional[Self]:
        if re_count_questions.search(text):
            action = "count"
        elif re_next_question.search(text):
            action = "next"
        else:
            return
        status = cls.parse_status(text)
        tag = cls.parse_tag(text)
        max_num_of_questions = cls.parse_max_num_of_questions(text)
        question_query = cls(
            status=status, tag=tag, max_num_of_questions=max_num_of_questions, action=action
        )
        log.info(f"{question_query=}")
        return question_query

    @staticmethod
    def parse_status(msg: str) -> Optional[str]:
        re_status = re.compile(
            r"status\s+({status_vals})".format(
                status_vals="|".join(
                    list(_status_shorthands) + list(_status_shorthands.values())
                ).replace(" ", r"\s")
            ),
            re.I | re.X,
        )
        if (match := re_status.search(msg)) is None:
            return None
        val = match.group(1)
        return _status_shorthands[val.lower()]

    @staticmethod
    def parse_tag(msg: str) -> Optional[str]:
        """Parse string of tags extracted from message"""
        # breakpoint()
        tag_group = "(" + "|".join(_all_tags).replace(" ", r"\s") + ")" # this \s may not be necessary (?)
        re_tag = re.compile(r"tag(?:s|ged(?:\sas)?)?\s+" + tag_group, re.I)
        if (match := re_tag.search(msg)) is None:
            return None
        tag = match.group(1)
        tag_group = tag_group.replace(r"\s", " ")
        tag_idx = tag_group.lower().find(tag.lower())
        tag = tag_group[tag_idx : tag_idx + len(tag)]
        return tag

    @staticmethod
    def parse_max_num_of_questions(msg: str) -> int:
        re_pre = re.compile(r"(\d{1,2})\sq(?:uestions?)?", re.I)
        re_post = re.compile(r"n\s?=\s?(\d{1,2})", re.I)
        if (match := re_pre.search(msg)) or (match := re_post.search(msg)):
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

@dataclass(frozen=True)
class GetQuestionInfoQuery:
    id: Optional[str]
    title: Optional[str]
    
    @classmethod
    def parse(cls, msg: str) -> Optional[Self]:
        re_id = re.compile(r"id:?\s+([-\w]+)", re.I)
        if match := re_id.search(msg):
            question_id = match.group(0)
            return cls(question_id, None)
        re_title = re.compile(r"(?:titled?|question):?\s+([-\w]+)", re.I)
        if match := re_title.search(msg):
            question_title = match.group(0)
            return cls(None, question_title)

        
##################
# Util functions #
##################

def contains(container: str, contained: str) -> bool:
    return remove_punct(
        contained.casefold().replace(" ", "")
    ) in remove_punct(container.casefold().replace(" ", ""))


@staticmethod
def remove_punct(s: str) -> str:
    for p in punctuation:
        s = s.replace(p, "")
    return s

def adjust_date(date_str: str) -> dt:
    """If date is in isoformat, parse it.
    Otherwise, assign earliest date possible.
    """

    if not date_str:
        return dt(1, 1, 1, 0)
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

def make_next_question_message(question: pd.Series) -> str:
    """Make question message from questions DataFrame row

    <title>\n
    <url>
    """
    return question["title"] + "\n" + question["url"]


###############
# Big regexes #
###############

PAT_QUESTION_QUERY = r"(\d{,2}\s)?q(uestions?)?(\s?.{,128})"
re_next_question = re.compile(r"""
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
        [nN]ext)\s
        ({question_query}),? # next question (please)
        (\splease)?\??
    |
        ([Dd]o\syou\shave
    |
        ([Hh]ave\syou\s)?
        [gG]ot
    )?
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
), re.I | re.X)
"""Exemplary questions that trigger this regex:
- Can you give us another question?
- Do you have any more questions for us?
- next 5 questions
- give us next 2 questions with status live on site and tagged as "decision theory"

Suggested:
- next N questions (with status X) (and tagged "Y" "Z")
"""

re_count_questions = re.compile(r"""
(
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
), re.I | re.X)
"""Suggested:
- how many questions (with status X) (and tagged "Y" "Z")
"""
