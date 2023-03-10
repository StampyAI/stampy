"""Test these functionalities before PR
- Posting next questions
    - Vary num, status, and tag
- Counting questions
    - Vary status and tag
- Getting info about questions
    - Vary id/last/title
- Asking for feedback
    - Vary whether you're a `@reviewer`, number of questions, 
    number of already `Live on site` questions
- Accepting feedback request
    - Vary whether you're a `@reviewer` and number of questions
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import random
import re
from textwrap import dedent
from typing import Any, Literal, Optional, cast

from dotenv import load_dotenv
from discord.threads import Thread
import pandas as pd
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
        self.last_question_autoposted = False
        self.class_name = "Questions Module"

        # Register `post_random_oldest_question` to be triggered every after 6 hours of no question posting
        @self.utils.client.event
        async def on_socket_event_type(event_type) -> None:
            if (
                self.last_question_posted
                < datetime.now() - self.AUTOPOST_QUESTION_INTERVAL
            ) and not self.last_question_autoposted :
                await self.post_random_oldest_question(event_type)

            if (
                coda_api.questions_cache_last_update
                < datetime.now() - coda_api.QUESTIONS_CACHE_UPDATE_INTERVAL
            ):
                coda_api.update_questions_cache()

    #########################################
    # Core: processing and posting messages #
    #########################################

    def process_message(self, message: ServiceMessage) -> Response:
        """Process message"""
        # these two options are before `.is_at_me`
        # because they dont' require calling Stampy explicitly ("s, XYZ")
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
        # get channel
        channel = cast(Thread, message.channel)

        # if status was specified, filter questions for that status
        if query.status:
            questions_df = questions_df.query("status == @query.status")
        else:  # otherwise, filter for question that ain't Live on site
            questions_df = questions_df.query("status != 'Live on site'")
        # if tag was specified, filter for questions having that tag
        if query.tag:
            questions_df = query.filter_on_tag(questions_df)

        # get all the oldest ones and shuffle them
        questions_df = get_least_recently_asked_on_discord(questions_df)
        questions_df = shuffle_questions(questions_df)

        # get specified number of questions (default [if unspecified] is 1)
        if query.max_num_of_questions > 5:
            await channel.send(
                f"Let's not spam the channel with {query.max_num_of_questions} "
                "questions. I'll give you up to 5."
            )

        # filter on max num of questions
        questions_df = query.filter_on_max_num_of_questions(questions_df)

        # make question message and return response
        response_text = query.post_result_info(len(questions_df))
        if not questions_df.empty:
            response_text += "\n\n" + "\n---\n".join(
                make_post_question_message(cast(QuestionRow, r.to_dict()))
                for _, r in questions_df.iterrows()
            )

        # update Last Asked On Discord column
        current_time = datetime.now()
        for question_id in questions_df["id"].tolist():
            coda_api.update_question_last_asked_date(question_id, current_time)

        # update caches
        self.last_question_posted = current_time
        self.last_question_autoposted = False
        # if there is only one question, cache its ID
        if len(questions_df) == 1:
            self.last_question_id = questions_df.iloc[0]["id"]

        return Response(
            confidence=8,
            text=response_text,
            why=f"{message.author.name} asked me for next questions",
        )

    async def post_random_oldest_question(self, event_type) -> None:
        """Post random oldest not started question.
        Triggered automatically six hours after non-posting any question.
        """
        # choose randomly one of the two channels
        channel = cast(
            Thread,
            self.utils.client.get_channel(
                int(random.choice([editing_channel_id, general_channel_id]))
            ),
        )
        # get random question with status Not started
        questions_df_filtered = coda_api.questions_df.query("status == 'Not started'")
        questions_df_filtered = questions_df_filtered[
            questions_df_filtered["tags"].map(lambda tags: "Stampy" not in tags)
        ]
        question = cast(
            QuestionRow,
            get_least_recently_asked_on_discord(questions_df_filtered)
            .iloc[0]
            .to_dict(),
        )

        # update in coda
        current_time = datetime.now()
        coda_api.update_question_last_asked_date(question["id"], current_time)

        # update caches
        self.last_question_id = question["id"]
        self.last_question_posted = current_time
        self.last_question_autoposted = True

        # log
        self.log.info(
            self.class_name,
            msg=(
                "Posting a random oldest question to the `#editing` channel because "
                f"I haven't posted anything for at least {self.AUTOPOST_QUESTION_INTERVAL}"
            ),
            event_type=event_type,
        )

        # send to channel
        await channel.send(make_post_question_message(question))


    ###################
    # Count questions #
    ###################

    async def cb_count_questions(
        self, query: PostOrCountQuestionQuery, message: ServiceMessage
    ) -> Response:
        """Post message to Discord about number of questions matching the query"""

        # get df with questions
        questions_df = coda_api.questions_df

        # if status and/or tags were specified, filter accordingly
        if query.status:
            questions_df = questions_df.query("status == @query.status")
        if query.tag:
            questions_df = query.filter_on_tag(questions_df)

        # Make message and respond
        msg = query.count_result_info(len(questions_df))

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
        """Get info about a question and post it as a dict in code block"""
        # early exit if asked for last question but there is no last question
        if query.query is None:  # possible only when query.type == "last"
            return Response(
                confidence=8,
                text="I don't remember dealing with any questions since my last reboot",
                why=(
                    f"{message.author.name} asked me for last question but "
                    "I don't remember dealing any questions since my last reboot"
                ),
            )

        response_text = f"Here it is ({query.info()}):\n\n"
        question_row = next(
            (q for _, q in coda_api.questions_df.iterrows() if query.matches(q)), None
        )
        if question_row is not None:
            self.last_question_id = question_row["id"]
            response_text += pformat_to_codeblock(question_row.to_dict())
        else:
            response_text = "Couldn't find a question matching " + query.info()

        return Response(
            confidence=8,
            text=response_text,
            why=f"{message.author.name} asked me to get the question with "
            + query.info(),
        )

    ##############
    # Set status #
    ##############

    async def cb_set_status_by_msg(
        self, query: SetQuestionByMsgQuery, message: ServiceMessage
    ) -> Response:
        """Set question status by telling Stampy

        ```
        s, set it to <some status>
        # or
        s, set <question id> to <some status>
        ```
        """
        # early exit if asked for last question but there is no last question
        if query.id is None:  # possible only when query.type == "last"
            mention = "it" if "it" in message.clean_content else "last"
            return Response(
                confidence=8,
                text=f'What do you mean by "{mention}"?',
                why=dedent(
                    (
                        f"{message.author.name} asked me to set last question's status "
                        f"to {query.status} but I haven't posted any questions yet"
                    )
                ),
            )

        question = coda_api.get_question_row(query.id)

        # early exit if a non-`@reviewer` asked for changing status from or to "Live on site"
        if response := unauthorized_set_los(query, question, message):
            return response

        coda_api.update_question_status(query.id, query.status)
        self.last_question_id = query.id

        response_text = "Ok!"
        if query.type == "last":
            response_text += f'\n"{question["title"]}" is now `{query.status}`.'
        else:  # query.type == "id":
            response_text += f" It's `{query.status}` now."

        return Response(
            confidence=8,
            text=response_text,
            why=(
                f"{message.author.name} asked to update status of question "
                f"with id `{query.id}` to `{query.status}`"
            ),
        )

    async def cb_set_status_by_review_request(
        self, query: SetQuestionByAtOrReplyQuery, message: ServiceMessage
    ) -> Response:
        """Change question status by posting GDoc link(s) for review
        along with one of the mentions:
        `@reviewer` or `@feedback` or `@feedback-sketch`
        """
        channel = cast(Thread, message.channel)

        # pre-send message to confirm that you're going to update statuses
        await channel.send(
            f"Thanks, {message.author.name}! I'll update "
            + ("their" if len(query.ids) > 1 else "its")
            + f" status to `{query.status}`"
        )
        # map question IDs to QuestionRows
        id2question = {qid: coda_api.get_question_row(qid) for qid in query.ids}
        # store IDs of questions that are already "Live on site" here
        already_los_qids = []

        # update
        for qid, question in id2question.items():
            if question["status"] == "Live on site" and not is_from_reviewer(message):
                already_los_qids.append(qid)
            else:
                coda_api.update_question_status(qid, query.status)

        # make message
        n_updated = len(id2question) - len(already_los_qids)
        if n_updated == 0:
            response_text = "I didn't update any questions"
        elif n_updated == 1:
            response_text = "I updated 1 question"
            # update last_question_id if only 1 question was updated
            updated_question_id = next(
                qid for qid in id2question if qid not in already_los_qids
            )
            self.last_question_id = updated_question_id
        else:
            response_text = f"I updated {n_updated} questions"
        response_text += f" to `{query.status}`"

        if already_los_qids:
            if len(already_los_qids) == 1:
                response_text += (
                    "\n\nOne question is already `Live on site`, so I didn't change it."
                )
            else:
                response_text += f"\n\n{len(already_los_qids)} questions are already `Live on site`, so I didn't change them."
            response_text += " You need to be a `@reviewer` to change the status of questions that are already `Live on site`.\n\n"
            response_text += "\n".join(
                f"- {id2question[qid]['title']} ({id2question[qid]['url']})"
                for qid in already_los_qids
            )

        return Response(
            confidence=8,
            text=response_text,
            why=f"{message.author.name} asked for review",
        )

    async def cb_set_status_by_approved(
        self, query: SetQuestionByAtOrReplyQuery, message: ServiceMessage
    ) -> Response:
        """Approve questions posted as GDoc links for review (see above).
        Their status is changed to "Live on site".
        Works for `@reviewer`s only.
        """
        # early exit if it's not from a `@reviewer`
        if not is_from_reviewer(message):
            return Response(
                confidence=8,
                text=f"You're not a `@reviewer` {message.author.name}",
                why=(
                    f"{message.author.name} tried accepting a review request "
                    "but they're not a `@reviewer`"
                ),
            )

        # pre-send message to confirm that you're going to update statuses
        channel = cast(Thread, message.channel)
        await channel.send(f"Approved by {message.author.name}!")

        # update question statuses
        for qid in query.ids:
            coda_api.update_question_status(qid, query.status)

        if len(query.ids) == 1:
            response_text = "1 more question goes"
        else:
            response_text = f"{len(query.ids)} more questions go"
        response_text += " `Live on site`!"

        return Response(
            confidence=8,
            text=response_text,
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
        if action == "post":
            max_num_of_questions = cls.parse_max_num_of_questions(text)
        else:
            max_num_of_questions = 1

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
        n = min(self.max_num_of_questions, 5, len(questions))
        questions = questions.sort_values(
            "last_asked_on_discord", ascending=False
        ).iloc[:n]
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

    def post_result_info(self, num_found: int) -> str:
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
    if match := re.search(r"\sid:?\s+([-\w]+)", text, re.I):
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
    # pylint:disable=unused-variable
    oldest_date = questions["last_asked_on_discord"].min()
    return questions.query("last_asked_on_discord == @oldest_date")


def make_post_question_message(question_row: QuestionRow) -> str:
    """Make question message from questions DataFrame row

    <title>\n
    <url>
    """
    return question_row["title"] + "\n" + question_row["url"]


def unauthorized_set_los(
    query: SetQuestionByMsgQuery,
    question: QuestionRow,
    message: ServiceMessage,
) -> Optional[Response]:
    """Somebody tried set questions status "Live on site" but they're not a reviewer"""
    if "Live on site" not in (
        query.status,
        question["status"],
    ) or is_from_reviewer(message):
        return
    if query.status == "Live on site":
        response_msg = NOT_FROM_REVIEWER_TO_LIVE_ON_SITE.format(
            author_name=message.author.name
        )
        why = (
            f"{message.author.name} wanted to change question status "
            "to `Live on site` but they're not a @reviewer"
        )
    else:  # "Live on site" in question_statuses:
        response_msg = NOT_FROM_REVIEWER_FROM_LIVE_ON_SITE.format(
            author_name=message.author.name, query_status=query.status
        )
        why = (
            f"{message.author.name} wanted to change status from "
            "`Live on site` but they're not a @reviewer"
        )
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
