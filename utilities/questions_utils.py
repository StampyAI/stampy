import re
from typing import Optional

from api.coda import CodaAPI, QuestionStatus

coda_api = CodaAPI.get_instance()
status_shorthands = coda_api.get_status_shorthand_dict()
all_tags = coda_api.get_all_tags()

status_pat = "|".join(fr"\b{s}\b" for s in status_shorthands).replace(" ", r"\s")

def parse_status(
    text: str, *, require_status_prefix: bool = True
) -> Optional[QuestionStatus]:
    status_prefix = r"status\s*" if require_status_prefix else ""
    re_status = re.compile(fr"{status_prefix}({status_pat})", re.I | re.X,)
    if not (match := re_status.search(text)):
        return
    val = match.group(1)
    return status_shorthands[val.lower()]

def parse_gdoc_links(text: str) -> list[str]:
    """Extract GDoc links from message content.
    Returns `[]` if message doesn't contain any GDoc link.
    """
    return re.findall(r"https://docs\.google\.com/document/d/[\w_-]+", text)
