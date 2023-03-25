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
from textwrap import dedent
from typing import Literal, Optional, TypedDict, Union, cast

from dotenv import load_dotenv
import pandas as pd

from api.coda import CodaAPI, QuestionStatus
from api.utilities.coda_utils import QuestionRow
from servicemodules.discordConstants import editing_channel_id, general_channel_id
from modules.module import Module, Response
from utilities.utilities import (
    fuzzy_contains,
    is_from_editor,
    is_from_reviewer,
    is_in_testing_mode,
    pformat_to_codeblock,
)
from utilities.discordutils import DiscordChannel, DiscordMessage


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

    def process_message(self, message: DiscordMessage) -> Response:
        """Process message"""
        # these two options are before `.is_at_me`
        # because they dont' require calling Stampy explicitly ("s, XYZ")
        if cmd := self.parse_review_request(message):
            return Response(
                confidence=8,
                callback=self.cb_set_status_by_review_request,
                args=[cmd, message],
                why=f"{message.author.name} asked for a review",
            )
        if cmd := self.parse_response_to_review_request(message):
            return Response(
                confidence=8,
                callback=self.cb_set_status_by_approval_to_review_request,
                args=[cmd, message],
                why=f"{message.author.name} accepted the review",
            )

        # past that point, we require the message to be directed to Stampy explicitly
        if not (text := self.is_at_me(message)):
            return Response()

        if cmd := self.parse_mark_question_request(message):
            return Response(
                confidence=8,
                callback=self.cb_set_status_by_mark_question_request,
                args=[cmd, message],
                why=f"{message.author.name} marked these questions as `{cmd['status']}`",
            )
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
        if cmd := self.parse_set_question_status_command(text, self.last_question_id):
            return Response(
                confidence=8,
                callback=self.cb_set_status_by_msg,
                args=[cmd, message],
                why=f"I was asked to set status of question with id `{cmd['id']}` to `{cmd['status']}`",
            )
        return Response(
            why="Left QuestionManager without matching to any possible response"
        )

    ##################
    # Review request #
    ##################

    def parse_review_request(
        self, message: DiscordMessage
    ) -> Optional[SetQuestionStatusByAtCommand]:
        """Is this message a review request with link do GDoc?
        If it is, return `SetQuestionStatusByAtCommand`.
        If it isn't, return `None`.
        """
        text = message.clean_content

        # get new status for questions
        if "@reviewer" in text:
            new_status = "In review"
        elif "@feedback-sketch" in text:
            new_status = "Bulletpoint sketch"
        elif "@feedback" in text:
            new_status = "In progress"
        else:  # if neither of these three roles is mentioned, this is not a review request
            return

        # try parsing gdoc links and questions that have these gdoc links
        # if you fail, assume this is not a review request
        if not (gdoc_links := parse_gdoc_links(text)):
            return
        if not (questions := coda_api.get_questions_by_gdoc_links(gdoc_links)):
            return

        # cache ids of these questions under the ID of this message
        question_ids = [q["id"] for q in questions]
        self.review_msg_id2question_ids[message.id] = question_ids

        return {"ids": question_ids, "status": new_status}

    async def cb_set_status_by_review_request(
        self, cmd: SetQuestionStatusByAtCommand, message: DiscordMessage
    ) -> Response:
        """Change question status by posting GDoc link(s) for review
        along with one of the mentions:
        `@reviewer` or `@feedback` or `@feedback-sketch`
        """
        q_ids = cmd["ids"]
        status = cmd["status"]
        channel = cast(DiscordChannel, message.channel)

        # pre-send message to confirm that you're going to update statuses
        await channel.send(
            f"Thanks, {message.author.name}! I'll update "
            + ("their" if len(q_ids) > 1 else "its")
            + f" status to `{status}`"
        )
        # map question IDs to QuestionRows
        id2question = {q_id: coda_api.get_question_row(q_id) for q_id in q_ids}
        # store IDs of questions that are already "Live on site" (unless message author is `@reviewer`)
        already_los_q_ids = []

        # update
        for q_id, question in id2question.items():
            if question["status"] == "Live on site" and not is_from_reviewer(message):
                already_los_q_ids.append(q_id)
            else:
                coda_api.update_question_status(q_id, status)

        # make message
        # number of questions that were updated
        n_updated = len(id2question) - len(already_los_q_ids)
        if n_updated == 0:
            response_text = "I didn't update any questions"
        elif n_updated == 1:
            response_text = "I updated 1 question"
            # update last_question_id if only 1 question was updated
            only_updated_question_id = next(
                q_id for q_id in id2question if q_id not in already_los_q_ids
            )
            self.last_question_id = only_updated_question_id
        else:
            response_text = f"I updated {n_updated} questions"
        response_text += f" to `{status}`"

        # if message author is not `@reviewer` and they tried setting some questions to "Live on site"
        # inform them that their statuses were not changed
        if already_los_q_ids:
            if len(already_los_q_ids) == 1:
                response_text += (
                    "\n\nOne question is already `Live on site`, so I didn't change it."
                )
            else:
                response_text += (
                    f"\n\n{len(already_los_q_ids)} questions are already `Live on site`, "
                    "so I didn't change them."
                )
            # explain why
            response_text += (
                " You need to be a `@reviewer` to change the status of "
                "questions that are already `Live on site`.\n\n"
            )
            # list these questions in the format: `- title (url)`
            response_text += "\n".join(
                f"- {id2question[q_id]['title']} ({id2question[q_id]['url']})"
                for q_id in already_los_q_ids
            )

        return Response(
            confidence=8,
            text=response_text,
            why=f"{message.author.name} asked for review",
        )

    ##################
    # Review approval #
    ##################

    def parse_response_to_review_request(
        self, message: DiscordMessage
    ) -> Optional[SetQuestionStatusByApproval]:
        """Is this message a response to review request?
        If it is, return `SetQuestionStatusByApproval`.
        If it isn't, return `None`.
        """
        text = message.clean_content
        # if it doesn't contain any of these three, it is not review approval
        if not any(s in text.lower() for s in ["approved", "accepted", "lgtm"]):
            return

        # ...same if it doesn't reply to any previous message
        if (msg_ref := message.reference) is None:
            return

        # ...or if its reference doesn't have a `message_id`
        # (which shouldn't happen in theory but just in case)
        msg_ref_id = cast(Optional[int], getattr(msg_ref, "message_id", None))
        if msg_ref_id is None:
            return

        # at this point, we know that this message replies to an approval request
        # so if the ID is missing, we will need to recover it later in the callback

        return {"ids": self.review_msg_id2question_ids.get(str(msg_ref_id), None)}

    async def cb_set_status_by_approval_to_review_request(
        self, cmd: SetQuestionStatusByApproval, message: DiscordMessage
    ) -> Response:
        """Approve questions posted as GDoc links for review (see above).
        Their status is changed to "Live on site".
        Works for `@reviewer`s only.
        """
        q_ids = cmd["ids"]
        channel = cast(DiscordChannel, message.channel)

        # if q_ids is None, this means that the message with review request precedes Stampy's last reboot,
        # so the `review_msg_id2question_ids` cache is empty
        # in that case, we restore the cache before proceeding
        if q_ids is None:
            await channel.send("Eh, I just got rebooted... gimme a moment plz")
            await self.restore_review_msg_cache(channel)
            msg_ref_id = str(getattr(message.reference, "message_id", None))
            if msg_ref_id not in self.review_msg_id2question_ids:
                return Response(
                    confidence=8,
                    text="But the message you replied wasn't among them",
                    why=f"{message.author.name} approved a review request but I couldn't find it in the channel history",
                )
            q_ids = self.review_msg_id2question_ids[msg_ref_id]

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
        await channel.send(f"Approved by {message.author.name}!")

        # update question statuses
        for q_id in q_ids:
            coda_api.update_question_status(q_id, "Live on site")

        if len(q_ids) == 1:
            response_text = "1 more question goes"
            # if the review request contains only one question, we save its ID to the cache
            self.last_question_id = q_ids[0]
        else:
            response_text = f"{len(q_ids)} more questions go"
        response_text += " `Live on site`!"

        return Response(
            confidence=8,
            text=response_text,
            why=f"{message.author.name} approved the questions posted for review",
        )

    ###################
    # Marking request #
    ###################

    def parse_mark_question_request(
        self, message: DiscordMessage
    ) -> Optional[SetQuestionStatusByMarking]:
        """Does this message tell Stampy, to change the status of one or more questions to
        "Marked for deletion" ("s, del <gdoc-link(s)>") or to "Duplicate" ("s, dup <gdoc-links>").
        If it does, return `SetQuestionStatusByMarking`. If it doesn't, return `None`.
        """
        text = message.clean_content
        if text.startswith("s, del"):
            new_status = "Marked for deletion"
        elif text.startswith("s, dup"):
            new_status = "Duplicate"
        else:
            return

        if not (gdoc_links := parse_gdoc_links(text)):
            return
        if not (questions := coda_api.get_questions_by_gdoc_links(gdoc_links)):
            return

        question_ids = [q["id"] for q in questions]

        return {"ids": question_ids, "status": new_status}

    async def cb_set_status_by_mark_question_request(
        self, cmd: SetQuestionStatusByMarking, message: DiscordMessage
    ) -> Response:
        """Change status of one or more questions to "Marked for deletion" or "Duplicate"
        upon a request of the following form:

        `s, <del/dup> <gdoc-link(s)>`
        """

        q_ids = cmd["ids"]
        status = cmd["status"]

        # verb - what exactly this request is supposed to do (for messaging)
        verb = "mark " + ("this question" if len(q_ids) == 1 else "these questions")
        if status == "Marked for deletion":
            verb += " for deletion"
        else:  # status == "Duplicate"
            verb += " as " + ("a duplicate" if len(q_ids) == 1 else "duplicates")

        # if this message is not from `@editor`, explain why you can't execute the command
        # (i.e. change questions' status)
        if not is_from_editor(message):
            return Response(
                confidence=8,
                text=f"You're not an `@editor`, {message.author.name}. You can't {verb}.",
                why=f"{message.author.name} wanted to {verb} but they don't have necessary permissions.",
            )

        # send pre-message to the channel
        channel = cast(DiscordChannel, message.channel)
        await channel.send(f"Thanks, {message.author.name}, I'll {verb}")

        # change statuses
        for q_id in q_ids:
            coda_api.update_question_status(q_id, status)

        # if there was only one question, save it to the cache
        if len(q_ids) == 1:
            self.last_question_id = q_ids[0]

        response_text = (
            "I changed "
            + ("its" if len(q_ids) == 1 else "their")
            + f" status to `{status}`"
        )

        return Response(
            confidence=8,
            text=response_text,
            why=f"{message.author.name} asked me to {verb}",
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
        self, cmd: CountQuestionsCommand, message: DiscordMessage
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
        self, cmd: PostQuestionsCommand, message: DiscordMessage
    ) -> Response:
        """Post message to Discord for least recently asked question.
        It will contain question title and GDoc url.
        """
        # get questions df
        questions_df = coda_api.questions_df
        # get channel
        channel = cast(DiscordChannel, message.channel)

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
        if max_num_of_questions == 1:
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
            DiscordChannel,
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
        message: DiscordMessage,
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

    ##############
    # Set status #
    ##############

    def parse_set_question_status_command(
        self, text: str, last_question_id: Optional[str]
    ) -> Optional[SetQuestionStatusByMsgCommand]:
        """Return `SetQuestionStatusByMsgCommand` if it asks Stampy to change status 
        of a particular question. Return `None` otherwise.
        """
        # set status of last question
        if "set it" in text or "set last" in text:
            query_type = "last"
            query_id = last_question_id
        # set status of question with specified ID
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

        return {"type": query_type, "id": query_id, "status": status}

    async def cb_set_status_by_msg(
        self, cmd: SetQuestionStatusByMsgCommand, message: DiscordMessage
    ) -> Response:
        """Set question status by telling Stampy

        ```
        s, set it to <some status>
        # or
        s, set <question id> to <some status>
        ```
        """
        q_id = cmd["id"]
        status = cmd["status"]

        # early exit if asked for last question but there is no last question
        if q_id is None:  # possible only when cmd is SetLastQuestionStatusCommand
            mention = "it" if "it" in message.clean_content else "last"
            return Response(
                confidence=8,
                text=f'What do you mean by "{mention}"?',
                why=dedent(
                    (
                        f"{message.author.name} asked me to set last question's status "
                        f"to `{status}` but I haven't posted any questions yet"
                    )
                ),
            )

        # get that question
        question = coda_api.get_question_row(q_id)

        # early exit if a non-`@reviewer` asked for changing status from or to "Live on site"
        if response := unauthorized_set_los(status, question, message):
            return response

        coda_api.update_question_status(q_id, status)
        self.last_question_id = q_id

        response_text = "Ok!"
        if cmd["type"] == "last":
            response_text += f'\n"{question["title"]}" is now `{status}`.'
        else:  # query.type == "id":
            response_text += f" It's `{status}` now."

        return Response(
            confidence=8,
            text=response_text,
            why=(
                f"{message.author.name} asked to update status of question "
                f"with id `{q_id}` to `{status}`"
            ),
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


class SetQuestionStatusByAtCommand(TypedDict):
    """Set question status on review request
    - Somebody mentions one of the roles (`@reviewer`, `@feedback`, `@feedback-sketch`)
    and posts a link to GDoc, triggering Stampy to change status of that question
    (to `In review`, `In progress`, `Bulletpoint sketch`, respectively)
    """

    ids: list[str]
    status: Literal["In review", "Bulletpoint sketch", "In progress"]


class SetQuestionStatusByApproval(TypedDict):
    """Set question status on review approval
    - A user with `@reviewer` role responds to a review request with a message containing
    "accepted", "approved", or "lgtm" (case insensitive)
    -> questions's status changes to "Live on site"
    """

    ids: Optional[list[str]]
    """IDs of questions taken from the cache. Is `None` when the cache was found empty, 
    e.g. when the question to which the reply was directed was sent before the last reboot.
    """


class SetQuestionStatusByMarking(TypedDict):
    """Set question status on marking
    - "s, del <gdoc-link(s)>" - question(s) get(s) status "Marked for deletion"
    - "s, dup <gdoc-link(s)>" - question(s) get(s) status "Duplicate"
    """

    ids: list[str]
    status: Literal["Marked for deletion", "Duplicate"]


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


class SetQuestionStatusByMsgCommand(TypedDict):
    """Change status of a particular question."""

    type: Literal["id", "last"]
    """
    - "id" - specified by unique row identifier in "All Answers" table
    - "last" - ordered to get the last row that stampy interacted with
    (changed or posted) in isolation from other rows
    """
    id: Optional[str]
    status: QuestionStatus


##################
# Util functions #
##################

# Parsing


def parse_status(
    text: str, *, require_status_prefix: bool = True
) -> Optional[QuestionStatus]:
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
    status: QuestionStatus,
    question: QuestionRow,
    message: DiscordMessage,
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
