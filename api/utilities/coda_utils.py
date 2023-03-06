from __future__ import annotations

from datetime import datetime
from pprint import pformat
import requests
from typing import Any, TypedDict

from codaio import Cell, Row

DEFAULT_DATE = datetime(1, 1, 1, 0)


def adjust_date(date_str: str) -> datetime:
    """If date is in isoformat, parse it.
    Otherwise, assign earliest date possible.
    """
    if not date_str:
        return DEFAULT_DATE
    return datetime.fromisoformat(date_str.split("T")[0])


def make_post_question_message(question_row: QuestionRow) -> str:
    """Make question message from questions DataFrame row

    <title>\n
    <url>
    """
    return question_row["title"] + "\n" + question_row["url"]


def parse_question_row(row: Row) -> QuestionRow:
    """Parse a raw row from "All answers" table"""
    row_dict = row.to_dict()
    title = row_dict["Edit Answer"]
    url = row_dict["Link"]
    status = row_dict["Status"]
    # remove empty strings
    tags = [tag for tag in row_dict["Tags"].split(",") if row_dict["Tags"]]
    last_asked_on_discord = adjust_date(row_dict["Last Asked On Discord"])
    return {
        "id": row.id,
        "title": title,
        "url": url,
        "status": status,
        "tags": tags,
        "last_asked_on_discord": last_asked_on_discord,
    }


def make_updated_cells(col2val: dict[str, Any]) -> list[Cell]:
    """#TODO"""
    return [
        Cell(column=col, value_storage=val)  # type:ignore
        for col, val in col2val.items()
    ]


class QuestionRow(TypedDict):
    """Dict representing one row parsed from coda "All Answers" table"""

    id: str
    title: str
    url: str
    status: str
    tags: list[str]
    last_asked_on_discord: datetime


def request_succesful(response: requests.Response) -> bool:
    return response.status_code in (200, 202)
