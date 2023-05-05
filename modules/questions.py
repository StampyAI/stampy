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
from typing import cast, Optional

from discord import Thread
from dotenv import load_dotenv
import pandas as pd

from api.coda import CodaAPI, QuestionStatus
from api.utilities.coda_utils import QuestionRow
from servicemodules.discordConstants import editing_channel_id, general_channel_id
from modules.module import Module, Response
from utilities.questions_utils import (
    parse_question_filter_data,
    parse_question_request_data,
    QuestionFilterData,
    QuestionRequestData,
)
from utilities.utilities import is_in_testing_mode, pformat_to_codeblock, shuffle_df
from utilities.serviceutils import ServiceMessage


load_dotenv()

coda_api = CodaAPI.get_instance()
status_shorthands = coda_api.get_status_shorthand_dict()
all_tags = coda_api.get_all_tags()

Text = Why = str


class Questions(Module):
    """Fetches not started questions from
    [All Answers](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a)
    """

    AUTOPOST_QUESTION_INTERVAL = timedelta(hours=6)

    def __init__(self) -> None:
        super().__init__()
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

    def process_message(self, message: ServiceMessage) -> Response:
        """Process message"""

        if not (text := self.is_at_me(message)):
            return Response()
        if response := self.parse_count_questions_command(text, message):
            return response
        if response := self.parse_post_questions_command(text, message):
            return response
        if response := self.parse_get_question_info_command(text, message):
            return response
        return Response(
            why="Left QuestionManager without matching to any possible response"
        )

    ###################
    # Count questions #
    ###################

    def parse_count_questions_command(
        self,
        text: str,
        message: ServiceMessage,
    ) -> Optional[Response]:
        """Returns `CountQuestionsCommand` if this message asks stampy to count questions,
        optionally, filtering for status and/or a tag.
        Returns `None` otherwise.
        """
        if not re_count_questions.search(text):
            return

        filter_data = parse_question_filter_data(text)
        return Response(
            confidence=8,
            callback=self.cb_count_questions,
            args=[filter_data, message],
            why="I was asked to count questions",
        )

    async def cb_count_questions(
        self,
        filter_data: QuestionFilterData,
        message: ServiceMessage,
    ) -> Response:
        """Post message to Discord about number of questions matching the query"""
        # get df with questions
        status = filter_data["status"]
        tag = filter_data["tag"]
        questions_df = coda_api.questions_df

        # if status and/or tags were specified, filter accordingly
        if status:
            questions_df = questions_df.query("status == @status")
        if tag:
            questions_df = filter_on_tag(questions_df, tag)

        # Make message and respond
        response_text = make_count_questions_response_text(
            status, tag, len(questions_df)
        )

        return Response(
            confidence=8,
            text=response_text,
            why=f"{message.author.name} asked me to count questions",
        )

    ######################
    #   Post questions   #
    ######################

    def parse_post_questions_command(
        self, text: str, message: ServiceMessage
    ) -> Optional[Response]:
        """Returns `PostQuestionsCommand` if this message asks Stampy to post questions,
        optionally, filtering for status and/or tag and/or maximum number of questions (capped at 5).
        Returns `None` otherwise.
        """
        if not re_next_question.search(text):
            return
        request_data = parse_question_request_data(text)
        return Response(
            confidence=8,
            callback=self.cb_post_questions,
            args=[request_data, message],
        )

    async def cb_post_questions(
        self,
        request_data: QuestionRequestData,
        message: ServiceMessage,
    ) -> Response:
        """Post message to Discord for least recently asked question.
        It will contain question title and GDoc url.
        """

        questions, text, why = await self.find_questions_for_post_or_get(
            request_data, message
        )

        current_time = datetime.now()
        text += "\n"
        for q in questions:
            text += f"\n{make_post_question_message(q)}"
            coda_api.update_question_last_asked_date(q["id"], current_time)

        # update caches
        self.last_question_posted = current_time
        self.last_question_autoposted = False

        # if there is only one question, cache its ID
        if len(questions) == 1:
            coda_api.last_question_id = questions[0]["id"]

        return Response(
            confidence=8,
            text=text,
            why=why,
        )

    def make_post_questions_result_response_text(
        self,
        status: Optional[QuestionStatus],
        tag: Optional[str],
        max_num_of_questions: int,
        num_found: int,
    ) -> str:
        """Generate response text for posting questions request"""
        if num_found == 1:
            s = "Here is a question"
        elif num_found == 0:
            s = "I found no questions"
        elif num_found < max_num_of_questions:
            s = f"I found only {num_found} questions"
        else:
            s = f"Here are {max_num_of_questions} questions"
        return s + make_status_and_tags_response_text(status, tag)

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
        coda_api.last_question_id = question["id"]
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

    #########################
    #   Get question info   #
    #########################

    def parse_get_question_info_command(
        self, text: str, message: ServiceMessage
    ) -> Optional[Response]:
        """
        - Return `GetQuestionInfoCommand` if this a request to print info about a question of specific ID
        or title matching a specific substring
        - Return `GetLastQuestionInfoCommand` if this a request to print info about the last question
        Stampy interacted with
        - Return `None` otherwise
        """

        # if text contains neither "get", nor "info", it's not a request for getting question info
        if "info" not in text:  # TODO: better regex for this command
            return

        request_data = parse_question_request_data(text)
        return Response(
            confidence=10,
            callback=self.cb_get_question_info,
            args=[request_data, message],
        )

    async def cb_get_question_info(
        self,
        request_data: QuestionRequestData,
        message: ServiceMessage,
    ) -> Response:
        """Get info about a question and post it as a dict in code block"""

        questions, text, why = await self.find_questions_for_post_or_get(
            request_data, message
        )

        text += "\n"
        for q in questions:
            text += f"\n{pformat_to_codeblock(cast(dict, q))}"

        if "mention" in request_data:
            text += "\n\nquery: `last question`"
        else:
            text += f"\n\nquery: {pformat_to_codeblock(cast(dict, request_data))}"

        if len(questions) == 1:
            coda_api.last_question_id = questions[0]["id"]

        return Response(
            confidence=8,
            text=text,
            why=why,
        )

    ######################################
    #   find_questions_for_post_or_get   #
    ######################################

    async def find_questions_for_post_or_get(
        self, request_data: QuestionRequestData, message: ServiceMessage
    ) -> tuple[list[QuestionRow], Text, Why]:
        # get questions df
        questions_df = coda_api.questions_df

        if question_id := request_data.get("question_id"):
            question = coda_api.get_question_row(question_id)
            if question is None:
                return (
                    [],
                    f"There are no questions matching ID `{question_id}`",
                    f"{message.author.name} wanted me to get a question matching ID `{question_id}` but I found nothing",
                )
            return (
                [question],
                "Here it is!",
                f"{message.author.name} wanted me to get a question matching ID `{question_id}`",
            )
        if gdoc_links := request_data.get("gdoc_links", []):
            questions = coda_api.get_questions_by_gdoc_links(gdoc_links)
            if not questions:
                return (
                    [],
                    "These links don't lead to any questions",
                    f"{message.author.name} gave me some links but they don't lead to any questions in my database",
                )
            return (
                questions,
                "Here it is:" if len(questions) == 1 else "Here they are:",
                f"{message.author.name} wanted me to get these questions",
            )
        if question_title := request_data.get("question_title"):
            question = coda_api.get_question_by_title(question_title)
            if question is None:
                return (
                    [],
                    "I found no question matching that title",
                    f'{message.author.name} asked for a question with title matching "{question_title}" but I found nothing ;_;',
                )
            return (
                [question],
                f"Here it is:\n\"{question['title']}\"",
                f'{message.author.name} wanted me to get a question with title matching "{question_title}"',
            )
        if mention := request_data.get("mention"):
            if coda_api.last_question_id is None:
                return (
                    [],
                    f'What do you mean by "{mention}"?',
                    f"{message.author.name} asked me to post the last question but I don't know what they're talking about",
                )
            question = cast(
                QuestionRow, coda_api.get_question_row(coda_api.last_question_id)
            )
            text = f"The last question was:\n\"{question['title']}\""
            why = f"{message.author.name} wanted me to get the last question"
            return [question], text, why

        ######################
        # QuestionFilterData #
        ######################

        filter_data = cast(QuestionFilterData, request_data)
        # if status was specified, filter questions for that status
        if status := filter_data["status"]:  # pylint:disable=unused-variable
            questions_df = questions_df.query("status == @status")
        else:  # otherwise, filter for question that ain't Live on site
            questions_df = questions_df.query("status != 'Live on site'")
        # if tag was specified, filter for questions having that tag
        questions_df = filter_on_tag(questions_df, filter_data["tag"])

        # get all the oldest ones and shuffle them
        questions_df = get_least_recently_asked_on_discord(questions_df)
        questions_df = shuffle_df(questions_df)

        limit = min(filter_data["limit"], 5)

        # get specified number of questions (default [if unspecified] is 1)
        if (limit := filter_data["limit"]) > 5:
            await message.channel.send(f"{limit} is to much. I'll give you up to 5.")

        n = min(limit, 5)
        # filter on max num of questions
        questions_df = questions_df.sort_values(
            "last_asked_on_discord", ascending=False
        ).iloc[:n]
        status_and_tags_response_text = make_status_and_tags_response_text(
            status, filter_data["tag"]
        )
        if questions_df.empty:
            return (
                [],
                f"I found no questions{status_and_tags_response_text}",
                f"{message.author.name} asked me for questions{status_and_tags_response_text} but I found nothing",
            )
        questions = cast(list[QuestionRow], questions_df.to_dict(orient="records"))
        if len(questions) == 1:
            text = f"I found one question{status_and_tags_response_text}"
        else:
            text = f"I found {len(questions)} questions{status_and_tags_response_text}"
        return (
            questions,
            text,
            f"{message.author.name} asked me for questions{status_and_tags_response_text} and I found {len(questions)}",
        )

    #############
    #   Other   #
    #############

    @property
    def test_cases(self):
        if is_in_testing_mode():
            return []
        return [
            self.create_integration_test(
                test_message="next q",
                expected_regex=r"Here is a question\n\n[^\n]+\nhttps://docs",
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


##################
# Util functions #
##################


def get_least_recently_asked_on_discord(
    questions: pd.DataFrame,
) -> pd.DataFrame:
    """Get all questions with oldest date and shuffle them"""
    # pylint:disable=unused-variable
    oldest_date = questions["last_asked_on_discord"].min()
    return questions.query("last_asked_on_discord == @oldest_date")


def make_count_questions_response_text(
    status: Optional[QuestionStatus], tag: Optional[str], num_found: int
) -> str:
    """Generate response text for counting questions request"""
    if num_found == 1:
        s = "There is 1 question"
    elif num_found > 1:
        s = f"There are {num_found} questions"
    else:  # n_questions == 0:
        s = "There are no questions"
    return s + make_status_and_tags_response_text(status, tag)


def make_post_question_message(question_row: QuestionRow) -> str:
    """Make question message from questions DataFrame row

    <title>\n
    <url>
    """
    return question_row["title"] + "\n" + question_row["url"]


def make_status_and_tags_response_text(
    status: Optional[QuestionStatus],
    tag: Optional[str],
) -> str:
    """Print info about query's status and/or tags inline"""
    if status and tag:
        return f" with status `{status}` and tagged as `{tag}`"
    if status:
        return f" with status `{status}`"
    if tag:
        return f" tagged as `{tag}`"
    return ""


def filter_on_tag(questions_df: pd.DataFrame, tag: Optional[str]) -> pd.DataFrame:
    if tag is None:
        return questions_df

    def _contains_tag(tags: list[str]) -> bool:
        return any(t.lower() == cast(str, tag).lower() for t in tags)

    return questions_df[questions_df["tags"].map(_contains_tag)]


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
