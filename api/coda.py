from __future__ import annotations

from datetime import datetime, timedelta
import os
from typing import cast, Optional

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
from utilities.utilities import get_user_handle

log = get_logger()


class CodaAPI:
    """Gathers everything for interacting with coda"""

    # Singleton instance
    __instance: Optional[CodaAPI] = None

    # Constants
    CODA_API_TOKEN = os.environ["CODA_API_TOKEN"]
    DOC_ID = (
        "ah62XEPvpG" if os.getenv("ENVIRONMENT_TYPE") == "development" else "fau7sl2hmG"
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
        self.__instance = self
        self.class_name = "Coda API"
        self.log = get_logger()

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
        [users/team table](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/Team_sur3i#_lu_Rc)"""
        # get row
        row = self.get_user_row("Discord handle", get_user_handle(user))
        if row is None:
            self.log.info(
                self.class_name, msg="Couldn't find user in table", user=user
            )
            return
            
        # update table
        updated_cells = make_updated_cells({"Stamp count": stamp_count})
        self.users.update_row(row, updated_cells)

    #################
    #   Questions   #
    #################

    def get_question_row(self, question_id: str) -> QuestionRow:
        """Get QuestionRow by its ID"""
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

    def update_question_status(
        self,
        question_id: str,
        status: str,
    ) -> None:
        """Update status of a question in 
        [coda table](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a). 
        Also, update local cache accordingly.
        """
        # get row
        row = self.get_question_row(question_id)
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

    #############
    #   Other   #
    #############

    def get_status_shorthand_dict(self) -> dict[str, str]:
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
        return sorted(status_vals)
