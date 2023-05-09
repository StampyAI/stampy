from __future__ import annotations

from datetime import datetime, timedelta
import os
from textwrap import dedent
from typing import cast, get_args, Optional, TYPE_CHECKING

from codaio import Coda, Document, Row
import pandas as pd
from structlog import get_logger


from api.utilities.coda_utils import (
    make_updated_cells,
    parse_question_row,
    QuestionRow,
    QuestionStatus,
    DEFAULT_DATE,
)
from utilities import is_in_testing_mode
from utilities.discordutils import DiscordUser
from utilities.serviceutils import ServiceMessage
from utilities.utilities import fuzzy_contains, get_user_handle, shuffle_df

if TYPE_CHECKING:
    from utilities.question_querying_utils import (
        QuestionQuery,
    )


log = get_logger()


class CodaAPI:
    """Gathers everything for interacting with
    [coda](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/Get-involved_susRF#_lufSr)."""

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

    #############
    #   Users   #
    #############

    def update_users_cache(self) -> None:
        """Update the cache of the
        [Team table](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/Team_sur3i#_luBnC).

        Gets called during initialization and every ~23 hours by StampCollection module,
        during updating all stamps in the coda table.
        """
        # get coda table
        self.users = self.doc.get_table(self.TEAM_GRID_ID)
        # log
        self.log.info(
            self.class_name, msg="Updated users cache", num_users=self.users.row_count
        )

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

    def update_questions_cache(self) -> None:
        """Update the cache of the
        [All answers coda table](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a).

        Gets called during initialization and every ~10 minutes by Questions module.
        """
        # get coda table
        questions = self.doc.get_table(self.ALL_ANSWERS_TABLE_ID)
        # parse its rows
        question_rows = [parse_question_row(row) for row in questions.rows()]
        # convert into dataframe
        self.questions_df = pd.DataFrame(question_rows).set_index("id", drop=False)
        # store date of update
        self.questions_cache_last_update = datetime.now()
        # log
        self.log.info(
            self.class_name,
            msg="Updated questions cache",
            num_questions=len(self.questions_df),
        )

    def get_question_by_id(self, question_id: str) -> Optional[QuestionRow]:
        """Get QuestionRow from questions cache by its ID"""
        if question_id not in self.questions_df.index.tolist():
            return
        return cast(QuestionRow, self.questions_df.loc[question_id].to_dict())

    def get_questions_by_gdoc_links(self, urls: list[str]) -> list[QuestionRow]:
        """Get questions by url links to their GDocs.
        Returns list of `QuestionRow`s.
        Empty list (`[]`) if couldn't find questions with any of the links.
        """
        questions_df = self.questions_df
        # query for questions whose url starts with any of the urls that were passed
        questions_df_queried = questions_df[  # pylint:disable=unsubscriptable-object
            questions_df["url"].map(  # pylint:disable=unsubscriptable-object
                lambda question_url: any(question_url.startswith(url) for url in urls)
            )
        ]
        if questions_df_queried.empty:
            return []
        questions = questions_df_queried.to_dict(orient="records")
        return cast(list[QuestionRow], questions)

    def get_question_by_title(self, title: str) -> Optional[QuestionRow]:
        questions_df = self.questions_df
        questions_df_queried = questions_df[  # pylint:disable=unsubscriptable-object
            questions_df["title"].map(  # pylint:disable=unsubscriptable-object
                lambda question_title: fuzzy_contains(question_title, title)
            )
        ]
        if questions_df_queried.empty:
            return
        if len(questions_df_queried) > 1:
            self.log.warning(
                self.class_name,
                msg=f'Found {len(questions_df_queried)} matching title query "{title}". Returning first.',
                results=questions_df_queried["title"].tolist(),
            )
        question = questions_df_queried.iloc[0].to_dict()
        return cast(QuestionRow, question)

    def update_question_status(
        self,
        question_id: str,
        status: QuestionStatus,
    ) -> None:
        """Update the status of a question in the
        [All answers table](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a).
        Also, update the local cache accordingly.
        """
        # get question row
        question = self.get_question_by_id(question_id)
        if question is None:
            self.log.warning(
                self.class_name,
                msg="Tried updating a question's status but couldn't find a question with that ID",
                question_id=question_id,
                status=status,
            )
            return
        # update coda table
        self.doc.get_table(self.ALL_ANSWERS_TABLE_ID).update_row(
            question["row"], make_updated_cells({"Status": status})
        )
        # update local cache
        self.questions_df.loc[question_id]["status"] = status

    def update_question_last_asked_date(
        self, question_id: str, current_time: datetime
    ) -> None:
        """Update the `Last Asked On Discord` field of a question in the
        [All answers table](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a).
        Also, update the local cache accordingly"""
        # get question row
        question = self.get_question_by_id(question_id)
        if question is None:
            self.log.warning(
                self.class_name,
                msg="Tried updating a question's `Last Asked On Discord` field but couldn't find a question with that ID",
                question_id=question_id,
                current_time=current_time,
            )
            return
        # update coda table
        self.doc.get_table(self.ALL_ANSWERS_TABLE_ID).update_row(
            question["row"],
            make_updated_cells({"Last Asked On Discord": current_time.isoformat()}),
        )
        # update local cache
        self.questions_df.loc[question_id]["last_asked_on_discord"] = current_time

    def _reset_dates(self) -> None:
        """Reset all questions' dates (util, not to be used by Stampy)"""
        for _, r in self.questions_df.iterrows():
            if r["last_asked_on_discord"] != DEFAULT_DATE:
                question_id = cast(str, r["question_id"])
                self.update_question_last_asked_date(question_id, DEFAULT_DATE)

    ###############
    #   Finding   #
    ###############

    async def query_for_questions(
        self,
        query: QuestionQuery,
        message: ServiceMessage,
        *,
        least_recently_asked_unpublished: bool = False,
    ) -> list[QuestionRow]:
        """Finds questions based on request data

        Args
        ----------
        query: QuestionQuery
            - A 2-tuple where the first value is a string indicating the type of the second value. Possible variants are:
                - ("Last", "last" or "it") - requesting the last question (e.g., `s, get last question`, `s, post it`)
                - ("GDocLinks", list of strings) - links to GDocs of particular answers
                - ("Title", question title) - doesn't have to be the exact, perfectly matching title, fuzzily matching substring is enough
                - ("Filter", QuestionFilterQuery) - a NamedTuple containing
                    - status: Optional[QuestionStatus] - optional query for questions
                    - tag: Optional[str] - optional query for questions
                    - limit: int - how many questions at most should be returned

        message: ServiceMessage
            - The original message from which that request was parsed.

        least_recently_asked_unpublished: bool, default=False
            - If `True` and `query` is of type "Filter" with `status=None` and `tag=None`, then questions will be filtered for those which are not `Live on site` and choose randomly from them
            - Should be set to `True` when querying for questions for posting

        Returns
        ----------
        A list of question rows matching the query.
        """
        questions_df = self.questions_df

        # QuestionGDocLinks
        if query[0] == "GDocLinks":
            gdoc_links = query[1]
            questions = self.get_questions_by_gdoc_links(gdoc_links)
            if not questions:
                return []
            return questions

        # QuestionTitle
        if query[0] == "Title":
            question_title = query[1]
            question = self.get_question_by_title(question_title)
            if question is None:
                return []
            return [question]

        # QuestionLast
        if query[0] == "Last":
            if self.last_question_id is None:
                return []
            question = cast(QuestionRow, self.get_question_by_id(self.last_question_id))
            return [question]

        ##############
        #   Filter   #
        ##############

        status, tag, limit = query[1]
        least_recently_asked_unpublished = (
            least_recently_asked_unpublished and status is None and tag is None
        )

        # (explained in this method's docstring)
        if least_recently_asked_unpublished:
            questions_df = questions_df.query("status != 'Live on site'")
        elif status is not None:
            questions_df = questions_df.query("status == @status")

        # if tag was specified, filter for questions having that tag
        questions_df = filter_on_tag(questions_df, tag)

        if least_recently_asked_unpublished:
            # get the least recently asked and shuffle them
            questions_df = get_least_recently_asked_on_discord(questions_df)
            questions_df = shuffle_df(questions_df)

        # get specified number of questions (default [if unspecified] is 1)
        if limit > 5:
            await message.channel.send(f"{limit} is to much. I'll give you up to 5.")

        # filter on max num of questions
        questions_df = questions_df.sort_values(
            "last_asked_on_discord", ascending=False
        ).iloc[: min(limit, 5)]
        if questions_df.empty:
            return []
        questions = questions_df.to_dict(orient="records")
        return cast(list[QuestionRow], questions)

    ResponseText = ResponseWhy = str

    async def get_response_text_and_why(
        self,
        questions: list[QuestionRow],
        query: QuestionQuery,
        message: ServiceMessage,
    ) -> tuple[ResponseText, ResponseWhy]:
        """Get `text` and `why` arguments for `Response` for questions returned by
        `query_for_questions` using `query`.
        """

        FOUND_NOTHING = " but I found nothing"

        # QuestionGDocLinks
        if query[0] == "GDocLinks":
            why = f"{message.author.name} queried for questions matching one or more GDoc links"
            if not questions:
                return ("These links don't lead to any questions", why + FOUND_NOTHING)
            text = "Here it is:" if len(questions) == 1 else "Here they are:"
            return text, why

        # QuestionTitle
        if query[0] == "Title":
            question_title = query[1]
            why = f'{message.author.name} asked for a question with title matching "{question_title}"'
            if not questions:
                return ("I found no question matching that title", why + FOUND_NOTHING)
            return "Here it is:", why

        # QuestionLast
        if query[0] == "Last":
            mention = query[1]
            why = f"{message.author.name} asked about the last question"
            if not questions:
                return (
                    f'What do you mean by "{mention}"?',
                    why
                    + " but I don't remember what it was because I recently rebooted",
                )
            return f'The last question was:\n"{questions[0]["title"]}"', why

        ######################
        # QuestionFilterData #
        ######################

        _status, _tag, limit = query[1]

        why = f"{message.author.name} asked me for questions{FOUND_NOTHING}"
        if not questions:
            return "I found no questions", why
        if len(questions) == limit == 1:
            text = "Here is a question"
        elif len(questions) == 1:
            text = "I found one question"
        elif len(questions) < limit:
            text = f"I found {len(questions)} questions"
        else:
            text = f"Here are {len(questions)} questions"

        return text, why + f" and I found {len(questions)}"

    ######################################
    #   Getters for valid field values   #
    ######################################

    def get_status_shorthand_dict(self) -> dict[str, QuestionStatus]:
        """Get dictionary mapping question statuses and status shorthands
        (e.g. "bs" for "Bulletpoint sketch") to valid `Status` field values.
        """
        # Workaround to make mock request during testing
        if is_in_testing_mode():
            return {}

        statuses = self.get_all_statuses()
        status_shorthand_dict = {}
        for status in statuses:
            # map default status name
            status_shorthand_dict[status] = status
            # map lowercased status name
            status_shorthand_dict[status.lower()] = status
            # map acronym shorthand
            shorthand = "".join(word[0].lower() for word in status.split())
            status_shorthand_dict[shorthand] = status
        return status_shorthand_dict

    def get_all_tags(self) -> list[str]:
        """Get all valid
        [question Tags](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/Tags_su-dP#_luAhW).
        """
        # Workaround to make mock request during testing
        if is_in_testing_mode():
            return []
        tags_table = self.doc.get_table(self.TAGS_GRID_ID)
        tags_vals = {row["Tag name"] for row in tags_table.to_dict()}
        return sorted(tags_vals)

    def get_all_statuses(self) -> list[str]:
        """Get all valid values for the question `Status` field
        from the table in
        [Admin Panel](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/Admin-Panel_su93i#_luy_h).
        """
        # get coda table
        status_table = self.doc.get_table(self.STATUSES_GRID_ID)
        # load status values from it
        coda_status_vals = {r["Status"].value for r in status_table.rows()}
        # load status values defined in code
        code_status_vals = set(get_args(QuestionStatus))
        # if mismatch, log and raise errory
        if coda_status_vals != code_status_vals:
            msg = "Status values defined in api/utilities/coda_utils.py don't match the values in coda"
            self.log.error(
                self.class_name,
                msg="Status values defined in api/utilities/coda_utils.py don't match the values in coda",
                code_status_vals=code_status_vals,
                coda_status_vals=coda_status_vals,
            )
            msg += f"; {code_status_vals=}; {coda_status_vals=}"
            raise AssertionError(msg)
        return sorted(coda_status_vals)


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
