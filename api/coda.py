"""#TODO
1. printing better messages when posting multiple gdoc links
"""
from __future__ import annotations

from datetime import datetime as dt
import os
from typing import cast, Optional

import pandas as pd
import requests
from structlog import get_logger


from api.utilities.coda_utils import (
    parse_coda_question,
    CodaQuestion,
    DEFAULT_DATE,
    request_succesful
)

log = get_logger()


class Coda:
    """Gathers everything for interacting with coda"""

    __instance: Optional[Coda] = None

    CODA_API_TOKEN = os.environ["CODA_API_TOKEN"]
    DOC_ID = (
        "ah62XEPvpG" if os.getenv("ENVIRONMENT_TYPE") == "development" else "fau7sl2hmG"
    )
    ALL_ANSWERS_TABLE_ID = "table-YvPEyAXl8a"
    STATUSES_GRID_ID = "grid-IWDInbu5n2"
    TEAM_GRID_ID = "grid-pTwk9Bo_Rc"
    REQUEST_TIMEOUT = 5

    # Caching tables
    users_df: pd.DataFrame
    users_last_fetched: dt
    questions_df: pd.DataFrame
    questions_last_fetched: dt

    def __init__(self):
        assert self.__instance is None
        self.__instance = self
        self.class_name = "Coda API"
        self.log = get_logger()

        # Caching tables
        self.users_last_fetched = DEFAULT_DATE
        self.questions_last_fetched = DEFAULT_DATE
        self.get_users_df(use_cache=False)
        self.get_questions_df(use_cache=False)

    @classmethod
    def get_instance(cls) -> Coda:
        if cls.__instance:
            return cls.__instance
        return cls()

    @property
    def auth_headers(self) -> dict[str, str]:
        """Get authorization headers for coda requests"""
        return {"Authorization": f"Bearer {self.CODA_API_TOKEN}"}

    #######################
    #   Getters - Users   #
    #######################

    def get_users_df(self, *, use_cache: bool = True) -> pd.DataFrame:
        """Get the [Team grid](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/Team_sur3i#Team_tu_Rc/r5) with info about users"""
        if use_cache and self.users_cache_up_to_date():
            return self.users_df

        uri = f"https://coda.io/apis/v1/docs/{self.DOC_ID}/tables/{self.TEAM_GRID_ID}/rows"
        params = {"valueFormat": "simple", "useColumnNames": True}
        response = requests.get(
            uri,
            params=params,
            headers=self.auth_headers,
            timeout=self.REQUEST_TIMEOUT,
        )
        if not request_succesful(response):
            self.log.error(
                self.class_name,
                msg="couldn't get users table",
                uri=uri,
                params=params,
                response=response,
            )
            response.raise_for_status()

        self.users_last_fetched = dt.now()
        users_df = pd.DataFrame(item["values"] for item in response.json()["items"])
        self.users_df = users_df
        return users_df

    def get_user_row(self, field: str, value: str) -> Optional[dict]:
        """Get user row from the users table using a query with the following form

        `"<field/column name>":"<value>"`
        """
        if self.users_cache_up_to_date():
            query_expr = f"{field} == @value"
            users_filtered = self.users_df.query(query_expr)
            if not users_filtered.empty:
                return users_filtered.iloc[0].to_dict()

        uri = f"https://coda.io/apis/v1/docs/{self.DOC_ID}/tables/{self.TEAM_GRID_ID}/rows"
        params = {
            "valueFormat": "simple",
            "useColumnNames": True,
            "query": f'"{field}":"{value}"',
            "limit": 1,
        }
        response = requests.get(
            uri, headers=self.auth_headers, params=params, timeout=self.REQUEST_TIMEOUT
        )
        if not request_succesful(response):
            self.log.error(
                self.class_name,
                msg="couldn't get user row, unsuccessful request",
                field=field,
                value=value,
                uri=uri,
                params=params,
                response=response,
            )
            return
        if users := response.json()["items"]:
            return users[0]

    ###########################
    #   Getters - Questions   #
    ###########################

    def get_questions_df(
        self, *, status: Optional[str] = None, use_cache: bool = False
    ) -> pd.DataFrame:
        """Get questions from with `status="Not started"`"""
        if use_cache and self.questions_cache_up_to_date():
            return self.questions_df

        request_res = self.send_all_answers_rows_request(status)
        rows = [parse_coda_question(row) for row in request_res["items"]]
        questions = pd.DataFrame(rows)
        self.questions_df = questions
        return questions

    def get_questions_by_ids(
        self, question_ids: list[str]
    ) -> dict[str, CodaQuestion]: #TODO: handle questions that couldn't be found?
        """Get many question by their ids in "All Answers" table.
        Returns `ParsedRow` or `None` (if question with that id doesn't exist)
        """
        questions = self.get_questions_df()
        id2question = cast(
            dict[str, CodaQuestion], questions.set_index("id").to_dict(orient="records")
        )
        return {qid: id2question[qid] for qid in question_ids if qid in id2question}

    def get_question_by_id(
        self, questions_id: str, *, use_cache: bool = True
    ) -> CodaQuestion:
        """Get question by id in "All Answers" table.
        Returns `ParsedRow` or `None` (if question with that id doesn't exist)
        """
        if use_cache and self.questions_cache_up_to_date():
            if questions_id in self.questions_df["id"].tolist():
                return cast(
                    CodaQuestion,
                    self.questions_df.query("id == @row_id").iloc[0].to_dict(),
                )

        uri = f"https://coda.io/apis/v1/docs/{self.DOC_ID}/tables/{self.ALL_ANSWERS_TABLE_ID}/rows/{questions_id}"
        params = {
            "valueFormat": "simple",
            "useColumnNames": True,
        }
        response = requests.get(
            uri, params=params, headers=self.auth_headers, timeout=self.REQUEST_TIMEOUT
        )
        if not request_succesful(response):
            self.log.error(
                self.class_name,
                msg="Couldn't get question by ID",
                questions_id=questions_id,
                uri=uri,
                params=params,
                response=response,
            )

        return parse_coda_question(response.json())

    def get_questions_by_gdoc_links(self, urls: list[str]) -> list[CodaQuestion]:
        """Get question by link to its GDoc.
        Returns `ParsedRow` or `None` (if question with that id doesn't exist)
        """
        questions = self.get_questions_df()
        questions_queried = questions[
            questions["url"].map(lambda qurl: any(qurl.startswith(url) for url in urls))
        ]
        if questions_queried.empty:
            return []
        return cast(list[CodaQuestion], questions_queried.to_dict(orient="records"))

    def send_all_answers_rows_request(self, status: Optional[str] = None) -> dict:
        """Get rows from "All Answers" table in our coda"""
        params = {
            "valueFormat": "simple",
            "useColumnNames": True,
            "visibleOnly": False,
            "limit": 1000,
        }
        # optionally query by status
        if status:
            params["query"] = f'"Status":"{status}"'
        uri = f"https://coda.io/apis/v1/docs/{self.DOC_ID}/tables/{self.ALL_ANSWERS_TABLE_ID}/rows"
        response = requests.get(
            uri, headers=self.auth_headers, params=params, timeout=self.REQUEST_TIMEOUT
        )
        if not request_succesful(response):
            self.log.response(
                self.class_name,
                msg="Couldn't get All Answers table",
                params=params,
                uri=uri,
                response=response,
            )
            response.raise_for_status()

        return response.json()

    #####################
    #   Getters - Doc   #
    #####################

    def get_doc(self) -> dict:
        uri = f"https://coda.io/apis/v1/docs/{self.DOC_ID}"
        response = requests.get(
            uri, headers=self.auth_headers, timeout=self.REQUEST_TIMEOUT
        )
        if not request_succesful(response):
            self.log.error(
                self.class_name, msg="Couldn't get coda doc", uri=uri, response=response
            )
            response.raise_for_status()
        return response.json()

    #####################
    #   Caching utils   #
    #####################

    def get_coda_last_update_time(self) -> dt:
        # this is a bit hacky, but should work (?)
        coda_doc = self.get_doc()
        last_update_time = dt.fromisoformat(coda_doc["updatedAt"].replace("Z", ""))
        return last_update_time

    def users_cache_up_to_date(self) -> bool:
        return self.get_coda_last_update_time() <= self.users_last_fetched

    def questions_cache_up_to_date(self) -> bool:
        return self.get_coda_last_update_time() <= self.questions_last_fetched

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

        response = self.send_all_answers_rows_request()
        tags = set()
        for row in response["items"]:
            if tag_string := row["values"]["Tags"]:
                tags.update(tag_string.split(","))
        return sorted(tags)

    def get_all_statuses(self) -> list[str]:
        """Get all valid Status values from table in admin panel"""
        uri = f"https://coda.io/apis/v1/docs/{self.DOC_ID}/tables/{self.STATUSES_GRID_ID}/rows"
        params = {
            "valueFormat": "rich",
            "useColumnNames": True,
        }

        response = requests.get(
            uri, params=params, headers=self.auth_headers, timeout=self.REQUEST_TIMEOUT
        )
        if not request_succesful(response):
            self.log.error(
                self.class_name,
                msg="Couldn't get statuses from statuses table",
                uri=uri,
                params=params,
                response=response,
            )
        return sorted(r["name"] for r in response.json()["items"])

    ##########################
    #   Updating questions   #
    ##########################

    def update_question_status(
        self,
        question_id: str,
        status: str,
    ) -> None: # Optional[str]: # response message (?)
        uri = f"https://coda.io/apis/v1/docs/{self.DOC_ID}/tables/{self.ALL_ANSWERS_TABLE_ID}/rows/{question_id}"
        payload = {
            "row": {
                "cells": [
                    {"column": "Status", "value": status},
                ],
            },
        }
        requests.put(
            uri,
            headers=self.auth_headers,
            json=payload,
            timeout=self.REQUEST_TIMEOUT,
        )


    def update_questions_last_asked_date(self, question_ids: list[str]) -> None:
        """Update the "Last Asked on Discord" field in "All Answers" table for many questions"""
        current_time = dt.now().isoformat()
        for q_id in question_ids:
            self.update_question_last_asked_date(q_id, current_time)

    def update_question_last_asked_date(
        self, question_id: str, current_time: str
    ) -> None:
        """Update the "Last Asked on Discord" field in table for the question"""
        payload = {
            "row": {
                "cells": [
                    {"column": "Last Asked On Discord", "value": current_time},
                ],
            },
        }
        uri = f"https://coda.io/apis/v1/docs/{self.DOC_ID}/tables/{self.ALL_ANSWERS_TABLE_ID}/rows/{question_id}"
        response = requests.put(
            uri, headers=self.auth_headers, json=payload, timeout=self.REQUEST_TIMEOUT
        )
        response.raise_for_status()  # Throw if there was an error.
        log.info(
            self.class_name,
            msg=f"Updated question with id {question_id} to time {current_time}",
        )

    def _reset_dates(self) -> None:
        """Reset all questions' dates (util, not to be used by Stampy)"""
        questions = self.get_questions_df()
        questions_with_dt_ids = questions[
            questions["last_asked_on_discord"] != DEFAULT_DATE
        ]["id"].tolist()
        for question_id in questions_with_dt_ids:
            self.update_question_last_asked_date(question_id, "")
