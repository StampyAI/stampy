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
import os
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


class Questions(Module):
    """Fetches not started questions from
    [Write answers](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/Write-answers_suuwH#Write-answers_tu4_x/r220)
    """

    DOC_ID = "fau7sl2hmG"
    TABLE_ID = "table-YvPEyAXl8a"

    def __init__(self) -> None:
        super().__init__()
        self.re_next_question = re.compile(_PAT_NEXT_QUESTION, re.I | re.X)
        self.re_count_questions = re.compile(_PAT_COUNT_QUESTIONS, re.I | re.X)

    def process_message(self, message: ServiceMessage) -> Response:
        """Process message"""
        if not (text := self.is_at_me(message)):
            return Response()
        if match := self.re_count_questions.search(text):
            return Response(
                confidence=8,
                callback=self.post_count_questions_message,
                args=[match, message],
                why="I was asked to count questions",
            )
        if match := self.re_next_question.search(text):
            return Response(
                confidence=8,
                callback=self.post_next_question_messages,
                args=[match, message],
                why="I was asked for next questions",
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

    async def post_next_question_messages(
        self, match: re.Match[str], message: ServiceMessage
    ) -> Response:
        """Post message to Discord for least recently asked question.
        It will contain question title and GDoc url.
        """
        # get questions df
        qq = QuestionQuery.parse(match.group())
        questions = self.get_questions_df(qq)

        # if tags were specified, filter questions on those which have at least one of the tags
        if qq.tags:
            questions = qq.filter_on_tags(questions)
        # otherwise, get all the oldest ones and shuffle them
        else:
            questions = self.shuffle_questions(questions)
            questions = self.get_least_recently_asked_on_discord(questions)

        # get exactly n questions (default is 1)
        questions = qq.filter_on_max_num_of_questions(questions)

        # make question message and return response
        if questions.empty:
            msg = f"There are no questions conforming to the following query\n{qq.code_info}"
        else:
            msg = "\n---\n".join(
                self.make_next_question_message(r) for _, r in questions.iterrows()
            )
            if len(questions) < qq.max_num_of_questions:
                if len(questions) == 1:
                    msg = f"(I found only 1 such question)\n\n{msg}"
                else:
                    msg = f"I found only {len(questions)} such questions\n\n{msg}"
        return Response(
            confidence=8,
            text=msg,
            why=f"{message.author} asked me for next questions",
        )

    @staticmethod
    def make_next_question_message(question: pd.Series) -> str:
        """Make question message from questions DataFrame row

        <title>\n
        <url>
        """
        return question["title"] + "\n" + question["url"]

    async def post_count_questions_message(
        self, match: re.Match[str], message: ServiceMessage
    ) -> Response:
        """Post message to Discord about number of questions matching the query"""

        # get df with questions
        qq = QuestionQuery.parse(match.group())
        questions_df = self.get_questions_df(qq)

        # if tags were specified, filter for questions which have at least one of these tags
        if qq.tags:
            questions_df = qq.filter_on_tags(questions_df)

        # Make message and respond
        if len(questions_df) == 1:
            msg = "There is 1 question"
        elif len(questions_df) > 1:
            msg = f"There are {len(questions_df)} questions"
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

        return Response(
            confidence=8,
            text=msg,
            why=f"{message.author} asked me to count questions",
        )

    @staticmethod
    def adjust_date(date_str: str) -> dt:
        """If date is in isoformat, parse it.
        Otherwise, assign earliest date possible.
        """

        if not date_str:
            return dt(1, 1, 1, 0)
        return dt.fromisoformat(date_str.split("T")[0])

    @staticmethod
    def shuffle_questions(questions: pd.DataFrame) -> pd.DataFrame:
        questions_inds = questions.index.tolist()
        shuffled_inds = random.sample(questions_inds, len(questions_inds))
        return questions.loc[shuffled_inds]

    @staticmethod
    def get_least_recently_asked_on_discord(
        questions: pd.DataFrame,
    ) -> pd.DataFrame:
        """Get all questions with oldest date and shuffle them"""

        oldest_date = questions["last_asked_on_discord"].min()
        return questions.query("last_asked_on_discord == @oldest_date")

    ############
    # Coda API #
    ############

    @classmethod
    def send_coda_questions_request(cls, qq: QuestionQuery | None = None) -> dict:
        """Get rows from "All Answers" table in our coda"""

        coda_api_token = os.environ["CODA_API_TOKEN"]
        headers = {"Authorization": f"Bearer {coda_api_token}"}
        params = {
            "valueFormat": "simple",
            "useColumnNames": True,
            "visibleOnly": False,
            "limit": 1000,
        }
        # optionally query by status
        if qq and qq.status:
            params["query"] = f'"Status":"{qq.status}"'
        uri = f"https://coda.io/apis/v1/docs/{cls.DOC_ID}/tables/{cls.TABLE_ID}/rows"
        response = requests.get(uri, headers=headers, params=params, timeout=16).json()
        return response

    @classmethod
    def get_status_shorthand_dict(cls) -> dict[str, str]:
        """Get dictionary mapping statuses and shorthands for statuses
        to actual status labels as appear in coda
        """

        response = cls.send_coda_questions_request()
        status_vals = {row["values"]["Status"] for row in response["items"]}
        shorthand_dict = {}
        for status_val in status_vals:
            shorthand_dict[status_val] = status_val
            shorthand_dict[status_val.lower()] = status_val
            shorthand = "".join(word[0].lower() for word in status_val.split())
            shorthand_dict[shorthand] = status_val
        return shorthand_dict

    #########
    # Other #
    #########

    # @property
    # def test_cases(self):
    #     return [
    #         self.create_integration_test(
    #             question="next q", expected_regex=r".+\n\nhttps:.+"
    #         ),
    #         self.create_integration_test(
    #             question="how many questions?",
    #             expected_regex=r"There are \d{3,4} questions",
    #         ),
    #         self.create_integration_test(
    #             question="what is the next question with status withdrawn and tagged 'doom'",
    #             expected_regex=r"There are no",
    #         ),
    #     ]

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


@dataclass(frozen=True)
class QuestionQuery:
    status: Optional[str]  # extend to list[str] (?)
    tags: list[str]
    max_num_of_questions: int
    # TODO: more queries (?)

    @property
    def code_info(self) -> str:
        """Print info about query in code block"""
        return f"""```\nstatus: {self.status}\ntags: {self.tags}\n```"""

    ##############################
    # Parsing query from message #
    ##############################

    @classmethod
    def parse(cls, msg: str) -> Self:
        status = cls.parse_status(msg)
        tags = cls.parse_tags(msg)
        max_num_of_questions = cls.parse_max_num_of_questions(msg)
        question_query = cls(
            status=status, tags=tags, max_num_of_questions=max_num_of_questions
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
    def parse_tags(msg: str) -> list[str]:
        """Parse string of tags extracted from message"""
        re_tags = re.compile(r"tag(?:s|ged(?:\sas)?)?\s+([\"'].+[\"'])+", re.I)
        if (match := re_tags.search(msg)) is None:
            return []
        tag_string = match.group(1)
        tags = re.split(r"[\"']\s+[\"']", tag_string)
        return [t.replace('"', "").replace("'", "") for t in tags]

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

    def filter_on_all(self, questions: pd.DataFrame) -> pd.DataFrame:
        assert not questions.empty
        questions = self.filter_on_status(questions)
        questions = self.filter_on_tags(questions)
        questions = self.filter_on_max_num_of_questions(questions)
        return questions

    def filter_on_status(self, questions: pd.DataFrame) -> pd.DataFrame:
        if (status := self.status) is not None:
            questions = questions.query("status == @status")
        return questions

    def filter_on_tags(self, questions: pd.DataFrame) -> pd.DataFrame:
        if self.tags:
            questions = questions[
                questions["tags"].map(
                    lambda tags: any(
                        t.casefold() in list(map(str.casefold, self.tags)) for t in tags
                    )
                )
            ]
        return questions

    def filter_on_max_num_of_questions(self, questions: pd.DataFrame) -> pd.DataFrame:
        """Filter on number of questions"""
        if questions.empty:
            return questions
        questions = questions.sort_values(
            "last_asked_on_discord", ascending=False
        ).iloc[: min(self.max_num_of_questions, len(questions))]
        return questions


###################################################
# Big regexes defined separately for code clarity #
###################################################

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
    question_query=_PAT_QUESTION_QUERY
)
"""Exemplary questions that trigger this regex:
- Can you give us another question?
- Do you have any more questions for us?
- next 5 questions
- give us next 2 questions with status live on site and tagged as "decision theory"

Suggested:
- next N questions (with status X) (and tagged "Y" "Z")
"""

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
"""Suggested:
- how many questions (with status X) (and tagged "Y" "Z")
"""
