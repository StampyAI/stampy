from __future__ import annotations

import re
from typing import cast, Literal, NamedTuple, Optional, Union
from api.coda import CodaAPI, QuestionStatus

coda_api = CodaAPI.get_instance()
status_shorthands = coda_api.get_status_shorthand_dict()
all_tags = coda_api.get_all_tags()


##########################
#   QuestionFilterData   #
##########################


class QuestionFilterDataNT(NamedTuple):
    status: Optional[QuestionStatus]
    tag: Optional[str]
    limit: int


QuestionFilterData = tuple[Literal["FilterData"], QuestionFilterDataNT]


def parse_question_filter_data(text: str) -> QuestionFilterDataNT:
    return QuestionFilterDataNT(
        status=parse_status(text),
        tag=parse_tag(text),
        limit=parse_questions_limit(text),
    )


_status_pat = "|".join(rf"\b{s}\b" for s in status_shorthands).replace(" ", r"\s")


def parse_status(text: str) -> Optional[QuestionStatus]:
    re_status = re.compile(
        rf"status\s*({_status_pat})",
        re.I | re.X,
    )
    if not (match := re_status.search(text)):
        return
    val = match.group(1)
    return status_shorthands[val.lower()]


def parse_tag(text: str) -> Optional[str]:
    """Parse string of tags extracted from message"""
    tag_group = (
        "(" + "|".join(all_tags).replace(" ", r"\s") + ")"
    )  # this \s may not be necessary (?)
    re_tag = re.compile(r"tag(?:s|ged(?:\sas)?)?\s+" + tag_group, re.I)
    if (match := re_tag.search(text)) is None:
        return None
    tag = match.group(1)
    tag_group = tag_group.replace(r"\s", " ")
    tag_idx = tag_group.lower().find(tag.lower())
    tag = tag_group[tag_idx : tag_idx + len(tag)]
    return tag


def parse_questions_limit(text: str) -> int:
    re_pre = re.compile(r"(\d{1,2})\sq(?:uestions?)?", re.I)
    re_post = re.compile(r"n\s?=\s?(\d{1,2})", re.I)
    if (match := (re_pre.search(text) or re_post.search(text))) and (
        num := match.group(1)
    ).isdigit():
        return int(num)
    return 1


########################
#   QuestionSpecData   #
########################


_re_last = re.compile(r"(?:i|info|get|post)\s(last|it)", re.I)


def parse_question_last(text: str) -> Optional[Literal["last", "it"]]:
    if match := _re_last.search(text):
        mention = match.group(1)
        return cast(Literal["last", "it"], mention)


_re_gdoc_link = re.compile(r"https://docs\.google\.com/document/d/[\w_-]+")


def parse_gdoc_links(text: str) -> list[str]:
    """Extract GDoc links from message content.
    Returns `[]` if message doesn't contain any GDoc link.
    """
    return _re_gdoc_link.findall(text)


_re_title = re.compile(r"\b(?:q|question|t|titled?)\s+([-\w\s]+)", re.I)


def parse_question_title(text: str) -> Optional[str]:
    if match := _re_title.search(text):
        question_title = match.group(1)
        return question_title


def parse_question_spec_data(text: str) -> Optional[QuestionSpecData]:
    # QuestionLast
    if mention := parse_question_last(text):
        return "Last", mention
    # QuestionGDocLinks
    if gdoc_links := parse_gdoc_links(text):
        return "GDocLinks", gdoc_links
    # QuestionTitle
    if question_title := parse_question_title(text):
        return "Title", question_title


def parse_question_request_data(text: str) -> QuestionRequestData:
    if spec_data := parse_question_spec_data(text):
        return spec_data
    return "FilterData", parse_question_filter_data(text)


QuestionSpecData = Union[
    tuple[Literal["Last"], Literal["last", "it"]],
    tuple[Literal["GDocLinks"], list[str]],
    tuple[Literal["Title"], str],
]


QuestionRequestData = Union[QuestionSpecData, QuestionFilterData]
