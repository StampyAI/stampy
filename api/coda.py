"""#TODO
1. printing better messages when posting multiple gdoc links
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
import os
from typing import cast, Optional

from codaio import Coda, Document, Table
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

    # Constance
    CODA_API_TOKEN = os.environ["CODA_API_TOKEN"]
    DOC_ID = (
        "ah62XEPvpG" if os.getenv("ENVIRONMENT_TYPE") == "development" else "fau7sl2hmG"
    )
    ALL_ANSWERS_TABLE_ID = "table-YvPEyAXl8a"
    STATUSES_GRID_ID = "grid-IWDInbu5n2"
    TEAM_GRID_ID = "grid-pTwk9Bo_Rc"
    REQUEST_TIMEOUT = 5

    users: Table
    id2question_row: dict[str, QuestionRow]
    questions_df: pd.DataFrame

    def __init__(self):
        assert self.__instance is None
        self.__instance = self
        self.class_name = "Coda API"
        self.log = get_logger()

        os.environ["CODA_API_KEY"] = self.CODA_API_TOKEN
        self.coda = Coda.from_environment()

        self.reset_questions_cache()

    @property
    def doc(self) -> Document:
        return Document.from_environment(self.DOC_ID)
    
    @classmethod
    def get_instance(cls) -> CodaAPI:
        if cls.__instance is None:
            cls.__instance = cls()
        return cls.__instance

    def reset_questions_cache(self) -> None:
        self.pending_update_question_ids = []
        questions = self.doc.get_table(self.ALL_ANSWERS_TABLE_ID)
        question_rows = [parse_question_row(row) for row in questions.rows()]
        self.id2question_row = {row["id"]: row for row in question_rows}
        self.questions_df = pd.DataFrame(question_rows)
        
    def update_questions_cache(self) -> None:
        
        questions = self.doc.get_table(self.ALL_ANSWERS_TABLE_ID)

        for qid in self.pending_update_question_ids:
            qrow = parse_question_row(questions.get_row_by_id(qid))
            breakpoint()
            self.id2question_row[qid] = qrow
            #TODO safeguards against failing?
            df_qid = self.questions_df.query("id == @qid").index[0]
            self.questions_df.loc[df_qid] = qrow #type:ignore

        self.pending_update_question_ids.clear()
        

    def reset_users_cache(self) -> None:
        self.users = self.doc.get_table(self.TEAM_GRID_ID)
        self.log.info(
            self.class_name,
            msg="Updated users cache",
        )
        

    #############
    #   Users   #
    #############

    def get_user_row(self, field: str, value: str) -> Optional[dict]:
        """Get user row from the users table using a query with the following form

        `"<field/column name>":"<value>"`
        """
        rows = self.users.find_row_by_column_name_and_value(column_name=field, value=value)
        if rows:
            return rows[0].to_dict()

    def update_user_stamps(self, user: DiscordUser, stamp_count: float) -> None:
        rows = self.users.find_row_by_column_name_and_value(
            column_name="Discord handle", value=get_user_handle(user)
        )
        if rows is None:
            self.log.error(self.class_name, msg="Couldn't find user in table", user=user)
            return
        row = rows[0]
        updated_cells = make_updated_cells({"Stamp count": stamp_count})
        self.users.update_row(row, updated_cells)

    #################
    #   Questions   #
    #################

    def get_questions_by_gdoc_links(self, urls: list[str]) -> list[QuestionRow]:
        """Get question by link to its GDoc.
        Returns `ParsedRow` or `None` (if question with that id doesn't exist)
        """
        questions_df_queried = self.questions_df[
            self.questions_df["url"].map(
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
        # Optional[str]: # response message (?)
        row = self.id2question_row[question_id]
        self.doc.get_table(self.ALL_ANSWERS_TABLE_ID).update_row(row["row"], make_updated_cells({"Status": status}))
        self.pending_update_question_ids.append(row["id"])

    def update_question_last_asked_date(
        self, question_id: str, current_time: str
    ) -> None:
        """Update the "Last Asked on Discord" field in table for the question"""
        row = self.id2question_row[question_id]
        self.doc.get_table(self.ALL_ANSWERS_TABLE_ID).update_row(row["row"], make_updated_cells({"Last Asked On Discord": current_time}))
        self.pending_update_question_ids.append(row["id"])

    def _reset_dates(self) -> None:
        """Reset all questions' dates (util, not to be used by Stampy)"""
        questions_df = self.questions_df
        questions_with_dt_ids = questions_df[
            questions_df["last_asked_on_discord"] != DEFAULT_DATE
        ]["id"].tolist()
        for question_id in questions_with_dt_ids:
            self.update_question_last_asked_date(question_id, "")

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
        tags = set()
        for row_tags in self.questions_df["tags"]:
            tags.update(row_tags)
        return sorted(tags)

    def get_all_statuses(self) -> list[str]:
        """Get all valid Status values from table in admin panel"""
        status_table = self.doc.get_table(self.STATUSES_GRID_ID)
        status_vals = {r["Status"].value for r in status_table.rows()}
        return sorted(status_vals)
