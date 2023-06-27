"""
Querying question database

How many questions, Count questions
Count questions, optionally queried by status and/or tag
`s, count questions [with status <status>] [tagged <tag>]`

Get question, Post question, Next question
Post links to one or more questions
`s, <get/post/next> [num-of-questions] question(s) [with status <status>] [tagged <tag>]` - filter by status and/or tags and/or specify maximum number of questions (up to 5)
`s, <get/post/next> question` - post next question with status `Not started`
`s, <get/post/next> question <question-title>` - post question fuzzily matching that title

Question info
Get info about question, printed in a codeblock
`s, <info> question <question-title>` - filter by title (fuzzy matching)
`s, <info>` - get info about last question
`s, <info> <gdoc-link>` - get tinfo about the question under that GDoc link

Refresh questions, Reload questions
Refresh bot's questions cache so that it's in sync with coda. (Only for bot devs and editors/reviewers)
`s, <refresh/reload> questions`
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
import random
import re
from typing import cast, Optional

from dateutil.relativedelta import relativedelta, MO
from discord import Thread
from dotenv import load_dotenv
import pandas as pd

from api.coda import (
    CodaAPI,
    filter_on_tag,
    get_least_recently_asked_on_discord,
)
from api.utilities.coda_utils import REVIEW_STATUSES, QuestionRow, QuestionStatus
from config import coda_api_token, is_rob_server
from servicemodules.discordConstants import (
    general_channel_id,
    stampy_dev_priv_channel_id,
)
from modules.module import Module, Response
from utilities.help_utils import ModuleHelp
from utilities.utilities import (
    has_permissions,
    is_in_testing_mode,
    pformat_to_codeblock,
)
from utilities.serviceutils import ServiceMessage


if coda_api_token is not None:
    from utilities.question_query_utils import (
        parse_question_filter,
        parse_question_query,
        parse_question_spec_query,
        QuestionFilterNT,
        QuestionQuery,
    )


load_dotenv()


class Questions(Module):
    @staticmethod
    def is_available() -> bool:
        return coda_api_token is not None and not is_in_testing_mode()

    def __init__(self) -> None:
        if not self.is_available():
            exc_msg = f"Module {self.class_name} is not available."
            if coda_api_token is None:
                exc_msg += " CODA_API_TOKEN is not set in `.env`."
            if is_in_testing_mode():
                exc_msg += " Stampy is in testing mode right now."
            raise Exception(exc_msg)

        super().__init__()
        self.help = ModuleHelp.from_docstring(self.class_name, __doc__)
        self.coda_api = CodaAPI.get_instance()

        ###################
        #   Autoposting   #
        ###################

        # How often Stampy posts random not started questions to `#general`
        self.not_started_question_autopost_interval = timedelta(hours=6)

        # Time when last question was posted
        self.last_question_posted_dt = (
            datetime.now() - self.not_started_question_autopost_interval / 2
        )

        # Was the last question that was posted, a not started question autoposted
        self.last_question_posted_was_not_started_autoposted = False

        # Date of last autopost of abandoned question
        self.last_abandoned_autopost_date: date = get_last_monday().date()

        # Max number of abandoned questions to be autoposted
        self.abandoned_autopost_limit: int = 5

        if is_rob_server:
            @self.utils.client.event  # fmt:skip
            async def on_socket_event_type(_event_type) -> None:
                if self.is_time_for_autopost_not_started():
                    await self.autopost_not_started()
                if self.is_time_for_autopost_abandoned():
                    await self.autopost_abandoned()

        ###############
        #   Regexes   #
        ###############

        self.re_post_question = re.compile(
            r"""
            (?:get|post|next) # get / post / next
            \s # whitespace char (obligatory)
            (?:\d+\s)? # optional number of questions
            (?:q|questions?|a|answers?|it|last)
            # q / question / questions / a / answer / answers / it / last
            """,
            re.I | re.X,
        )
        self.re_get_question_info = re.compile(r"(?:i|info|get info)\b", re.I)
        self.re_count_questions = re.compile(
            r"(?:count|how many|number of|n of|#) (?:q|questions|a|answers)", re.I
        )
        self.re_big_next_question = re.compile(  # TODO: this matches just "a question"
            r"(([wW]hat(’|'| i)?s|([Cc]an|[Mm]ay) (we|[iI]) (have|get)|[Ll]et[’']?s have|[gG]ive us)"
            r"?( ?[Aa](nother)?|( the)? ?[nN]ext) question,?( please)?\??|([Dd]o you have|([Hh]ave you )"
            r"?[gG]ot)?( ?[Aa]ny( more| other)?| another) questions?( for us)?\??)!?"
        )
        self.re_big_count_questions = re.compile(
            r"([hH]ow many questions (are (there )?)?(left )?in)|([hH]ow "
            r"(long is|long's)) (the|your)( question)? queue( now)?\??",
        )
        self.re_refresh_questions = re.compile(
            r"(reload|fetch|load|update|refresh)(\s+new)?\s+q(uestions)?", re.I
        )

    def process_message(self, message: ServiceMessage) -> Response:
        if not (text := self.is_at_me(message)):
            return Response()
        if text == "hardreload questions":
            return Response(
                confidence=9, callback=self.cb_hardreload_questions, args=[message]
            )
        if self.re_refresh_questions.match(text):
            return Response(
                confidence=9, callback=self.cb_refresh_questions, args=[message]
            )
        if response := self.parse_count_questions_command(text, message):
            return response
        if response := self.parse_post_questions_command(text, message):
            return response
        if response := self.parse_get_question_info(text, message):
            return response
        return Response()

    ############################
    # Reload/refresh questions #
    ############################

    async def cb_hardreload_questions(self, message: ServiceMessage) -> Response:
        if not has_permissions(message.author):
            return Response(
                confidence=9,
                text=f"You don't have permissions to request hard-reload, <@{message.author}>",
                why=f"{message.author.display_name} asked me to hard-reload questions questions but they don't have permissions for that",
            )
        await message.channel.send(
            f"Ok, hard-reloading questions cache\nBefore: {len(self.coda_api.questions_df)} questions"
        )
        self.coda_api.reload_questions_cache()
        return Response(
            confidence=9,
            text=f"After: {len(self.coda_api.questions_df)} questions",
            why=f"{message.author.display_name} asked me to hard-reload questions",
        )

    async def cb_refresh_questions(self, message: ServiceMessage) -> Response:
        if not has_permissions(message.author):
            return Response(
                confidence=9,
                text=f"You don't have permissions, <@{message.author}>",
                why=f"{message.author.display_name} wanted me to refresh questions questions but they don't have permissions for that",
            )
        await message.channel.send(
            f"Ok, refreshing questions cache\nBefore: {len(self.coda_api.questions_df)} questions"
        )
        new_questions, deleted_questions = self.coda_api.update_questions_cache()
        response_text = f"After: {len(self.coda_api.questions_df)} questions"
        if not new_questions:
            response_text += "\nNo new questions"
        elif len(new_questions) <= 10:
            response_text += "\nNew questions:\n\t" + "\n\t".join(
                f'"{q["title"]}"' for q in new_questions
            )
        else:
            response_text += (
                f"\n{len(new_questions)} new questions:\n\t"
                + "\n\t".join(f'"{q["title"]}"' for q in new_questions[:10])
            ) + "\n\t..."

        if not deleted_questions:
            response_text += "\nNo questions deleted"
        elif len(deleted_questions) <= 10:
            response_text += "\nDeleted questions:\n\t" + "\n\t".join(
                f'"{q["title"]}"' for q in deleted_questions
            )
        else:
            response_text += (
                f"\n{len(deleted_questions)} deleted questions:\n\t"
                + "\n\t".join(f'"{q["title"]}"' for q in deleted_questions[:10])
            ) + "\n\t..."
        return Response(
            confidence=9,
            text=response_text,
            why=f"{message.author.display_name} asked me to refresh questions cache",
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
        if not (
            self.re_big_count_questions.search(text)
            or self.re_count_questions.match(text)
        ):
            return
        filter_data = parse_question_filter(text)

        return Response(
            confidence=9,
            callback=self.cb_count_questions,
            args=[filter_data, message],
            why="I was asked to count questions",
        )

    async def cb_count_questions(
        self,
        question_filter: QuestionFilterNT,
        message: ServiceMessage,
    ) -> Response:
        questions_df = self.coda_api.questions_df
        status, tag, _limit = question_filter

        # if status and/or tag specified, filter accordingly
        if status:
            questions_df = questions_df.query("status == @status")
        if tag:
            questions_df = filter_on_tag(questions_df, tag)

        # Make message and respond
        if len(questions_df) == 1:
            response_text = "There is 1 question"
        elif len(questions_df) > 1:
            response_text = f"There are {len(questions_df)} questions"
        else:  # len(questions_df) == 0
            response_text = "There are no questions"
        status_and_tag_response_text = make_status_and_tag_response_text(status, tag)
        response_text += status_and_tag_response_text

        return Response(
            confidence=9,
            text=response_text,
            why=f"{message.author.display_name} asked me to count questions{status_and_tag_response_text}",
        )

    ######################
    #   Post questions   #
    ######################

    def parse_post_questions_command(
        self, text: str, message: ServiceMessage
    ) -> Optional[Response]:
        if not (
            self.re_post_question.search(text) or self.re_big_next_question.search(text)
        ):
            return
        request_data = parse_question_query(text)
        return Response(
            confidence=9,
            callback=self.cb_post_questions,
            args=[request_data, message],
        )

    async def cb_post_questions(
        self,
        question_query: QuestionQuery,
        message: ServiceMessage,
    ) -> Response:
        # Dispatch on every possible type of QuestionQuery
        if question_query[0] == "GDocLinks":
            # it doesn't make any sense to ask Stampy to post questions to which we already have links
            response_text = (
                "Why don't you post "
                + ("it" if len(question_query[1]) == 1 else "them")
                + f" yourself, <@{message.author}>?"
            )
            return Response(
                confidence=9,
                text=response_text,
                why=f"If {message.author.display_name} has these links, they can surely post these question themselves",
            )

        # get questions (can be emptylist)
        questions = await self.coda_api.query_for_questions(
            question_query, message, least_recently_asked_unpublished=True
        )

        # get text and why (requires handling failures)
        response_text, why = await self.coda_api.get_response_text_and_why(
            questions, question_query, message
        )

        # If FilterData, add additional info about status and/or tag queried for
        if question_query[0] == "Filter":
            status, tag, _limit = question_query[1]
            response_text += make_status_and_tag_response_text(status, tag)

        # get current time for updating when these questions were last asked on Discord
        current_time = datetime.now()
        # add each question to response_text
        response_text += "\n"
        for q in questions:
            response_text += f"\n{make_post_question_message(q)}"
            self.coda_api.update_question_last_asked_date(q, current_time)

        # update caches
        self.last_question_posted_dt = current_time
        self.last_question_posted_was_not_started_autoposted = False

        # if there is exactly one question, remember its ID
        if len(questions) == 1:
            self.coda_api.last_question_id = questions[0]["id"]

        return Response(
            confidence=9,
            text=response_text,
            why=why,
        )

    def is_time_for_autopost_not_started(self) -> bool:
        return (
            self.last_question_posted_dt
            < datetime.now() - self.not_started_question_autopost_interval
            and not self.last_question_posted_was_not_started_autoposted
        )

    async def autopost_not_started(self) -> None:
        """Choose a random question from the oldest not started questions
        and post to the `#general` channel
        """
        self.log.info(
            self.class_name,
            msg="Autoposting a not started question to #general channel",
            dt=datetime.now(),
        )
        questions_df = self.coda_api.questions_df.query("status == 'Not started'")
        questions_df = questions_df[
            questions_df["tags"].map(lambda tags: "Stampy" not in tags)
        ]
        if questions_df.empty:
            self.log.info(
                self.class_name,
                msg='Found no questions with status "Not started" without tag "Stampy"',
            )
            return

        question = cast(
            QuestionRow,
            random.choice(
                get_least_recently_asked_on_discord(questions_df).to_dict(
                    orient="records"
                )
            ),
        )

        channel = cast(Thread, self.utils.client.get_channel(int(general_channel_id)))
        self.last_question_posted_was_not_started_autoposted = True

        await self.post_questions_to_channel([question], channel)

    def is_time_for_autopost_abandoned(self) -> bool:
        today = date.today()
        return today.weekday() == 0 and self.last_abandoned_autopost_date != today

    async def autopost_abandoned(self) -> None:
        """Post up to a specified number of questions to a #TODO channel"""

        self.log.info(
            self.class_name, msg="Autoposting abandoned questions to `#general`"
        )
        self.last_abandoned_autopost_date = date.today()
        _week_ago = datetime.now() - timedelta(days=7)
        questions_df = self.coda_api.questions_df.sort_values(
            by=["last_asked_on_discord", "doc_last_edited"]
        ).query("doc_last_edited < @_week_ago")
        questions_df = questions_df[
            questions_df["status"].map(lambda status: status in REVIEW_STATUSES)
        ].head(self.abandoned_autopost_limit)

        if questions_df.empty:
            self.log.info(
                self.class_name,
                msg=f"Found no questions with status from {REVIEW_STATUSES}",
            )
            return

        # TODO: decide on channel
        channel = cast(Thread, self.utils.client.get_channel(int(general_channel_id)))
        questions = cast(list[QuestionRow], questions_df.to_dict(orient="records"))

        self.log.info(
            self.class_name,
            msg=f"Posting {len(questions)} abandoned questions to channel",
            channel_name=channel.name,
        )

        await self.post_questions_to_channel(questions, channel)

    async def post_questions_to_channel(
        self,
        questions: list[QuestionRow],
        channel: Thread,  # TODO: check if this type is correct
    ) -> None:
        """Post random oldest not started question.
        Triggered automatically six hours after non-posting any question
        (unless the last was already posted automatically using this method).
        """
        current_time = datetime.now()
        for q in questions:
            self.coda_api.update_question_last_asked_date(q, current_time)
            await channel.send(make_post_question_message(q))
        if len(questions) == 1:
            self.coda_api.last_question_id = questions[0]["id"]
        self.last_question_posted_dt = current_time
        # get channel #general

        # query for questions with status "Not started" and not tagged as "Stampy"

        # update in coda
        # current_time = datetime.now()
        # self.coda_api.update_question_last_asked_date(question, current_time)

        # update caches
        # self.coda_api.last_question_id = question["id"]
        # self.last_posted_time = current_time
        # self.last_question_posted_random_autoposted = True

        # log #TODO
        # self.log.info(
        #     self.class_name,
        #     msg="Posting a random, least recent, not started question to #general",
        # )

        # send to channel
        # await channel.send(make_post_question_message(question))

    async def post_stagnant_questions(
        self, _event_type, stagnant_questions_df: pd.DataFrame
    ) -> None:
        """#TODO docstring explanation wtf"""
        # TODO: add comments like in the above method
        # TODO: merge this and the method above into one method?
        channel = cast(
            Thread, self.utils.client.get_channel(int(stampy_dev_priv_channel_id))
        )
        questions = cast(
            list[QuestionRow], stagnant_questions_df.to_dict(orient="records")
        )
        current_time = datetime.now()
        for question in questions:
            self.coda_api.update_question_last_asked_date(question, current_time)
        self.last_question_posted_dt = current_time
        self.last_question_posted_was_not_started_autoposted = True
        self.log.info(
            self.class_name, msg=f"Posting {len(questions)} stagnant questions"
        )  # TODO: better msg

    #########################
    #   Get question info   #
    #########################

    def parse_get_question_info(
        self, text: str, message: ServiceMessage
    ) -> Optional[Response]:
        # must match regex and contain query info
        if not self.re_get_question_info.match(text):
            return
        spec_data = parse_question_spec_query(text, return_last_by_default=True)

        return Response(
            confidence=9,
            callback=self.cb_get_question_info,
            args=[spec_data, message],
        )

    async def cb_get_question_info(
        self,
        question_query: QuestionQuery,
        message: ServiceMessage,
    ) -> Response:
        # get questions (can be emptylist)
        questions = await self.coda_api.query_for_questions(question_query, message)

        # get text and why (requires handling failures)
        response_text, why = await self.coda_api.get_response_text_and_why(
            questions, question_query, message
        )

        # add info about each question to response_text
        response_text += "\n"
        for q in questions:
            response_text += f"\n{pformat_to_codeblock(cast(dict, q))}"

        # add info about query
        if question_query[0] == "Last":
            response_text += "\n\nquery: `last question`"
        else:
            response_text += (
                f"\n\nquery:\n{pformat_to_codeblock(dict([question_query]))}"
            )

        # if there is exactly one question, remember its ID
        if len(questions) == 1:
            self.coda_api.last_question_id = questions[0]["id"]

        return Response(
            confidence=9,
            text=response_text,
            why=why,
        )

    #############
    #   Other   #
    #############

    @property
    def test_cases(self):
        if is_in_testing_mode():
            return []
        # TODO: write some tests that are expected to fail and ensure they fail in the way we expected
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
                expected_regex=r"There are \d{3} questions with status `Live on site`",
            ),
            self.create_integration_test(
                test_message="count questions tagged hedonium",
                expected_regex=r"There are \d\d? questions tagged as `Hedonium`",
            ),
            ########
            # Info #
            ########
            self.create_integration_test(
                test_message="info q is it unethical", expected_regex="Here it is"
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
                test_message="give us another question",
                expected_regex="Here is a question",
            ),
            self.create_integration_test(
                test_message="how long is the question queue",
                expected_regex=r"There are \d{3,4} questions",
            ),
        ]

    def __str__(self):
        return "Questions Module"


#############
#   Utils   #
#############


def make_post_question_message(question_row: QuestionRow) -> str:
    """Make message for posting a question into a Discord channel

    ```
    "<QUESTION_TITLE>"
    <GDOC_URL>
    ```
    """
    return '"' + question_row["title"] + '"' + "\n" + question_row["url"]


def make_status_and_tag_response_text(
    status: Optional[QuestionStatus],
    tag: Optional[str],
) -> str:
    """Generate additional info about status and/or tag queried for"""
    if status and tag:
        return f" with status `{status}` and tagged as `{tag}`"
    if status:
        return f" with status `{status}`"
    if tag:
        return f" tagged as `{tag}`"
    return ""


def get_last_monday() -> datetime:
    today = datetime.now()
    last_monday = today + relativedelta(weekday=MO(-1))
    return last_monday.replace(hour=8, minute=0, second=0, microsecond=0)
