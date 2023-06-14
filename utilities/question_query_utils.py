from __future__ import annotations

import re
from typing import cast, overload, Literal, NamedTuple, Optional, Union

from api.coda import CodaAPI
from api.utilities.coda_utils import QuestionStatus
from utilities.utilities import mask_quoted_text

coda_api = CodaAPI.get_instance()
status_shorthands = coda_api._get_status_shorthand_dict()
all_tags = coda_api.get_all_tags()


###########################
#   QuestionFilterQuery   #
###########################


class QuestionFilterNT(NamedTuple):
    status: Optional[QuestionStatus]
    tag: Optional[str]
    limit: int


QuestionFilterQuery = tuple[Literal["Filter"], QuestionFilterNT]


def parse_question_filter(text: str) -> QuestionFilterNT:
    """Parse query specifying properties of questions we're looking for
    (status and tag) + limit (how many questions we want max)
    """
    return QuestionFilterNT(
        status=parse_status(text),
        tag=parse_tag(text),
        limit=parse_questions_limit(text),
    )


_status_pat = "|".join(rf"\b{s}\b" for s in status_shorthands)
_re_status = re.compile(rf"({_status_pat})", re.I)


def parse_status(text: str) -> Optional[QuestionStatus]:
    """Parse valid question status value from message text for querying questions database."""
    if not (match := _re_status.search(text)):
        return
    status_val = match.group(1)
    return status_shorthands[status_val.lower()]


_tag_pat = "|".join(rf"\b{t}\b" for t in all_tags)
_re_tag = re.compile(rf"({_tag_pat})", re.I)


def parse_tag(text: str) -> Optional[str]:
    """Parse valid tag from message text for querying questions database"""
    if "tag" not in text or (match := _re_tag.search(text)) is None:
        return None
    tag_val = match.group(1)
    tag_pat = _tag_pat.replace(r"\s", " ")
    tag_idx = tag_pat.lower().find(tag_val.lower())
    tag_val = tag_pat[tag_idx : tag_idx + len(tag_val)]
    return tag_val


_re_limit = re.compile(r"(\d\d?)\sq(?:uestions?)?", re.I)


def parse_questions_limit(text: str) -> int:
    """Parse limit/number of questions for querying questions database"""
    if match := _re_limit.search(text):
        if (num := match.group(1)).isdigit():
            return int(num)
    return 1


########################
#   QuestionSpecData   #
########################


_re_last = re.compile(r"(?:i|info|get|post)\s(last|it)", re.I)


def parse_question_last(text: str) -> Optional[Literal["last", "it"]]:
    """Parse the word referring to the last question, if somebody referred to it."""
    if match := _re_last.search(text):
        mention = match.group(1)
        return cast(Literal["last", "it"], mention)


_re_gdoc_link = re.compile(r"https://docs\.google\.com/document/d/[\w_-]+")


def parse_gdoc_links(text: str) -> list[str]:
    """Extract GDoc links from message content.
    Returns `[]` if message doesn't contain any GDoc link.
    """
    return _re_gdoc_link.findall(text)


_re_title = re.compile(r"\b(?:q|question|titled?)\s+([-\w\s]+)", re.I)


def parse_question_title(text: str) -> Optional[str]:
    """Parse a substring of the message which we want to match to question title"""
    if match := _re_title.search(text):
        question_title = match.group(1)
        return question_title


def parse_alt_phr(text: str) -> Optional[str]:
    start = text.find('"') + 1
    end = text.find('"', start)
    if -1 in (start, end):
        return
    return text[start:end]


@overload
def parse_question_spec_query(
    text: str,
) -> Optional[QuestionSpecQuery]:
    ...


@overload
def parse_question_spec_query(
    text: str, *, return_last_by_default: Literal[True]
) -> QuestionSpecQuery:
    ...


def parse_question_spec_query(
    text: str, *, return_last_by_default: bool = False
) -> Optional[QuestionSpecQuery]:  # TODO: raise or sth if no last
    """Parse data specifying concrete questions"""
    # QuestionLast
    if mention := parse_question_last(text):
        return "Last", mention
    # QuestionGDocLinks
    if gdoc_links := parse_gdoc_links(text):
        return "GDocLinks", gdoc_links
    # QuestionTitle
    # double quotes are used for specifying alternate phrasings,
    # so in order to remove interference with title parsing, we mask whatever is between double quotes
    if question_title := parse_question_title(mask_quoted_text(text)):
        return "Title", question_title
    if return_last_by_default:
        return "Last", "DEFAULT"


def parse_question_query(text: str) -> QuestionQuery:
    """Parse `QuestionSpecQuery` (specifying concrete question)
    or `QuestionFilterQuery` (specifying properties of questions
    we're looking for)
    """
    if spec_data := parse_question_spec_query(text):
        return spec_data
    return "Filter", parse_question_filter(text)


QuestionSpecQuery = Union[
    tuple[Literal["Last"], Literal["last", "it", "DEFAULT"]],
    tuple[Literal["GDocLinks"], list[str]],
    tuple[Literal["Title"], str],
]


QuestionQuery = Union[QuestionSpecQuery, QuestionFilterQuery]
