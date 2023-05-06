from __future__ import annotations

from datetime import datetime, timedelta
import os
from textwrap import dedent
from typing import cast, get_args, Optional, Literal

from codaio import Coda, Document, Row
import pandas as pd
from structlog import get_logger


from api.utilities.coda_utils import (
    parse_question_row,
    QuestionRow,
    DEFAULT_DATE,
    make_updated_cells,
)
from utilities import is_in_testing_mode
from utilities.discordutils import DiscordUser
from utilities.questions_utils import (
    QuestionRequestData,
    make_status_and_tag_response_text,
)
from utilities.serviceutils import ServiceMessage
from utilities.utilities import fuzzy_contains, get_user_handle, shuffle_df

log = get_logger()

QuestionStatus = Literal[
    "Bulletpoint sketch",
    "Duplicate",
    "In progress",
    "In review",
    "Live on site",
    "Marked for deletion",
    "Not started",
    "Uncategorized",
    "Withdrawn",
]


class CodaAPI:
    """Gathers everything for interacting with coda"""

    # Singleton instance
    __instance: Optional[CodaAPI] = None

    # Constants
    CODA_API_TOKEN = os.environ["CODA_API_TOKEN"]
    DOC_ID = (
        "bmMz5rbOHi" if os.getenv("ENVIRONMENT_TYPE") == "development" else "fau7sl2hmG"
    )
    ALL_ANSWERS_TABLE_ID = "table-YvPEyAXl8a"
    STATUSES_GRID_ID = "grid-IWDInbu5n2"
    TEAM_GRID_ID = "grid-pTwk9Bo_Rc"
    TAGS_GRID_ID = "grid-4uOTjz1Rkz"

    REQUEST_TIMEOUT = 5

    QUESTIONS_CACHE_UPDATE_INTERVAL = timedelta(minutes=10)

    def __init__(self):
        if CodaAPI.__instance is not None:
            raise Exception(
                "This class is a singleton! Access it using `Utilities.get_instance()`"
            )
        self.__instance = self  # pylint:disable=unused-private-member
        self.class_name = "Coda API"
        self.log = get_logger()
        self.last_question_id: Optional[str] = None

        if is_in_testing_mode():
            return

        self.coda = Coda(self.CODA_API_TOKEN)  # type:ignore
        self.update_questions_cache()
        self.update_users_cache()

    @property
    def doc(self) -> Document:
        """As property to make coda document always up-to-date"""
        return Document(self.DOC_ID, coda=self.coda)  # type:ignore

    @classmethod
    def get_instance(cls) -> CodaAPI:
        """Get singleton instance"""
        if cls.__instance is None:
            cls.__instance = cls()
        return cls.__instance

    def update_questions_cache(self) -> None:
        """Update questions cache, i.e. DataFrame with questions.
        Gets called upon CodaAPI initialization and every 10 minutes or so by Questions module.
        """
        questions = self.doc.get_table(self.ALL_ANSWERS_TABLE_ID)
        question_rows = [parse_question_row(row) for row in questions.rows()]
        self.questions_df = pd.DataFrame(question_rows).set_index("id", drop=False)
        self.questions_cache_last_update = datetime.now()
        self.log.info(
            self.class_name,
            msg="Updated questions cache",
            num_questions=len(self.questions_df),
        )

    def update_users_cache(self) -> None:
        """Update users cache, i.e. codaio Table representing
        [Team table](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/Team_sur3i#Team_tu_Rc/r5).
        Gets called upon CodaAPI initialization and every 23 hours or so
        from within StampCollection module,
        when all stamps in the coda table are being updated.
        """
        self.users = self.doc.get_table(self.TEAM_GRID_ID)
        self.log.info(
            self.class_name, msg="Updated users cache", num_users=self.users.row_count
        )

    #############
    #   Users   #
    #############

    def get_user_row(self, field: str, value: str) -> Optional[Row]:
        """Get user row from the users table using a query with the following form

        `"<field/column name>":"<value>"`
        """
        rows = self.users.find_row_by_column_name_and_value(
            column_name=field, value=value
        )
        if rows:
            return rows[0]

    def update_user_stamps(self, user: DiscordUser, stamp_count: float) -> None:
        """Update stamps count in Coda
        [users/team table](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/Team_sur3i#_lu_Rc)
        """
        # get row
        row = self.get_user_row("Discord handle", get_user_handle(user))
        if row is None:
            self.log.info(self.class_name, msg="Couldn't find user in table", user=user)
            return

        # update table
        updated_cells = make_updated_cells({"Stamp count": stamp_count})
        self.users.update_row(row, updated_cells)

    #################
    #   Questions   #
    #################

    def get_question_row(self, question_id: str) -> Optional[QuestionRow]:
        """Get QuestionRow by its ID"""
        if question_id not in self.questions_df.index.tolist():
            return
        return cast(QuestionRow, self.questions_df.loc[question_id].to_dict())

    def get_questions_by_gdoc_links(self, urls: list[str]) -> list[QuestionRow]:
        """Get questions by url links to their GDocs.
        Returns list of `QuestionRow`s. Empty list (`[]`) if couldn't find questions
        with any of the links.
        """
        questions_df = self.questions_df
        questions_df_queried = questions_df[  # pylint:disable=unsubscriptable-object
            questions_df["url"].map(  # pylint:disable=unsubscriptable-object
                lambda qurl: any(qurl.startswith(url) for url in urls)
            )
        ]
        if questions_df_queried.empty:
            return []
        return cast(list[QuestionRow], questions_df_queried.to_dict(orient="records"))

    def get_question_by_title(self, searched_title: str) -> Optional[QuestionRow]:
        questions_df = self.questions_df
        questions_df_queried = questions_df[  # pylint:disable=unsubscriptable-object
            questions_df["title"].map(  # pylint:disable=unsubscriptable-object
                lambda title: fuzzy_contains(title, searched_title)
            )
        ]
        if questions_df_queried.empty:
            return
        if len(questions_df_queried) > 1:
            self.log.warning(
                self.class_name,
                msg=f"Found {len(questions_df_queried)} matching title {searched_title}. Returning first.",
                results=questions_df_queried["title"].tolist(),
            )
        question = questions_df_queried["title"][0]
        return question

    def update_question_status(
        self,
        question_id: str,
        status: QuestionStatus,
    ) -> None:
        """Update status of a question in
        [coda table](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a).
        Also, update local cache accordingly.
        """
        # get row
        row = self.get_question_row(question_id)
        if row is None:
            return
        # update coda table
        self.doc.get_table(self.ALL_ANSWERS_TABLE_ID).update_row(
            row["row"], make_updated_cells({"Status": status})
        )
        # update local cache
        self.questions_df.loc[question_id]["status"] = status

    def update_question_last_asked_date(
        self, question_id: str, current_time: datetime
    ) -> None:
        """Update "Last Asked On Discord" field of a question in
        [coda table](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a).
        Also, update local cache accordingly"""
        # get row
        row = self.get_question_row(question_id)
        if row is None:
            return
        # update coda table
        self.doc.get_table(self.ALL_ANSWERS_TABLE_ID).update_row(
            row["row"],
            make_updated_cells({"Last Asked On Discord": current_time.isoformat()}),
        )
        # update local cache
        self.questions_df.loc[question_id]["last_asked_on_discord"] = current_time

    def _reset_dates(self) -> None:
        """Reset all questions' dates (util, not to be used by Stampy)"""
        questions_df = self.questions_df
        # pylint:disable=unsubscriptable-object
        questions_with_dt_ids = questions_df[
            questions_df["last_asked_on_discord"] != DEFAULT_DATE
        ]["id"].tolist()
        for question_id in questions_with_dt_ids:
            self.update_question_last_asked_date(question_id, DEFAULT_DATE)

    ###############
    #   Finding   #
    ###############

    async def query_for_questions(
        self, request_data: QuestionRequestData, message: ServiceMessage
    ) -> list[QuestionRow]:
        """Finds questions based on request data"""
        questions_df = self.questions_df

        # QuestionId
        if request_data[0] == "Id":
            question_id = request_data[1]
            question = self.get_question_row(question_id)
            if question is None:
                return []
            return [question]

        # QuestionGDocLinks
        if request_data[0] == "GDocLinks":
            gdoc_links = request_data[1]
            questions = self.get_questions_by_gdoc_links(gdoc_links)
            if not questions:
                return []
            return questions

        # QuestionTitle
        if request_data[0] == "Title":
            question_title = request_data[1]
            question = self.get_question_by_title(question_title)
            if question is None:
                return []
            return [question]

        # QuestionLast
        if request_data[0] == "Last":
            if self.last_question_id is None:
                return []
            question = cast(QuestionRow, self.get_question_row(self.last_question_id))
            return [question]

        ######################
        # QuestionFilterData #
        ######################
        status, tag, limit = request_data[1]

        # if status was specified, filter questions for that status
        if status:  # pylint:disable=unused-variable
            questions_df = questions_df.query("status == @status")
        else:  # otherwise, filter for question that ain't Live on site
            questions_df = questions_df.query("status != 'Live on site'")
        # if tag was specified, filter for questions having that tag
        questions_df = filter_on_tag(questions_df, tag)

        # get all the oldest ones and shuffle them
        questions_df = get_least_recently_asked_on_discord(questions_df)
        questions_df = shuffle_df(questions_df)

        limit = min(limit, 5)

        # get specified number of questions (default [if unspecified] is 1)
        if limit > 5:
            await message.channel.send(f"{limit} is to much. I'll give you up to 5.")

        n = min(limit, 5)
        # filter on max num of questions
        questions_df = questions_df.sort_values(
            "last_asked_on_discord", ascending=False
        ).iloc[:n]
        if questions_df.empty:
            return []
        questions = cast(list[QuestionRow], questions_df.to_dict(orient="records"))
        return questions

    Text = Why = str

    async def get_questions_text_and_why(
        self,
        questions: list[QuestionRow],
        request_data: QuestionRequestData,
        message: ServiceMessage,
    ) -> tuple[Text, Why]:
        # QuestionId
        if request_data[0] == "Id":
            question_id = request_data[1]
            if not questions:
                return (
                    f"There are no questions matching ID `{question_id}`",
                    f"{message.author.name} wanted me to get a question matching ID `{question_id}` but I found nothing",
                )
            return (
                "Here it is!",
                f"{message.author.name} wanted me to get a question matching ID `{question_id}`",
            )

        # QuestionGDocLinks
        if request_data[0] == "GDocLinks":
            if not questions:
                return (
                    "These links don't lead to any questions",
                    f"{message.author.name} gave me some links but they don't lead to any questions in my database",
                )
            text = "Here it is:" if len(questions) == 1 else "Here they are:"
            return (
                text,
                f"{message.author.name} wanted me to get these questions",
            )

        # QuestionTitle
        if request_data[0] == "Title":
            question_title = request_data[1]
            if not questions:
                return (
                    "I found no question matching that title",
                    f'{message.author.name} asked for a question with title matching "{question_title}" but I found nothing ;_;',
                )
            return (
                f'Here it is:\n"{questions[0]["title"]}"',
                f'{message.author.name} wanted me to get a question with title matching "{question_title}"',
            )

        # QuestionLast
        if request_data[0] == "Last":
            mention = request_data[1]
            if not questions:
                return (
                    f'What do you mean by "{mention}"?',
                    f"{message.author.name} asked me to post the last question but I don't know what they're talking about",
                )
            return (
                f"The last question was:\n\"{questions[0]['title']}\"",
                f"{message.author.name} wanted me to get the last question",
            )

        ######################
        # QuestionFilterData #
        ######################

        status, tag = request_data[1][:2]
        status_and_tag_response_text = make_status_and_tag_response_text(status, tag)
        if not questions:
            return (
                f"I found no questions{status_and_tag_response_text}",
                f"{message.author.name} asked me for questions{status_and_tag_response_text} but I found nothing",
            )
        if len(questions) == 1:
            text = f"I found one question{status_and_tag_response_text}"
        else:
            text = f"I found {len(questions)} questions{status_and_tag_response_text}"
        return (
            text,
            f"{message.author.name} asked me for questions{status_and_tag_response_text} and I found {len(questions)}",
        )

    #############
    #   Other   #
    #############

    def get_status_shorthand_dict(self) -> dict[str, QuestionStatus]:
        """Get dictionary mapping statuses and status shorthands
        (e.g. "bs" for "Bulletpoint sketch") to valid Status labels.
        """
        # Workaround to make mock request during testing
        if is_in_testing_mode():
            return {}

        statuses = self.get_all_statuses()
        status_shorthand_dict = {}
        for status in statuses:
            status_shorthand_dict[status] = status
            status_shorthand_dict[status.lower()] = status
            shorthand = "".join(word[0].lower() for word in status.split())
            status_shorthand_dict[shorthand] = status
        return status_shorthand_dict

    def get_all_tags(self) -> list[str]:
        """Get all tags from "All Answers" table"""
        # Workaround to make mock request during testing
        if is_in_testing_mode():
            return []
        tags_table = self.doc.get_table(self.TAGS_GRID_ID)
        tags_vals = {row["Tag name"] for row in tags_table.to_dict()}
        return sorted(tags_vals)

    def get_all_statuses(self) -> list[str]:
        """Get all valid Status values from table in admin panel"""
        status_table = self.doc.get_table(self.STATUSES_GRID_ID)
        status_vals = {r["Status"].value for r in status_table.rows()}
        if status_vals != (code_status_vals := set(get_args(QuestionStatus))):
            msg = dedent(
                f"""\
                Status values defined in api/coda.py file don't match the values found in coda table:
                values in code: {code_status_vals}
                values in coda table: {status_vals}"""
            )
            log.error(self.class_name, msg=msg)
            raise AssertionError(msg)
        return sorted(status_vals)


def filter_on_tag(questions_df: pd.DataFrame, tag: Optional[str]) -> pd.DataFrame:
    if tag is None:
        return questions_df

    def _contains_tag(tags: list[str]) -> bool:
        return any(t.lower() == cast(str, tag).lower() for t in tags)

    return questions_df[questions_df["tags"].map(_contains_tag)]


def get_least_recently_asked_on_discord(
    questions: pd.DataFrame,
) -> pd.DataFrame:
    """Get all questions with oldest date and shuffle them"""
    # pylint:disable=unused-variable
    oldest_date = questions["last_asked_on_discord"].min()
    return questions.query("last_asked_on_discord == @oldest_date")
