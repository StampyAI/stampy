"""
Querying question database.

This module is also responsible for automatically posting questions coda questions to channels
1. `Not started`: Every 6 hours Stampy posts to `#general` a question with status `Not started`, chosen randomly from those that were least recently posted to Discord. Stampy doesn't post, if the last message in `#general` was this kind of autoposted question.
2. **WIP**: Every Monday, Wednesday, and Friday, sometime between 8 and 12 AM, Stampy posts to `#meta-editing` 1 to 3 questions with status `In review`, `In progress` or `Bulletpoint sketch` that have not been edited for longer than a week. Similarly, he skips if the last message in `#meta-editing` was this one.

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

from discord.channel import TextChannel
from dotenv import load_dotenv

from api.coda import (
    CodaAPI,
    filter_on_tag,
    get_least_recently_asked_on_discord,
)
from api.utilities.coda_utils import REVIEW_STATUSES, QuestionRow, QuestionStatus
from config import coda_api_token, is_rob_server
from servicemodules.discordConstants import (
    general_channel_id,
    meta_editing_channel_id,
)
from modules.module import Module, Response
from utilities.utilities import (
    has_permissions,
    is_in_testing_mode,
    pformat_to_codeblock,
)
from utilities.serviceutils import ServiceMessage
from utilities.time_utils import get_last_monday


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
    AUTOPOST_NOT_STARTED_MSG_PREFIX = "Recently I've been wondering..."
    AUTOPOST_STAGNANT_MSG_PREFIX = "Would any of you like to pick these up?"

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
        self.coda_api = CodaAPI.get_instance()

        ###################
        #   Autoposting   #
        ###################

        # How often Stampy posts random not started questions to `#general`
        self.not_started_question_autopost_interval = timedelta(hours=24)

        # Time of last (attempted) autopost of not started question
        self.last_not_started_autopost_attempt_dt = (
            datetime.now() - self.not_started_question_autopost_interval / 2
        )

        # Date of last (attempted) autopost of WIP question(s)
        self.last_wip_autopost_attempt_date: date = get_last_monday().date()

        # Max number of WIP questions to be autoposted
        self.wip_autopost_limit: int = 3

        if is_rob_server:
            @self.utils.client.event  # fmt:skip
            async def on_socket_event_type(_event_type) -> None:
                if self.is_time_for_autopost_not_started():
                    await self.autopost_not_started()
                if self.is_time_for_autopost_wip():
                    await self.autopost_wip()

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
            questions_df = questions_df.query(f"status == '{status}'")
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
            self.last_not_started_autopost_attempt_dt
            < datetime.now() - self.not_started_question_autopost_interval
        )

    async def last_msg_in_general_was_autoposted(self) -> bool:
        channel = cast(
            TextChannel, self.utils.client.get_channel(int(general_channel_id))
        )
        async for msg in channel.history(limit=20):
            if msg.content.startswith(self.AUTOPOST_NOT_STARTED_MSG_PREFIX):
                return True
        return False

    async def autopost_not_started(self) -> None:
        """Choose a random question from the oldest not started questions and post to `#general` channel"""
        current_time = datetime.now()
        self.last_not_started_autopost_attempt_dt = current_time

        if await self.last_msg_in_general_was_autoposted():
            self.log.info(
                self.class_name,
                msg="Last message in #general was an autoposted question with status `Not started` -> skipping autoposting",
            )
            return

        self.log.info(
            self.class_name,
            msg="Autoposting a question with status `Not started` to #general",
        )
        questions_df = self.coda_api.questions_df.query("status == 'Not started'")
        questions_df = questions_df[
            questions_df["tags"].map(lambda tags: "Stampy" not in tags)
        ]
        if questions_df.empty:
            self.log.info(
                self.class_name,
                msg='Found no questions with status `Not started` without tag "Stampy"',
            )
            return

        question = random.choice(
            self.coda_api.q_df_to_rows(
                get_least_recently_asked_on_discord(questions_df)
            )
        )

        channel = cast(
            TextChannel, self.utils.client.get_channel(int(general_channel_id))
        )

        msg = f"{self.AUTOPOST_NOT_STARTED_MSG_PREFIX}\n\n{make_post_question_message(question)}"
        self.coda_api.update_question_last_asked_date(question, current_time)
        self.coda_api.last_question_id = question["id"]

        await channel.send(msg)

    def is_time_for_autopost_wip(self) -> bool:
        now = datetime.now()
        return (
            now.weekday() in (0, 2, 4)  # Monday, Wednesday, or Friday
            and 8 <= now.hour <= 12  # between 08:00 and 12:00
            and self.last_wip_autopost_attempt_date
            != now.date()  # Wasn't posted today yet
        )

    async def last_msg_in_meta_editing_was_autoposted(self) -> bool:
        channel = cast(
            TextChannel, self.utils.client.get_channel(int(meta_editing_channel_id))
        )
        async for msg in channel.history(limit=1):
            if msg.content.startswith(self.AUTOPOST_STAGNANT_MSG_PREFIX):
                return True
        return False

    async def autopost_wip(self) -> None:
        """Post up to a specified number of questions that have been worked on but not touched for longer than a week
        to #meta-editing channel."""
        today = date.today()
        self.last_wip_autopost_attempt_date = today

        if await self.last_msg_in_meta_editing_was_autoposted():
            self.log.info(
                self.class_name,
                msg="Last message in `#meta-editing` was one or more autoposted WIP question(s) -> skipping autoposting",
            )
            return

        week_ago = today - timedelta(days=7)
        question_limit = random.randint(1, self.wip_autopost_limit)

        questions_df = self.coda_api.questions_df.query(
            f"doc_last_edited <= '{week_ago}'"
        )
        questions_df = (
            questions_df[
                questions_df["status"].map(lambda status: status in REVIEW_STATUSES)
            ]
            .sort_values(["last_asked_on_discord", "doc_last_edited"])
            .head(question_limit)
        )

        if questions_df.empty:
            self.log.info(
                self.class_name,
                msg=f"Found no questions with status from {REVIEW_STATUSES} with docs edited one week ago or earlier",
            )
            return

        questions = self.coda_api.q_df_to_rows(questions_df)

        self.log.info(
            self.class_name,
            msg=f"Posting {len(questions)} WIP questions to #meta-editing",
        )

        if len(questions) == 1:
            self.coda_api.last_question_id = questions[0]["id"]

        channel = cast(
            TextChannel, self.utils.client.get_channel(int(meta_editing_channel_id))
        )
        current_time = datetime.now()
        msg = self.AUTOPOST_STAGNANT_MSG_PREFIX + "\n\n"
        for q in questions:
            msg += f"{make_post_question_message(q, with_status=True, with_doc_last_edited=True)}\n"
            self.coda_api.update_question_last_asked_date(q, current_time)

        await channel.send(msg)

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


def make_post_question_message(
    question: QuestionRow,
    *,
    with_status: bool = False,
    with_doc_last_edited: bool = False,
) -> str:
    """Make message for posting a question into a Discord channel

    ```
    <QUESTION_TITLE>
    <status?> <last_edited?> (optional)
    <GDOC_URL>
    ```
    """
    msg = question["title"] + "\n"
    if with_status:
        msg += f"Status: `{question['status']}`."
        if with_doc_last_edited:
            msg += f" Last edited: `{question['doc_last_edited'].date()}`."
        msg += "\n"
    elif with_doc_last_edited:
        msg += f"Last edited: `{question['doc_last_edited'].date()}`\n"
    msg += question["url"]
    return msg


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
