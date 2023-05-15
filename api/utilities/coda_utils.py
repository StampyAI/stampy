from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypedDict

from codaio import Cell, Row
import requests

DEFAULT_DATE = datetime(1, 1, 1, 0)


def adjust_date(date_str: str) -> datetime:
    """If date is in isoformat, parse it.
    Otherwise, assign earliest date possible.
    """
    if not date_str:
        return DEFAULT_DATE
    return datetime.fromisoformat(date_str.split("T")[0])


def parse_question_row(row: Row) -> QuestionRow:
    """Parse a raw row from
    [All answers](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a)
    """
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
        "row": row,
    }


def make_updated_cells(col2val: dict[str, Any]) -> list[Cell]:
    """Make cells for updating coda Tables.
    Takes a dictionary mapping fields of a particular row to their new values
    """
    return [
        Cell(column=col, value_storage=val)  # type:ignore
        for col, val in col2val.items()
    ]


class QuestionRow(TypedDict):
    """Dictionary representing one row parsed from coda "All Answers" table"""

    id: str
    title: str
    url: str
    status: str
    tags: list[str]
    last_asked_on_discord: datetime
    row: Row


# Status of question in coda table
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
