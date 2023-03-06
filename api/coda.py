"""#TODO
1. printing better messages when posting multiple gdoc links
"""
from __future__ import annotations

import os
from typing import cast, Optional

from codaio import Coda, Document
import pandas as pd
from structlog import get_logger


from api.utilities.coda_utils import (
    parse_question_row,
    QuestionRow,
    DEFAULT_DATE,
    make_updated_cells
)
from utilities import is_in_testing_mode

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

    users_df: pd.DataFrame
    questions_df: pd.DataFrame

    def __init__(self):
        assert self.__instance is None
        self.__instance = self
        self.class_name = "Coda API"
        self.log = get_logger()

        # Coda API library
        os.environ["CODA_API_KEY"] = self.CODA_API_TOKEN
        self.coda = Coda.from_environment()
        self.users = self.doc.get_table(self.TEAM_GRID_ID)
        self.fetch_users_df()
        self.questions = self.doc.get_table(self.ALL_ANSWERS_TABLE_ID)
        self.fetch_questions_df()

    @classmethod
    def get_instance(cls) -> CodaAPI:
        if cls.__instance:
            return cls.__instance
        return cls()

    @property
    def doc(self) -> Document:
        return Document.from_environment(self.DOC_ID)

    #######################
    #   Getters - Users   #
    #######################

    def fetch_users_df(self) -> None:
        self.user_df = pd.DataFrame(self.users.to_dict())

    def get_users_df(self) -> pd.DataFrame:
        """Get the [Team grid](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/Team_sur3i#Team_tu_Rc/r5) with info about users"""
        if not self.users_df_up_to_date():
            self.fetch_users_df()
        return self.users_df

    def get_user_row(self, field: str, value: str) -> Optional[dict]:
        """Get user row from the users table using a query with the following form

        `"<field/column name>":"<value>"`
        """
        users_df = self.get_users_df()
        users_df_filtered = users_df[users_df[field] == value]
        if not users_df_filtered.empty:
            return users_df_filtered.iloc[0].to_dict()

    ###########################
    #   Getters - Questions   #
    ###########################

    def fetch_questions_df(self) -> None:
        """#TODO docstring"""
        question_rows = [parse_question_row(row) for row in self.questions.rows()]
        self.questions_df = pd.DataFrame(question_rows)

    def get_questions_df(
        self,
    ) -> pd.DataFrame:
        """Get questions from with `status="Not started"`"""
        if not self.questions_df_up_to_date():
            self.fetch_questions_df()
        return self.questions_df

    def get_questions_by_ids(
        self, question_ids: list[str]
    ) -> dict[str, QuestionRow]:  # TODO: handle questions that couldn't be found?
        """Get many question by their ids in "All Answers" table.
        Returns `ParsedRow` or `None` (if question with that id doesn't exist)
        """
        id2question = {
            qid: parse_question_row(self.questions[qid]) for qid in question_ids
        }
        return id2question

    def get_question_by_id(self, question_id: str) -> QuestionRow:
        """Get question by id in "All Answers" table.
        Returns `ParsedRow` or `None` (if question with that id doesn't exist)
        """
        return parse_question_row(self.questions[question_id])

    def get_questions_by_gdoc_links(self, urls: list[str]) -> list[QuestionRow]:
        """Get question by link to its GDoc.
        Returns `ParsedRow` or `None` (if question with that id doesn't exist)
        """
        questions_df = self.get_questions_df()
        questions_df_queried = questions_df[
            questions_df["url"].map(
                lambda qurl: any(qurl.startswith(url) for url in urls)
            )
        ]
        if questions_df_queried.empty:
            return []
        return cast(list[QuestionRow], questions_df_queried.to_dict(orient="records"))

    #####################
    #   Caching utils   #
    #####################

    def users_df_up_to_date(self) -> bool:  # TODO docstrings to both
        return self.doc.updated_at <= self.users.updated_at

    def questions_df_up_to_date(self) -> bool:
        return self.doc.updated_at <= self.questions.updated_at

    #######################
    #   Getters - Other   #
    #######################

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
        statuses_table = self.doc.get_table(self.STATUSES_GRID_ID)
        statuses_df = pd.DataFrame(statuses_table.to_dict())
        return sorted(statuses_df["Status"].unique())

    ##########################
    #   Updating questions   #
    ##########################

    def update_question_status(
        self,
        question_id: str,
        status: str,
    ) -> None:  
        # Optional[str]: # response message (?)
        row = self.questions[question_id]
        updated_cells = make_updated_cells({"Status": status})
        self.questions.update_row(row, updated_cells)

    def update_question_last_asked_date(
        self, question_id: str, current_time: str
    ) -> None:
        """Update the "Last Asked on Discord" field in table for the question"""
        row = self.questions[question_id]
        updated_cells = make_updated_cells({"Last Asked On Discord": current_time})
        self.questions.update_row(row, updated_cells)

    def _reset_dates(self) -> None:
        """Reset all questions' dates (util, not to be used by Stampy)"""
        questions = self.get_questions_df()
        questions_with_dt_ids = questions[
            questions["last_asked_on_discord"] != DEFAULT_DATE
        ]["id"].tolist()
        for question_id in questions_with_dt_ids:
            self.update_question_last_asked_date(question_id, "")
