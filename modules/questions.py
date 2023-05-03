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

from datetime import datetime, timedelta
import random
import re
from typing import Literal, Optional, TypedDict, Union, cast
from discord import Thread

from dotenv import load_dotenv
import pandas as pd

from api.coda import CodaAPI, QuestionStatus
from api.utilities.coda_utils import QuestionRow
from servicemodules.discordConstants import editing_channel_id, general_channel_id
from modules.module import Module, Response
from utilities.discordutils import DiscordChannel
from utilities.questions_utils import parse_gdoc_links, parse_status
from utilities.utilities import (
    fuzzy_contains,
    is_from_editor,
    is_from_reviewer,
    is_in_testing_mode,
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

        # Register `post_random_oldest_question` to be triggered every after 6 hours of no question posting
        @self.utils.client.event
        async def on_socket_event_type(event_type) -> None:
            if (
                self.last_question_posted
                < datetime.now() - self.AUTOPOST_QUESTION_INTERVAL
            ) and not self.last_question_autoposted:
                await self.post_random_oldest_question(event_type)

            if (
                coda_api.questions_cache_last_update
                < datetime.now() - coda_api.QUESTIONS_CACHE_UPDATE_INTERVAL
            ):
                coda_api.update_questions_cache()

    async def restore_review_msg_cache(
        self, channel: DiscordChannel, limit: int = 2000
    ) -> None:
        """#TODO: docstring"""
        self.log.info(
            self.class_name,
            msg="Empty `review_msg_id2question_ids` cache after reboot, restoring",
        )
        async for msg in channel.history(limit=limit):
            text = msg.clean_content
            if any(s in text for s in ["@feedback", "@reviewer"]) and (
                gdoc_links := parse_gdoc_links(text)
            ):
                questions = coda_api.get_questions_by_gdoc_links(gdoc_links)
                self.review_msg_id2question_ids[str(msg.id)] = [
                    q["id"] for q in questions
                ]
        self.log.info(
            self.class_name,
            msg=(
                f"Found {len(self.review_msg_id2question_ids)} "
                f"in the last {limit} messages in channel {channel.name}",
            ),
        )

    #########################################
    # Core: processing and posting messages #
    #########################################

    def process_message(self, message: ServiceMessage) -> Response:
        """Process message"""

        if not (text := self.is_at_me(message)):
            return Response()

        if cmd := self.parse_count_questions_command(text):
            return Response(
                confidence=8,
                callback=self.cb_count_questions,
                args=[cmd, message],
                why="I was asked to count questions",
            )
        if cmd := self.parse_post_questions_command(text):
            return Response(
                confidence=8,
                callback=self.cb_post_questions,
                args=[cmd, message],
                why="I was asked for next questions",
            )
        if cmd := self.parse_get_question_info_command(text, self.last_question_id):
            return Response(
                confidence=8,
                callback=self.cb_get_question_info,
                args=[cmd, message],
                why="I was asked to post info about a message",
            )
        return Response(
            why="Left QuestionManager without matching to any possible response"
        )


    ###################
    # Count questions #
    ###################

    def parse_count_questions_command(
        self, text: str
    ) -> Optional[CountQuestionsCommand]:
        """Returns `CountQuestionsCommand` if this message asks stampy to count questions,
        optionally, filtering for status and/or a tag.
        Returns `None` otherwise.
        """
        if not re_count_questions.search(text):
            return
        return {"status": parse_status(text), "tag": parse_tag(text)}

    async def cb_count_questions(
        self, cmd: CountQuestionsCommand, message: ServiceMessage
    ) -> Response:
        """Post message to Discord about number of questions matching the query"""
        # get df with questions
        questions_df = coda_api.questions_df

        # if status and/or tags were specified, filter accordingly
        if status := cmd["status"]:  # pylint:disable=unused-variable
            questions_df = questions_df.query("status == @status")
        if cmd["tag"]:
            questions_df = self.filter_on_tag(questions_df, cmd["tag"])

        # Make message and respond
        response_text = self.make_count_questions_result_response_text(
            cmd, len(questions_df)
        )

        return Response(
            confidence=8,
            text=response_text,
            why=f"{message.author.name} asked me to count questions",
        )

    def make_count_questions_result_response_text(
        self, cmd: CountQuestionsCommand, num_found: int
    ) -> str:
        """Generate response text for counting questions request"""
        if num_found == 1:
            s = "There is 1 question"
        elif num_found > 1:
            s = f"There are {num_found} questions"
        else:  # n_questions == 0:
            s = "There are no questions"
        return s + self.get_status_and_tags_info(cmd)

    ####################
    # Post question(s) #
    ####################

    def parse_post_questions_command(self, text: str) -> Optional[PostQuestionsCommand]:
        """Returns `PostQuestionsCommand` if this message asks Stampy to post questions,
        optionally, filtering for status and/or tag and/or maximum number of questions (capped at 5).
        Returns `None` otherwise.
        """

        if not re_next_question.search(text):
            return
        return {
            "status": parse_status(text),
            "tag": parse_tag(text),
            "max_num_of_questions": parse_max_num_of_questions(text),
        }

    async def cb_post_questions(
        self, cmd: PostQuestionsCommand, message: ServiceMessage
    ) -> Response:
        """Post message to Discord for least recently asked question.
        It will contain question title and GDoc url.
        """
        # get questions df
        questions_df = coda_api.questions_df
        # get channel
        channel = message.channel

        # if status was specified, filter questions for that status
        if status := cmd["status"]:  # pylint:disable=unused-variable
            questions_df = questions_df.query("status == @status")
        else:  # otherwise, filter for question that ain't Live on site
            questions_df = questions_df.query("status != 'Live on site'")
        # if tag was specified, filter for questions having that tag
        if cmd["tag"]:
            questions_df = self.filter_on_tag(questions_df, cmd["tag"])

        # get all the oldest ones and shuffle them
        questions_df = get_least_recently_asked_on_discord(questions_df)
        questions_df = shuffle_questions(questions_df)

        # get specified number of questions (default [if unspecified] is 1)
        if cmd["max_num_of_questions"] > 5:
            await channel.send(
                f"Let's not spam the channel with {cmd['max_num_of_questions']} "
                "questions. I'll give you up to 5."
            )

        # filter on max num of questions
        questions_df = self.filter_on_max_num_of_questions(
            questions_df, cmd["max_num_of_questions"]
        )

        # make question message and return response
        response_text = self.make_post_questions_result_response_text(cmd, len(questions_df))
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

    def make_post_questions_result_response_text(self, cmd: PostQuestionsCommand, num_found: int) -> str:
        """Generate response text for posting questions request"""
        max_num_of_questions = cmd["max_num_of_questions"]
        if num_found == 1:
            s = "Here is a question"
        elif num_found == 0:
            s = "I found no questions"
        elif num_found < max_num_of_questions:
            s = f"I found only {num_found} questions"
        else:
            s = f"Here are {max_num_of_questions} questions"
        return s + self.get_status_and_tags_info(cmd)

    async def post_random_oldest_question(self, event_type) -> None:
        """Post random oldest not started question.
        Triggered automatically six hours after non-posting any question
        (unless the last was already posted automatically using this method).
        """
        # choose randomly one of the two channels
        channel = cast(
            Thread,
            self.utils.client.get_channel(
                int(random.choice((editing_channel_id, general_channel_id)))
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
                "Posting a random oldest question to the channel because "
                f"Stampy hasn't posted anything for at least {self.AUTOPOST_QUESTION_INTERVAL}"
            ),
            channel_name=channel.name,
            event_type=event_type,
        )

        # send to channel
        await channel.send(make_post_question_message(question))

    #####################
    # Get question info #
    #####################

    def parse_get_question_info_command(
        self, text: str, last_question_id: Optional[str]
    ) -> GetQuestionInfoCommand | GetLastQuestionInfoCommand | None:
        """
        - Return `GetQuestionInfoCommand` if this a request to print info about a question of specific ID 
        or title matching a specific substring
        - Return `GetLastQuestionInfoCommand` if this a request to print info about the last question 
        Stampy interacted with
        - Return `None` otherwise
        """
        
        # if text contains neither "get", nor "info", it's not a request for getting question info
        if "get" not in text and "info" not in text:
            return
        
        # request to get question by ID
        if question_id := parse_id(text):
            return {"type": "title", "query": question_id}
        
        # request to get question by its title (or substring fuzzily contained in title)
        if match := re.search(r"(?:question):?\s+([-\w\s]+)", text, re.I):
            question_title = match.group(1)
            return {"type": "title", "query": question_title} # GetQuestionInfoCommand
        
        # request to get last question
        if "get last" in text or "get it" in text:
            return {"query": last_question_id} # GetLastQuestionInfoCommand

    async def cb_get_question_info(
        self,
        cmd: GetQuestionInfoCommand | GetLastQuestionInfoCommand,
        message: ServiceMessage,
    ) -> Response:
        """Get info about a question and post it as a dict in code block"""
        
        # early exit if asked for last question but there is no last question
        if cmd["query"] is None:  # possible only when cmd is GetLastQuestionInfoCommand
            return Response(
                confidence=8,
                text="I don't remember dealing with any questions since my last reboot",
                why=(
                    f"{message.author.name} asked me for last question but "
                    "I don't remember dealing any questions since my last reboot"
                ),
            )

        info = self.get_question_info_query_result(cmd)

        response_text = f"Here it is ({info}):\n\n"
        question_row = next(
            (
                q
                for _, q in coda_api.questions_df.iterrows()
                if self.matches_get_question_info_query(cmd, q)
            ),
            None,
        )
        if question_row is not None:
            self.last_question_id = question_row["id"]
            response_text += pformat_to_codeblock(question_row.to_dict())
        else:
            response_text = f"Couldn't find a question matching: {info}"

        return Response(
            confidence=8,
            text=response_text,
            why=f"{message.author.name} asked me to get the question with {info}",
        )

    @staticmethod
    def get_question_info_query_result(
        cmd: GetQuestionInfoCommand | GetLastQuestionInfoCommand,
    ) -> str:
        """Get a result saying how Stampy interpreted the query"""
        query = cmd["query"]

        # GetLastQuestionInfoCommand
        if "type" not in cmd:
            if query:
                return f"id `{query}` (last)"
            return "id `MISSING` (last)"

        # GetQuestionInfoCommand
        return f"{cmd.get('type')} `{query}`"

    @staticmethod
    def matches_get_question_info_query(
        cmd: GetQuestionInfoCommand | GetLastQuestionInfoCommand,
        question_row: pd.Series,
    ) -> bool:
        """Does this question (row from coda "All Answers" table)
        match this query?
        """
        if cmd.get("type") == "title":
            return fuzzy_contains(question_row["title"], cast(str, cmd["query"]))
        if cmd["query"]: 
            return question_row["id"].startswith(cmd["query"])
        return False


    #########
    # Other #
    #########

    @property
    def test_cases(self):
        if is_in_testing_mode():
            return []
        return [
            self.create_integration_test(
                test_message="next q", expected_regex=r"Here is a question\n\n[^\n]+\nhttps://docs"
            ),
            self.create_integration_test(
                test_message="how many questions?",
                expected_regex=r"There are \d{3,4} questions",
            ),
            self.create_integration_test(
                test_message="what is the next question with status withdrawn and tagged doom",
                expected_regex=r"I found no|Here is a question",
            ),
        ]

    def __str__(self):
        return "Questions Module"

    ################################
    # Filtering quetions DataFrame #
    ################################

    @staticmethod
    def filter_on_tag(questions: pd.DataFrame, tag: Optional[str]) -> pd.DataFrame:
        if tag is None:
            return questions

        def _contains_tag(tags: list[str]) -> bool:
            return any(t.lower() == cast(str, tag).lower() for t in tags)

        return questions[questions["tags"].map(_contains_tag)]

    @staticmethod
    def filter_on_max_num_of_questions(
        questions: pd.DataFrame, max_num_of_questions: int
    ) -> pd.DataFrame:
        """Filter on number of questions"""
        if questions.empty:
            return questions

        n = min(max_num_of_questions, 5, len(questions))
        questions = questions.sort_values(
            "last_asked_on_discord", ascending=False
        ).iloc[:n]

        return questions

    @staticmethod
    def get_status_and_tags_info(
        cmd: Union[CountQuestionsCommand, PostQuestionsCommand]
    ) -> str:
        """Print info about query's status and/or tags inline"""
        status, tag = cmd["status"], cmd["tag"]
        if status and tag:
            return f" with status `{status}` and tagged as `{tag}`"
        if status:
            return f" with status `{status}`"
        if tag:
            return f" tagged as `{tag}`"
        return ""


##########################
#   Command TypedDicts   #
##########################




class PostQuestionsCommand(TypedDict):
    """Post questions matching `status` and `tag`"""

    status: Optional[str]
    tag: Optional[str]
    max_num_of_questions: int


class CountQuestionsCommand(TypedDict):
    """Count questions matching `status` and `tag`"""

    status: Optional[str]
    tag: Optional[str]


class GetQuestionInfoCommand(TypedDict):
    """Get info about particular question

    If `type` is "id", `query` also must be question's id.
    Same when type is `last`, although in that case, Stampy may have not
    interacted with any questions, since its most recent start, which means that
    `query` is `None`. Stampy handles that case gracefully. If `type` is "title",
    Stampy looks up the first question with title that `contains` `query`
    (`query` fuzzily matches some substring of `title`).
    """

    type: Literal["id", "title"]
    query: str


class GetLastQuestionInfoCommand(TypedDict):
    """Get info about particular question

    If `type` is "id", `query` also must be question's id.
    Same when type is `last`, although in that case, Stampy may have not
    interacted with any questions, since its most recent start, which means that
    `query` is `None`. Stampy handles that case gracefully. If `type` is "title",
    Stampy looks up the first question with title that `contains` `query`
    (`query` fuzzily matches some substring of `title`).
    """

    query: Optional[str]



##################
# Util functions #
##################

# Parsing



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


def parse_max_num_of_questions(text: str) -> int:
    re_pre = re.compile(r"(\d{1,2})\sq(?:uestions?)?", re.I)
    re_post = re.compile(r"n\s?=\s?(\d{1,2})", re.I)
    if (match := (re_pre.search(text) or re_post.search(text))) and (
        num := match.group(1)
    ).isdigit():
        return int(num)
    return 1


def parse_id(text: str) -> Optional[str]:
    """Parse question id from message content"""
    # matches: "id: <question-id>"
    if match := re.search(r"\sid:?\s+([-\w]+)", text, re.I):
        return match.group(1)
    # matches: "i-<letters-and-numbers-unitl-word-boundary>" (i.e. question id)
    if match := re.search(r"(i-[\w\d]+)\b", text, re.I):
        return match.group(1)

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
