from __future__ import annotations

from datetime import datetime
from typing import Any, Literal, TypedDict

from codaio import Cell, Row

from utilities.time_utils import adjust_date


def parse_question_row(row: Row) -> QuestionRow:
    """Parse a raw row from
    [All answers](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/All-Answers_sudPS#_lul8a)
    """
    row_dict = row.to_dict()
    title = row_dict["Edit Answer"]
    url = row_dict["Link"]
    status = row_dict["Status"]
    # remove empty strings
    tags = [tag for tag in row_dict["Tags"].split(",") if tag]
    last_asked_on_discord = adjust_date(row_dict["Last Asked On Discord"])
    doc_last_edited = adjust_date(row_dict["Doc Last Edited"])
    alternate_phrasings = [
        alt for alt in row_dict["Alternate Phrasings"].split(",") if alt
    ]
    return {
        "id": row.id,
        "title": title,
        "url": url,
        "status": status,
        "tags": tags,
        "alternate_phrasings": alternate_phrasings,
        "last_asked_on_discord": last_asked_on_discord,
        "doc_last_edited": doc_last_edited,
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
    alternate_phrasings: list[str]
    last_asked_on_discord: datetime
    doc_last_edited: datetime
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

QUESTION_STATUS_ALIASES: dict[str, QuestionStatus] = {
    "bulletpoint": "Bulletpoint sketch",
    "del": "Marked for deletion",
    "deleted": "Marked for deletion",
    "duplicated": "Duplicate",
    "published": "Live on site",
}

REVIEW_STATUSES: set[QuestionStatus] = {
    "Bulletpoint sketch",
    "In progress",
    "In review",
}
