"""#TODO:
1. make it parse queries as it should to print one question queried by status and tags
2. make it print more questions
3. make it count questions
4. refactor and make PR
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime as dt
import os
from pprint import pformat
import re
import random
from typing import Optional, TypedDict

from dotenv import load_dotenv
import pandas as pd
import requests
from structlog import get_logger
from typing_extensions import Self

from modules.module import Module, Response
from utilities.serviceutils import ServiceMessage

log = get_logger()


load_dotenv()


CODA_API_TOKEN = os.environ["CODA_API_TOKEN"]


class QuestionManager(Module):
    """Fetches not started questions from
    [Write answers](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/Write-answers_suuwH#Write-answers_tu4_x/r220)
    """

    DOC_ID = "fau7sl2hmG"
    TABLE_NAME = "All answers"

    def __init__(self) -> None:
        super().__init__()
        self.re_next_question = re.compile(_PAT_NEXT_QUESTION, re.I | re.X)
        self.re_count_questions = re.compile(_PAT_COUNT_QUESTIONS, re.I | re.X)

    def process_message(self, message: ServiceMessage) -> Response:
        """Process message"""
        if not (text := self.is_at_me(message)):
            return Response()
        if match := self.re_count_questions.search(text):
            question_query = QuestionQuery.parse(match.group())
            msg = self.make_count_questions_message(question_query)
            return Response(
                confidence=8,
                text=msg,
            )
        if match := self.re_next_question.search(text):
            question_query = QuestionQuery.parse(match.group())
            msg = self.make_next_question_messages(question_query)
            return Response(
                confidence=8, text=msg, why="I was asked for next questions"
            )
        return Response(why="Left QuestionManager without matching to any Regex")

    def get_questions_df(self, qq: QuestionQuery) -> pd.DataFrame:
        """Get questions from with `status="Not started"`"""
        request_res = self.send_coda_questions_request(qq)
        rows = [self.parse_row(row) for row in request_res["items"]]
        return pd.DataFrame(rows)

    def parse_row(self, row: dict) -> ParsedRow:
        """Parse row from "All answers" table"""
        title = row["values"]["Edit Answer"]
        url = row["values"]["Link"]
        status = row["values"]["Status"]
        tags = row["values"]["Tags"].split(",")
        last_asked_on_discord = self.adjust_date(row["values"]["Last Asked On Discord"])
        return {
            "id": row["id"],
            "title": title,
            "url": url,
            "status": status,
            "tags": tags,
            "last_asked_on_discord": last_asked_on_discord,
        }

    ###################
    # Making messages #
    ###################

    def make_next_question_messages(self, qq: QuestionQuery) -> str:
        """Generate Discord message for least recently asked question.
        It will contain question title and GDoc url.
        """
        # get df
        questions_df = self.get_questions_df(qq)
        # filter it
        questions_df = qq.filter_df_on_tags(questions_df)
        questions_df = qq.filter_df_on_n(questions_df)
        # make question messages
        question_messages = [
            self.make_next_question_message(r) for _, r in questions_df.iterrows()
        ]
        if not question_messages:
            return (
                "There are no questions conforming to the query \n```\n"
                + pformat(asdict(qq))
                + "\n```\n"
            )
        return "\n---\n".join(question_messages)

    @staticmethod
    def make_next_question_message(question: pd.Series) -> str:
        return question["title"] + "\n" + question["url"]

    def make_count_questions_message(self, qq: QuestionQuery) -> str:
        questions_df = self.get_questions_df(qq)
        if qq.tags:
            questions_df = qq.filter_df_on_tags(questions_df)

        if n_questions := len(questions_df) == 1:
            msg = "There is 1 question"
        elif n_questions > 1:
            msg = f"There are {n_questions} questions"
        else:  # n_questions == 0:
            msg = "There are no questions"

        if qq.status is not None and not qq.tags:
            msg += f" with status '{qq.status}'"
        elif qq.status is not None and qq.tags:
            if len(qq.tags) > 1:
                msg += f" with status '{qq.status}' and tagged as one of: {qq.tags}"
            else:
                msg += f" with status '{qq.status}' and tagged as '{qq.tags[0]}'"
        elif qq.status is None and qq.tags:
            if len(qq.tags) > 1:
                msg += f" tagged as one of: {qq.tags}"
            else:
                msg += f" tagged as '{qq.tags[0]}'"

        return msg

    @staticmethod
    def adjust_date(date_str: str) -> dt:
        """If date is in isoformat, parse it.
        Otherwise, assign earliest date possible.
        """

        if not date_str:
            return dt(1, 1, 1, 0)
        return dt.fromisoformat(date_str.split("T")[0])

    ############
    # Coda API #
    ############

    @classmethod
    def send_coda_questions_request(cls, qq: QuestionQuery | None = None) -> dict:
        headers = {"Authorization": f"Bearer {CODA_API_TOKEN}"}
        params = {
            "valueFormat": "simple",
            "useColumnNames": True,
            "visibleOnly": False,
            "limit": 1000,
        }
        # breakpoint()
        if qq and qq.status:
            params["query"] = f'"Status":"{qq.status}"'
        uri = f"https://coda.io/apis/v1/docs/{cls.DOC_ID}/tables/{cls.TABLE_NAME}/rows"
        res = requests.get(uri, headers=headers, params=params, timeout=16).json()
        return res

    @classmethod
    def get_status_shorthand_dict(cls) -> dict[str, str]:
        response = cls.send_coda_questions_request()
        status_vals = {row["values"]["Status"] for row in response["items"]}
        d = {}
        for sv in status_vals:
            d[sv] = sv
            d[sv.lower()] = sv
            shorthand = "".join(s[0].lower() for s in sv.split())
            d[shorthand] = sv
        return d

    #########
    # Other #
    #########

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                question="next q", expected_regex=r".+\n\nhttps:.+"
            )
        ]

    def __str__(self):
        return "Question Manager module"


class ParsedRow(TypedDict):
    id: str
    title: str
    url: str
    status: str
    tags: list[str]
    last_asked_on_discord: dt


_status_shorthands = QuestionManager.get_status_shorthand_dict()


@dataclass(frozen=True)
class QuestionQuery:
    status: Optional[str]  # extend to list[str] (?)
    tags: list[str]
    n: int
    # TODO: more queries (?)

    @classmethod
    def parse(cls, msg: str) -> Self:
        status = cls.parse_status(msg)
        tags = cls.parse_tags(msg)
        n = cls.parse_n(msg)
        question_query = cls(status=status, tags=tags, n=n)
        log.info(f"{question_query=}")
        return question_query

    @staticmethod
    def parse_status(msg: str) -> Optional[str]:
        re_status = re.compile(_PAT_STATUS, re.I | re.X)
        if (match := re_status.search(msg)) is None:
            return None
        val = match.group(1)
        return _status_shorthands[val.lower()]

    @staticmethod
    def parse_tags(msg: str) -> list[str]:
        """Parse string of tags extracted from message"""
        re_tags = re.compile(_PAT_TAGS, re.I | re.X)
        if (match := re_tags.search(msg)) is None:
            return []
        tag_string = match.group(1)
        tags = re.split(r"[\"']\s+[\"']", tag_string)
        return [t.replace('"', "").replace("'", "") for t in tags]

    @staticmethod
    def parse_n(msg: str) -> int:
        re_pre = re.compile(_PAT_N_QUESTIONS_PRE, re.I)
        re_post = re.compile(_PAT_N_QUESTIONS_POST, re.I)
        if (match := re_pre.search(msg)) or (match := re_post.search(msg)):
            try:
                return int(match.group(1))
            except ValueError as exc:
                log.error(exc)
        return 1

    def filter_df_on_all(self, df: pd.DataFrame) -> pd.DataFrame:
        assert not df.empty
        df = self.filter_df_on_status(df)
        df = self.filter_df_on_tags(df)
        df = self.filter_df_on_n(df)
        return df

    def filter_df_on_status(self, df: pd.DataFrame) -> pd.DataFrame:
        assert "status" in df
        if (status := self.status) is not None:
            df = df.query("status == @status")
        return df

    def filter_df_on_tags(self, df: pd.DataFrame) -> pd.DataFrame:
        assert "tags" in df
        if self.tags:
            df = df[
                df["tags"].map(
                    lambda tags: any(
                        t.casefold() in list(map(str.casefold, self.tags)) for t in tags
                    )
                )
            ]
        return df

    def filter_df_on_n(self, df: pd.DataFrame) -> pd.DataFrame:
        if df.empty:
            return df
        df = df.sort_values("last_asked_on_discord", ascending=False).iloc[
            : min(self.n, len(df))
        ]
        return df


_PAT_STATUS = r"status\s+({status_vals})".format(
    status_vals="|".join(
        list(_status_shorthands) + list(_status_shorthands.values())
    ).replace(" ", r"\s")
)

_PAT_TAGS = r"tag(?:s|ged(?:\sas)?)?\s+([\"'].+[\"'])+"

_PAT_N_QUESTIONS_PRE = r"(\d{1,2})\sq(?:uestions?)?"
_PAT_N_QUESTIONS_POST = r"n\s?=\s?(\d{1,2})"

_PAT_QUESTION_QUERY = r"(\d{,2}\s)?q(uestions?)?(\s?.{,128})"
_PAT_NEXT_QUESTION = r"""
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
    )?
    (
        \s?[Aa](nother)?
    |
        (\sthe)?\s?
        [nN]ext)\s
        ({question_query}),?
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
    question_query=_PAT_QUESTION_QUERY
)

_PAT_COUNT_QUESTIONS = r"""
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
    question_query=_PAT_QUESTION_QUERY
)
