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
import re
from typing import cast, Optional

from discord import Thread
from dotenv import load_dotenv

from api.coda import (
    CodaAPI,
    QuestionStatus,
    filter_on_tag,
    get_least_recently_asked_on_discord,
    make_status_and_tag_response_text,
)
from api.utilities.coda_utils import QuestionRow
from servicemodules.discordConstants import general_channel_id
from modules.module import Module, Response
from utilities.questions_utils import (
    QuestionFilterDataNT,
    parse_question_filter_data,
    parse_question_request_data,
    QuestionRequestData,
    parse_question_spec_data,
)
from utilities.utilities import is_in_testing_mode, pformat_to_codeblock
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
        if response := self.parse_get_question_info(text, message):
            return response
        return Response()

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
        if re_big_count_questions.search(text):
            filter_data = QuestionFilterDataNT(None, None, 1)
        elif re_count_questions.search(text):
            filter_data = parse_question_filter_data(text)
        else:
            return

        return Response(
            confidence=8,
            callback=self.cb_count_questions,
            args=[filter_data, message],
            why="I was asked to count questions",
        )

    async def cb_count_questions(
        self,
        filter_data: QuestionFilterDataNT,
        message: ServiceMessage,
    ) -> Response:
        """Post message to Discord about number of questions matching the query"""
        # get df with questions
        questions_df = coda_api.questions_df
        status, tag, _limit = filter_data

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
        request_data: QuestionRequestData
        if re_post_question.search(text):
            request_data = parse_question_request_data(text)
        elif re_big_next_question.search(text):
            request_data = "FilterData", QuestionFilterDataNT(None, None, 1)
        else:
            return
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
        if request_data[0] == "GDocLinks":
            text = (
                "Why don't you post "
                + ("it" if len(request_data[1]) == 1 else "them")
                + f" yourself, <@{message.author}>?"
            )
            return Response(
                confidence=10,
                text=text,
                why=f"If {message.author.name} has these links, they can surely post these question themselves",
            )
        # get questions (can be emptylist)
        questions = await coda_api.query_for_questions(
            request_data, message, get_least_recently_asked_unpublished=True
        )

        # get text and why (requires handling failures)
        text, why = await coda_api.get_questions_text_and_why(
            questions, request_data, message
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
            confidence=10,
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
        return s + make_status_and_tag_response_text(status, tag)

    # TODO: this should be on Rob's discord only
    async def post_random_oldest_question(self, event_type) -> None:
        """Post random oldest not started question.
        Triggered automatically six hours after non-posting any question
        (unless the last was already posted automatically using this method).
        """
        # choose randomly one of the two channels
        channel = cast(Thread, self.utils.client.get_channel(int(general_channel_id)))

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

    def parse_get_question_info(
        self, text: str, message: ServiceMessage
    ) -> Optional[Response]:
        """
        - Return `GetQuestionInfoCommand` if this a request to print info about a question of specific ID
        or title matching a specific substring
        - Return `GetLastQuestionInfoCommand` if this a request to print info about the last question
        Stampy interacted with
        - Return `None` otherwise
        """
        # if text contains neither "get", nor "info", it's not a request for getting question info #TODO: update
        # breakpoint()
        if not re_get_question_info.search(text):
            return
        if not (spec_data := parse_question_spec_data(text)):
            return
        return Response(
            confidence=10,
            callback=self.cb_get_question_info,
            args=[spec_data, message],
        )

    async def cb_get_question_info(
        self,
        request_data: QuestionRequestData,
        message: ServiceMessage,
    ) -> Response:
        """Get info about a question and post it as a dict in code block"""

        questions = await coda_api.query_for_questions(request_data, message)

        text, why = await coda_api.get_questions_text_and_why(
            questions, request_data, message
        )

        text += "\n"
        for q in questions:
            text += f"\n{pformat_to_codeblock(cast(dict, q))}"

        if request_data[0] == "Last":
            text += "\n\nquery: `last question`"
        else:
            text += f"\n\nquery: {pformat_to_codeblock(dict([request_data]))}"

        if len(questions) == 1:
            coda_api.last_question_id = questions[0]["id"]

        return Response(
            confidence=8,
            text=text,
            why=why,
        )

    #############
    #   Other   #
    #############

    @property
    def test_cases(self):
        if is_in_testing_mode():
            return []
        return [
            #########
            # Count #
            #########
            self.create_integration_test(
                test_message="how many questions?",
                expected_regex=r"There are \d{3,4} questions",
            ),
            self.create_integration_test(
                test_message="how many questions with status los?",
                expected_regex=r"There are \d{3} questions",
            ),
            self.create_integration_test(
                test_message="count questions tagged hedonium",
                expected_regex=r"There are \d\d? questions",
            ),
            ########
            # Info #
            ########
            self.create_integration_test(
                test_message="info t is it unethical", expected_regex="Here it is"
            ),
            self.create_integration_test(
                test_message="info https://docs.google.com/document/d/1Nzjn-Q_u44KMPzrg_fYE3B-7AqRFJOCfbYQ5HOp8svY/edit",
                expected_regex="Here it is",
            ),
            self.create_integration_test(
                test_message="i last", expected_regex="The last question"
            ),
            self.create_integration_test(
                test_message="info question hedonium",
                expected_regex="Here it is",
            ),
            # the next few should fail
            self.create_integration_test(
                test_message="info question asfdasdfasdfasdfasdasdasd",
                expected_regex="I found no question matching that title",
            ),
            self.create_integration_test(
                test_message="info https://docs.google.com/document/d/1Nzasdrg_fYE3B",
                expected_regex="These links don't lead",
            ),
            ########
            # Post #
            ########
            self.create_integration_test(
                test_message="get q https://docs.google.com/document/d/1Nzjn-Q_u44KMPzrg_fYE3B-7AqRFJOCfbYQ5HOp8svY/edit",
                expected_regex="Why don't you post it yourself,",
            ),
            self.create_integration_test(
                test_message="get questions https://docs.google.com/document/d/1Nzjn-Q_u44KMPzrg_fYE3B-7AqRFJOCfbYQ5HOp8svY/edit\nhttps://docs.google.com/document/d/1bnxJIy_iXOSjFw5UJUW1wfwwMAg5hUFNqDMq1T7Vrc0/edit",
                expected_regex="Why don't you post them yourself,",
            ),
            self.create_integration_test(
                test_message="post 5 questions tagged decision theory",
                expected_regex="Here are 5 questions tagged as `Decision Theory`",
            ),
            self.create_integration_test(
                test_message="post 5 questions with status los",
                expected_regex="Here are 5 questions with status `Live on site`",
            ),
            self.create_integration_test(
                test_message="post 5 questions tagged hedonium and with status w",
                expected_regex="I found no",
            ),
            self.create_integration_test(
                test_message="get question hedonium", expected_regex="Here it is"
            ),
            # This should fail
            self.create_integration_test(
                test_message="get questions https://docs.google.com/document/d/blablabla1\nhttps://docs.google.com/document/d/blablablabla2",
                expected_regex="Why don't you",
            ),
            # Next
            self.create_integration_test(
                test_message="next q",
                expected_regex=r"Here is a question\n\n[^\n]+\nhttps://docs",
            ),
            self.create_integration_test(
                test_message="what is the next question with status withdrawn and tagged doom",
                expected_regex=r"I found no|Here is a question",
            ),
            self.create_integration_test(
                test_message="next 2 questions tagged hedonium",
                expected_regex="Here are 2",
            ),
            ###############
            # Big regexes #
            ###############
            self.create_integration_test(
                test_message="give is another question",
                expected_regex="Here is a question",
            ),
            self.create_integration_test(
                test_message="how long is the question queue",
                expected_regex=r"There are \d{3,4} questions",
            ),
        ]

    def __str__(self):
        return "Questions Module"


##################
# Util functions #
##################


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
    return s + make_status_and_tag_response_text(status, tag)


def make_post_question_message(question_row: QuestionRow) -> str:
    """Make question message from questions DataFrame row

    <title>\n
    <url>
    """
    return question_row["title"] + "\n" + question_row["url"]


Text = Why = str


###########################
#   Regexes and strings   #
###########################

# TODO: update Commands.md after getting these regexes to their final form
re_post_question = re.compile(
    r"""
    (?:get|post|next) # get / post / next
    \s # whitespace char (obligatory)
    (?:\d+\s)? # optional number of questions
    (?:q|questions?|a|answers?) # q / question / questions / a / answer / answers
    """,
    re.I | re.X,
)
re_get_question_info = re.compile(r"i|info", re.I)
re_count_questions = re.compile(
    r"(?:count|how many|number of|n of|#) (?:q|questions|a|answers)", re.I
)


re_big_next_question = re.compile(
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
    question,? # next question (please)
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
    \s(question)?
    (\sfor\sus)?\??
)
!?
"""
)


re_big_count_questions = re.compile(
    r"""
(
    ( # how many questions are there left in ...
    how\s+many\s+questions\s*
    (are\s*(there\s*)?)?
    (left\s*)?
    (in\s+(your\s+|the\s+)?queue\s*)?
    )
|
    ( # how long is/'s the/your questions queue now
    how\s+
    (long\s+is|long's)\s+
    (the\s+|your\s+)?
    (question\s+)?
    queue
    (\s+now)?
    )
|
    (
    (\#|n|num)\s+(of\s+)?questions
    )
)
\?* # optional question mark
$   # end
""",
    re.X | re.I,
)
