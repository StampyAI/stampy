from enum import Enum


class Services(Enum):
    DISCORD = "Discord"
    FLASK = "Flask"
    SLACK = "Slack"

    def __str__(self) -> str:
        return str(self._value_)

    def __eq__(self, other: object) -> bool:
        try:
            return str(self) == str(other)
        except Exception:
            return False

    def __hash__(self):
        return hash(str(self)) >> 22


service_italics_marks = {
    Services.SLACK: "_",
    Services.FLASK: "",
}


default_italics_mark = "*"


def italicise(text: str, message) -> str:
    if not text.strip():
        return text
    im = service_italics_marks.get(message.service, default_italics_mark)
    return f'{im}{text}{im}'
