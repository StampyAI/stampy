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
