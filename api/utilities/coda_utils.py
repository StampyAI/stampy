from __future__ import annotations

from datetime import datetime as dt
from pprint import pformat
import requests
from typing import Any, TypedDict


DEFAULT_DATE = dt(1, 1, 1, 0)


def adjust_date(date_str: str) -> dt:
    """If date is in isoformat, parse it.
    Otherwise, assign earliest date possible.
    """
    if not date_str:
        return DEFAULT_DATE
    return dt.fromisoformat(date_str.split("T")[0])


def make_post_question_message(question_row: CodaQuestion) -> str:
    """Make question message from questions DataFrame row

    <title>\n
    <url>
    """
    return question_row["title"] + "\n" + question_row["url"]

def parse_coda_question(row: dict) -> CodaQuestion:
    """Parse a raw row from "All answers" table"""
    title = row["values"]["Edit Answer"]
    url = row["values"]["Link"]
    status = row["values"]["Status"]
    tags = row["values"]["Tags"].split(",")
    last_asked_on_discord = adjust_date(row["values"]["Last Asked On Discord"])
    return {
        "id": row["id"],
        "title": title,
        "url": url,
        "status": status,
        "tags": tags,
        "last_asked_on_discord": last_asked_on_discord,
    }






def pformat_to_codeblock(d: dict[Any, Any]) -> str:
    """`pformat` a dictionary and embed it in a code block
    (for nice display in discord message)
    """
    return "```\n" + pformat(d, sort_dicts=False) + "\n```"


class CodaQuestion(TypedDict):
    """Dict representing one row parsed from coda "All Answers" table"""

    id: str
    title: str
    url: str
    status: str
    tags: list[str]
    last_asked_on_discord: dt

def request_succesful(response: requests.Response) -> bool:
    return response.status_code in (200, 202)
