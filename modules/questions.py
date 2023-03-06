from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import random
import re
from textwrap import dedent
from typing import Any, Literal, Optional, Union, cast

from dotenv import load_dotenv
from discord.threads import Thread
import pandas as pd
from structlog import get_logger
from typing_extensions import Self

from api.coda import CodaAPI
from api.utilities.coda_utils import QuestionRow
from servicemodules.discordConstants import editing_channel_id, general_channel_id
from modules.module import Module, Response
from utilities.utilities import (
    is_in_testing_mode,
    is_from_reviewer,
    fuzzy_contains,
    pformat_to_codeblock,
)
from utilities.serviceutils import ServiceMessage


log = get_logger()
load_dotenv()

coda_api = CodaAPI.get_instance()
status_shorthands = coda_api.get_status_shorthand_dict()
all_tags = coda_api.get_all_tags()


class Questions(Module):
    """Fetches not started questions from
    [All Answers](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a)
    """

    AUTOPOST_QUESTION_INTERVAL = timedelta(hours=6)

    def __init__(self) -> None:
        super().__init__()
        self.last_question_id: Optional[str] = None
        self.review_msg_id2question_ids: dict[str, list[str]] = {}
        self.last_question_posted: datetime = (
            datetime.now() - self.AUTOPOST_QUESTION_INTERVAL / 2
        )
        self.class_name = "Questions Module"

        # Register `post_random_oldest_question` to be triggered every after 6 hours of no question posting
        @self.utils.client.event
        async def on_socket_event_type(event_type) -> None:
            if (
                self.last_question_posted
                < datetime.now() - self.AUTOPOST_QUESTION_INTERVAL
            ):
                await self.post_random_oldest_question(event_type)

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
                callback=self.cb_set_status_by_review_request,
                args=[query, message],
                why=f"{message.author.name} asked for a review",
            )
        if query := self.is_response_to_review_request(message):
            return Response(
                confidence=8,
                callback=self.cb_set_status_by_approved,
                args=[query, message],
                why=f"{message.author.name} accepted the review",
            )
        if not (text := self.is_at_me(message)):
            coda_api.update_caches(on_interval=True)
            return Response()
        if query := PostOrCountQuestionQuery.parse(text):
            if query.action == "count":
                return Response(
                    confidence=8,
                    callback=self.cb_count_questions,
                    args=[query, message],
                    why="I was asked to count questions",
                )
            # get_question_query.action == "post":
            return Response(
                confidence=8,
                callback=self.cb_post_question,
                args=[query, message],
                why="I was asked for next questions",
            )
        if query := QuestionInfoQuery.parse(text, self.last_question_id):
            return Response(
                confidence=8,
                callback=self.cb_get_question_info,
                args=[query, message],
                why="I was asked to post info about a message",
            )
        if query := SetQuestionByMsgQuery.parse(text, self.last_question_id):
            return Response(
                confidence=8,
                callback=self.cb_set_status_by_msg,
                args=[query, message],
                why=f"I was asked to set status of question with id `{query.id}` to `{query.status}`",
            )
        return Response(
            why="Left QuestionManager without matching to any possible response"
        )

    ##################
    # Review request #
    ##################

    def is_review_request(
        self, message: ServiceMessage
    ) -> Optional[SetQuestionByAtOrReplyQuery]:
        """Is this message a review request with link do GDoc?"""
        text = message.clean_content

        if "@reviewer" in text:
            new_status = "In review"
        elif "@feedback-sketch" in text:
            new_status = "Bulletpoint sketch"
        elif "@feedback" in text:
            new_status = "In progress"
        else:
            return

        if not (gdoc_links := parse_gdoc_links(text)):
            return
        if not (questions := coda_api.get_questions_by_gdoc_links(gdoc_links)):
            return

        question_ids = [q["id"] for q in questions]
        self.review_msg_id2question_ids[message.id] = question_ids

        return SetQuestionByAtOrReplyQuery(question_ids, new_status)

    def is_response_to_review_request(
        self, message: ServiceMessage
    ) -> Optional[SetQuestionByAtOrReplyQuery]:
        """Is this message a response to review request?"""
        if (msg_ref := message.reference) is None:
            return
        if (
            msg_ref_id := str(getattr(msg_ref, "message_id", None))
        ) not in self.review_msg_id2question_ids:
            return

        text = message.clean_content
        if any(s in text.lower() for s in ["approved", "accepted", "lgtm"]):
            return SetQuestionByAtOrReplyQuery(
                self.review_msg_id2question_ids[cast(str, msg_ref_id)],
                "Live on site",
            )

    ####################
    # Post question(s) #
    ####################

    async def cb_post_question(
        self, query: PostOrCountQuestionQuery, message: ServiceMessage
    ) -> Response:
        """Post message to Discord for least recently asked question.
        It will contain question title and GDoc url.
        """
        # get questions df
        questions_df = coda_api.questions_df

        # if tags were specified, filter questions on those which have at least one of the tags
        if query.status:
            questions_df = questions_df.query("status == @query.status")
        else:
            questions_df = questions_df.query("status != 'Live on site'")
        if query.tag:
            questions = query.filter_on_tag(questions_df)

        # get all the oldest ones and shuffle them
        questions = shuffle_questions(questions_df)
        questions = get_least_recently_asked_on_discord(questions)

        # get exactly n questions (default is 1)
        questions = query.filter_on_max_num_of_questions(questions)

        # make question message and return response
        msg = query.next_result_info(len(questions))
        if not questions.empty:
            msg += "\n\n" + "\n---\n".join(
                make_post_question_message(cast(QuestionRow, r.to_dict()))
                for _, r in questions.iterrows()
            )

        # if there is only one question, remember that one
        if len(questions) == 1:
            self.last_question_id = questions.iloc[0]["id"]

        await message.channel.send(msg)

        # update Last Asked On Discord column
        current_time = datetime.now().isoformat()
        for question_id in questions["id"].tolist():
            coda_api.update_question_last_asked_date(question_id, current_time)

        self.last_question_posted = datetime.now()

        coda_api.update_caches()
        return Response(
            confidence=8,
            # text=msg,
            why=f"{message.author.name} asked me for next questions",
        )

    async def post_random_oldest_question(self, event_type) -> None:
        channel = cast(
            Thread,
            self.utils.client.get_channel(
                int(random.choice([editing_channel_id, general_channel_id]))
            ),
        )
        if channel is None:
            return
        q = cast(
            QuestionRow,
            get_least_recently_asked_on_discord(
                coda_api.questions_df.query("status == 'Not started'")
            )
            .iloc[0]
            .to_dict(),
        )
        self.last_question_id = q["id"]
        self.last_question_posted = datetime.now()
        coda_api.update_question_last_asked_date(q["id"], datetime.now().isoformat())
        msg = make_post_question_message(q)
        self.log.info(
            self.class_name,
            msg=f"Posting a random oldest question to the `#editing` channel because of {event_type}",
        )
        await channel.send(msg)
        coda_api.update_caches()

    ###################
    # Count questions #
    ###################

    async def cb_count_questions(
        self, query: PostOrCountQuestionQuery, message: ServiceMessage
    ) -> Response:
        """Post message to Discord about number of questions matching the query"""

        # get df with questions
        questions = coda_api.questions_df

        # if tags were specified, filter for questions which have at least one of these tags
        if query.status:
            questions = questions.query("status == @query.status")
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

    async def cb_get_question_info(
        self, query: QuestionInfoQuery, message: ServiceMessage
    ) -> Response:
        if query.type == "last" and query.query is None:
            return Response(
                confidence=8,
                text="There is no last question ;/",
                why=f"{message.author.name} asked me for last question but I haven't been asked for (or posted) any questions since I've been started",
            )
        questions = coda_api.questions_df
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

    async def cb_set_status_by_msg(
        self, query: SetQuestionByMsgQuery, message: ServiceMessage
    ) -> Response:
        if query.type == "last" and query.id is None:
            return Response(
                confidence=8,
                text='What do you mean by "it"?',
                why=dedent(
                    f"{message.author.name} asked me to set last question's status to {query.status} but I haven't posted any questions yet"
                ),
            )
        query_id = cast(str, query.id)
        question = coda_api.get_question_by_id(query_id)
        if response := unauthorized_set_los(query, [question], message):
            return response

        msg = f"Updated question's status to `{query.status}`"
        msg += "\n\nPreviously:\n" + pformat_to_codeblock(cast(dict, question))
        await message.channel.send(msg)
        coda_api.update_question_status(query_id, query.status)
        coda_api.update_caches()
        return Response(
            confidence=8,
            # text=msg,
            why=f"{message.author.name} asked me to set the status of questions with id `{query_id}` to `{query.status}`",
        )

    async def cb_set_status_by_review_request(
        self, query: SetQuestionByAtOrReplyQuery, message: ServiceMessage
    ) -> Response:
        id2question = coda_api.get_questions_by_ids(query.ids)
        id2status = {qid: q["status"] for qid, q in id2question.items()}
        if not is_from_reviewer(message) and "Live on site" in id2status.values():
            ids_los = [
                qid for qid, status in id2status.items() if status == "Live on site"
            ]
            one_los = len(ids_los) == 1
            msg_los = (
                f"{len(ids_los)} of these questions {'is' if one_los else 'are'} already `Live on site`. You can't change {'its' if one_los else 'their'} status because you're not a `@reviewer`.\n\nThese are:\n"
                + "\n".join(
                    f"{id2question[qid]['title']} ({id2question[qid]['url']})"
                    for qid in ids_los
                )
            )
            id2question = {
                qid: q for qid, q in id2question.items() if qid not in ids_los
            }
        else:
            msg_los = ""

        msg = f"Thanks, {message.author.name}!\n"
        if not id2question:
            msg += "I didn't updated any questions to "
        elif len(id2question) == 1:
            msg += "I updated status of 1 question to "
        else:
            msg += f"I updated status of {len(id2question)} questions to "
        msg += f"`{query.status}`" + msg_los

        await message.channel.send(msg)
        
        for qid, q in id2question.items():
            coda_api.update_question_status(qid, q["status"])

        self.log.info(self.class_name, msg=msg)
        coda_api.update_caches()
        return Response(
            confidence=8,
            # text=msg,
            why=f"{message.author.name} kindly asked for review"
        )

    async def cb_set_status_by_approved(
        self, query: SetQuestionByAtOrReplyQuery, message: ServiceMessage
    ) -> Response:
        if not is_from_reviewer(message):
            await message.channel.send(
                YOU_NOT_REVIEWER.format(author_name=message.author.name)
            )
        response_text = (
            "Approved! "
            + (
                "1 more question"
                if len(query.ids) == 1
                else f"{len(query.ids)} more questions"
            )
            + " `Live on site`"
        )
        await message.channel.send(response_text)
        for qid in query.ids:
            coda_api.update_question_status(qid, query.status)
        coda_api.update_caches()
        return Response(
            confidence=8,
            # text=response_text,
            why=f"{message.author.name} approved the questions posted for review",
        )

    #########
    # Other #
    #########

    @property
    def test_cases(self):
        if is_in_testing_mode():
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
        return "Questions Module"


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
        if (match := (re_pre.search(text) or re_post.search(text))) and (
            num := match.group(1)
        ).isdigit():
            return int(num)
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
        # if text contains neither "get", nor "info", it's not a request for getting question info
        if "get" not in text and "info" not in text:
            return
        # request to get question by ID
        if question_id := parse_id(text):
            return cls("id", question_id)
        # request to get question by its title (or substring fuzzily contained in title)
        if match := re.search(r"(?:question):?\s+([-\w\s]+)", text, re.I):
            question_title = match.group(1)
            return cls("title", question_title)
        # request to get last question
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
            return fuzzy_contains(question_row["title"], cast(str, self.query))
        return False


@dataclass(frozen=True)
class SetQuestionByMsgQuery:
    """Change status of a particular question."""

    type: Literal["id", "last"]
    """
    - "id" - specified by unique row identifier in "All Answers" table
    - "last" - ordered to get the last row that stampy interacted with
    (changed or posted) in isolation from other rows
    """
    id: Optional[str]  # TODO: adjust description and make comments in `parse`
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


@dataclass(frozen=True)
class SetQuestionByAtOrReplyQuery:
    """Sets question status when
    - Review request
        - Somebody mentions one of the roles (`@reviewer`, `@feedback`, `@feedback-sketch`)
        and posts a link to GDoc, triggering Stampy to change status of that question
        (to `In review`, `In progress`, `Bulletpoint sketch`, respectively)
    - Review approval
        - A user with `@reviewer` role responds to a review request with a message containing
        "accepted", "approved", or "lgtm" (case insensitive)
        -> questions's status changes to "Live on site"
    """

    ids: list[str]
    status: str


##################
# Util functions #
##################

# Parsing


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


def parse_id(text: str) -> Optional[str]:
    """Parse question id from message content"""
    # matches: "id: <question-id>"
    if match := re.search(r"id:?\s+([-\w]+)", text, re.I):
        return match.group(1)
    # matches: "i-<letters-and-numbers-unitl-word-boundary>" (i.e. question id)
    if match := re.search(r"(i-[\w\d]+)\b", text, re.I):
        return match.group(1)


def parse_gdoc_links(text: str) -> list[str]:
    """Extract GDoc links from message content.
    Returns `[]` if message doesn't contain any GDoc link.
    """
    return re.findall(r"https://docs\.google\.com/document/d/[\w_-]+", text)


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


def make_post_question_message(question_row: QuestionRow) -> str:
    """Make question message from questions DataFrame row

    <title>\n
    <url>
    """
    return question_row["title"] + "\n" + question_row["url"]


def unauthorized_set_los(
    query: Union[SetQuestionByMsgQuery, SetQuestionByAtOrReplyQuery],
    questions: list[QuestionRow],
    message: ServiceMessage,
) -> Optional[Response]:
    """Somebody tried set questions status "Live on site" but they're not a reviewer"""
    question_statuses = [q["status"] for q in questions]
    if "Live on site" not in (
        query.status,
        *question_statuses,
    ) or is_from_reviewer(message):
        return
    if query.status == "Live on site":
        response_msg = NOT_FROM_REVIEWER_TO_LIVE_ON_SITE.format(
            author_name=message.author.name
        )
        why = f"{message.author.name} wanted to change question status to `Live on site` but they're not a @reviewer"
    else:  # "Live on site" in question_statuses:
        response_msg = NOT_FROM_REVIEWER_FROM_LIVE_ON_SITE.format(
            author_name=message.author.name, query_status=query.status
        )
        why = f"{message.author.name} wanted to change status from `Live on site` but they're not a @reviewer"
    return Response(confidence=8, text=response_msg, why=why)


###############################
#   Big regexes and strings   #
###############################

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

NOT_FROM_REVIEWER_TO_LIVE_ON_SITE = """\
Sorry, {author_name}. You can't set question status to `Live on site` because you are not a `@reviewer`. 
Only `@reviewer`s can do thats."""

NOT_FROM_REVIEWER_FROM_LIVE_ON_SITE = """\
Sorry, {author_name}. You can't set status  to `{query_status}` because at least one of them is already `Live on site`. 
Only `@reviewer`s can change status of questions that are already `Live on site`."""

YOU_NOT_REVIEWER = "You're not a `@reviewer` {author_name}"
