from enum import Enum
from servicemodules import discordConstants


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


openai_channel_ids: dict[Services, tuple[str, ...]] = {
    Services.DISCORD: (
        discordConstants.stampy_dev_priv_channel_id,
        discordConstants.aligned_intelligences_only_channel_id,
        discordConstants.ai_channel_id,
        discordConstants.not_ai_channel_id,
        discordConstants.events_channel_id,
        discordConstants.projects_channel_id,
        discordConstants.book_club_channel_id,
        discordConstants.dialogues_with_stampy_channel_id,
        discordConstants.meta_channel_id,
        discordConstants.general_channel_id,
        discordConstants.talk_to_stampy_channel_id,
    )
}


service_italics_marks = {
    Services.SLACK: "_",
    Services.FLASK: "",
}


default_italics_mark = "*"
