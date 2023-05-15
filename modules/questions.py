"""
Querying the question database. No special permissions required.

### Counting questions

Stampy can count questions in the database. You can narrow down the counting using a particular status or tag. Use commands like these:

- `s, count questions` - counts all questions
- `s, count questions with status live on site` - counts only questions with status `Live on site`
- `s, count questions tagged decision theory` - counts only questions with the tag `Decision theory`
- `s, count questions with status live on site and tagged decision theory` - counts only questions that **both** have status `Live on site` **and** the tag `Decision theory`

![](images/help/Questions-count-questions.png)

---

Status name is case-insensitive: there is no difference between `Live on site`, `live on site`, or `LIVE ON SITE`. Similarly for tags. You can also use acronym aliases for status (but not for tags), e.g., `los` for `Live on site` or `bs` for `Bulletpoint sketch`.

### Posting questions

You can use Stampy to query the database of questions. Stampy will put links to questions that match your query into the channel.

The general pattern for that command is: `s, <get/post/next> <q/question/questions> <ADDITIONAL_INFO>`.

You can query in three ways

#### 1. Title

Stampy returns first question matching that title

`s, get <q/question/title/titled> <question_title>`

![](/images/help/Questions-get-adversarial.png)

#### 2. Filtering by status on tags

Stampy returns the specified number of questions (max 5, default 1) matching (optional) status and tag

`s, get 3 questions with status in progress and tagged definitions` (like [above](#counting-questions))

![](images/help/Questions-get-3-questions-status-tagged.png)

If you say, `s, next question`, then Stampy will query all questions, and post the least recently asked one.

![](images/help/Questions-next.png)

#### 3. Last

Stampy will post last question he interacted with.

`s, post last question` / `s, post it`

![](/images/help/Questions-get-last.png)

---

#### Autoposting (Rob Miles' server only)

On Rob Miles' Discord server, Stampy posts a random least recently asked question, if the last question was posted on somebody's request **and** more than 6 hours passed since then. Stampy posts either to the `#editing` channel or the `#general`

### Getting question info

`s, get info <ADDITIONAL_INFO>` (with any filtering option mentioned so far, except `next`) can be used to get detailed information about the question as an entity in the database.

![](images/help/Questions-get-info-babyagi.png)
"""
from __future__ import annotations

from datetime import datetime, timedelta
import random
import re
from typing import cast, Optional

from discord import Thread
from dotenv import load_dotenv

from api.coda import (
    CodaAPI,
    filter_on_tag,
    get_least_recently_asked_on_discord,
)
from api.utilities.coda_utils import QuestionRow, QuestionStatus
from servicemodules.discordConstants import general_channel_id
from modules.module import Module, Response
from utilities.question_query_utils import (
    parse_question_filter,
    parse_question_query,
    parse_question_spec_query,
    QuestionFilterNT,
    QuestionQuery,
)
from utilities.utilities import is_in_testing_mode, pformat_to_codeblock
from utilities.serviceutils import ServiceMessage


load_dotenv()

coda_api = CodaAPI.get_instance()


class Questions(Module):
    AUTOPOST_QUESTION_INTERVAL = timedelta(hours=6)

    def __init__(self) -> None:
        super().__init__()
        # Time when last question was posted
        self.last_posted_time: datetime = (
            datetime.now() - self.AUTOPOST_QUESTION_INTERVAL / 2
        )
        # Was the last question that was posted, automatically posted by Stampy?
        self.last_question_autoposted = False

        # Register `post_random_oldest_question` to be triggered every after 6 hours of no question posting
        @self.utils.client.event
        async def on_socket_event_type(event_type) -> None:
            if (
                self.last_posted_time < datetime.now() - self.AUTOPOST_QUESTION_INTERVAL
            ) and not self.last_question_autoposted:
                await self.post_random_oldest_question(event_type)

            if (
                coda_api.questions_cache_last_update
                < datetime.now() - coda_api.QUESTIONS_CACHE_UPDATE_INTERVAL
            ):
                coda_api.update_questions_cache()

    def process_message(self, message: ServiceMessage) -> Response:
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
        if not (re_big_count_questions.search(text) or re_count_questions.search(text)):
            return
        filter_data = parse_question_filter(text)

        return Response(
            confidence=8,
            callback=self.cb_count_questions,
            args=[filter_data, message],
            why="I was asked to count questions",
        )

    async def cb_count_questions(
        self,
        question_filter: QuestionFilterNT,
        message: ServiceMessage,
    ) -> Response:
        questions_df = coda_api.questions_df
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
            confidence=8,
            text=response_text,
            why=f"{message.author.name} asked me to count questions{status_and_tag_response_text}",
        )

    ######################
    #   Post questions   #
    ######################

    def parse_post_questions_command(
        self, text: str, message: ServiceMessage
    ) -> Optional[Response]:
        if not (re_post_question.search(text) or re_big_next_question.search(text)):
            return
        request_data = parse_question_query(text)
        return Response(
            confidence=8,
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
                confidence=10,
                text=response_text,
                why=f"If {message.author.name} has these links, they can surely post these question themselves",
            )

        # get questions (can be emptylist)
        questions = await coda_api.query_for_questions(
            question_query, message, least_recently_asked_unpublished=True
        )

        # get text and why (requires handling failures)
        response_text, why = await coda_api.get_response_text_and_why(
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
            coda_api.update_question_last_asked_date(q["id"], current_time)

        # update caches
        self.last_posted_time = current_time
        self.last_question_autoposted = False

        # if there is exactly one question, remember its ID
        if len(questions) == 1:
            coda_api.last_question_id = questions[0]["id"]

        return Response(
            confidence=10,
            text=response_text,
            why=why,
        )

    # TODO: this should be on Rob's discord only
    async def post_random_oldest_question(self, _event_type) -> None:
        """Post random oldest not started question.
        Triggered automatically six hours after non-posting any question
        (unless the last was already posted automatically using this method).
        """
        # get channel #general
        channel = cast(Thread, self.utils.client.get_channel(int(general_channel_id)))

        # query for questions with status "Not started" and not tagged as "Stampy"
        questions_df_filtered = coda_api.questions_df.query("status == 'Not started'")
        questions_df_filtered = questions_df_filtered[
            questions_df_filtered["tags"].map(lambda tags: "Stampy" not in tags)
        ]
        # choose at random from least recently asked ones
        question = cast(
            QuestionRow,
            random.choice(
                get_least_recently_asked_on_discord(questions_df_filtered).to_dict(
                    orient="records"
                ),
            ),
        )

        # update in coda
        current_time = datetime.now()
        coda_api.update_question_last_asked_date(question["id"], current_time)

        # update caches
        coda_api.last_question_id = question["id"]
        self.last_posted_time = current_time
        self.last_question_autoposted = True

        # log
        self.log.info(
            self.class_name,
            msg="Posting a random, least recent, not started question to #general",
        )

        # send to channel
        await channel.send(make_post_question_message(question))

    #########################
    #   Get question info   #
    #########################

    def parse_get_question_info(
        self, text: str, message: ServiceMessage
    ) -> Optional[Response]:
        # must match regex and contain query info
        if not re_get_question_info.search(text):
            return
        if not (spec_data := parse_question_spec_query(text)):
            return
        return Response(
            confidence=10,
            callback=self.cb_get_question_info,
            args=[spec_data, message],
        )

    async def cb_get_question_info(
        self,
        question_query: QuestionQuery,
        message: ServiceMessage,
    ) -> Response:
        # get questions (can be emptylist)
        questions = await coda_api.query_for_questions(question_query, message)

        # get text and why (requires handling failures)
        response_text, why = await coda_api.get_response_text_and_why(
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
            coda_api.last_question_id = questions[0]["id"]

        return Response(
            confidence=8,
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


###############
#   Regexes   #
###############

re_post_question = re.compile(
    r"""
    (?:get|post|next) # get / post / next
    \s # whitespace char (obligatory)
    (?:\d+\s)? # optional number of questions
    (?:q|questions?|a|answers?|itlast)
    # q / question / questions / a / answer / answers / it / last
    """,
    re.I | re.X,
)
re_get_question_info = re.compile(r"i|info", re.I)
re_count_questions = re.compile(
    r"(?:count|how many|number of|n of|#) (?:q|questions|a|answers)", re.I
)

re_big_next_question = re.compile(
    r"(([wW]hat(’|'| i)?s|([Cc]an|[Mm]ay) (we|[iI]) (have|get)|[Ll]et[’']?s have|[gG]ive us)"
    r"?( ?[Aa](nother)?|( the)? ?[nN]ext) question,?( please)?\??|([Dd]o you have|([Hh]ave you )"
    r"?[gG]ot)?( ?[Aa]ny( more| other)?| another) questions?( for us)?\??)!?"
)

re_big_count_questions = re.compile(
    r"([hH]ow many questions (are (there )?)?(left )?in)|([hH]ow "
    r"(long is|long's)) (the|your)( question)? queue( now)?\??",
)
