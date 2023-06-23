from __future__ import annotations

from datetime import datetime, timedelta
from enum import Enum
from functools import cached_property
import os
from pprint import pformat
import random
import re
from string import punctuation
import sys
from threading import Event
from time import time
import traceback
from typing import (
    TYPE_CHECKING,
    Any,
    Callable,
    Literal,
    Optional,
    Union,
    cast,
)

import discord
from git.repo import Repo
import pandas as pd
import psutil
from structlog import get_logger

from config import (
    TEST_MESSAGE_PREFIX,
    TEST_RESPONSE_PREFIX,
    database_path,
    discord_guild,
    discord_token,
    bot_dev_roles,
    bot_dev_ids,
    bot_vip_ids,
    paid_service_for_all,
    paid_service_whitelist_role_ids,
    be_shy
)
from database.database import Database
from servicemodules.discordConstants import (
    wiki_feed_channel_id,
    stampy_error_log_channel_id,
)
from servicemodules.serviceConstants import Services
from utilities.discordutils import DiscordUser, user_has_role
from utilities.serviceutils import ServiceMessage, ServiceUser

if TYPE_CHECKING:
    from modules.module import Module


# Sadly some of us run windows...
if os.name != "nt":
    import pwd

log = get_logger()

discord_message_length_limit = 2000


class OrderType(Enum):
    TOP = 0
    RANDOM = 1
    LATEST = 2


class Utilities:
    __instance: Optional[Utilities] = None

    TOKEN = discord_token
    GUILD = discord_guild
    DB_PATH = database_path

    def __init__(self) -> None:
        if Utilities.__instance is not None:
            raise Exception(
                "This class is a singleton! Access it using `Utilities.get_instance()`"
            )

        Utilities.__instance = self

        self.class_name = self.__class__.__name__
        self.start_time = time()
        self.test_mode = False
        self.people = {"stampy"}

        self.db = Database(self.DB_PATH)
        log.info(self.class_name, status=f"Trying to open db - {self.DB_PATH}")
        intents = discord.Intents.default()
        intents.members = True
        intents.message_content = True
        self.client = discord.Client(intents=intents)
        self.discord_user: Optional[ServiceUser] = None
        self.stop: Optional[Event] = None

        self.last_question_asked_timestamp: datetime
        self.latest_question_posted = None

        # Last messages we got per channel, for annoyance prevention
        self.lastMessages: dict[str, str] = {}
        self.last_message_was_youtube_question: bool = False

        self.users: list[int] = []
        self.ids: list[int] = []
        self.index: dict[int, int] = {}

        # stamp counts
        self.scores: list[float] = []

        # modules stuff
        self.modules_dict: dict[str, Module] = {}
        self.service_modules_dict: dict[Services, Any] = {}
        self.unavailable_module_filenames: list[str] = []

        # testing
        self.message_prefix: str = ""

        # errors raised during initialization - to be raised on discord service start
        self.initialization_error_messages: list[str] = []

        self.exit_value: int = 0

    @staticmethod
    def get_instance() -> Utilities:
        if Utilities.__instance is None:
            return Utilities()
        return Utilities.__instance

    def stampy_is_author(self, message: ServiceMessage) -> bool:
        return self.is_stampy(message.author)

    def is_stampy(self, user: ServiceUser) -> bool:
        if (
            user.id == wiki_feed_channel_id
        ):  # consider wiki-feed ID as stampy to ignore -- is it better to set a wiki user?
            return True
        if self.discord_user:
            return user == self.discord_user
        if user.id == str(cast(discord.ClientUser, self.client.user).id):
            self.discord_user = user
            return True
        return False

    def is_stampy_mentioned(self, message: ServiceMessage) -> bool:
        for user in message.mentions:
            if self.is_stampy(user):
                return True
        return False

    def clear_votes(self) -> None:
        """Reset all the votes scores"""
        self.db.query("DELETE FROM uservotes")
        self.db.query(
            "INSERT INTO uservotes (`user`, `votedFor`, `votecount`) VALUES (?, ?, ?)",
            (0, 181142785259208704, 1),
        )
        self.db.commit()

    def update_ids_list(self) -> None:
        self.ids = sorted(list(self.users))
        self.index = {0: 0}
        for userid in self.ids:
            self.index[userid] = self.ids.index(userid)

    def index_dammit(self, user) -> Optional[int]:
        """Get an index into the scores array from whatever you get"""

        if user in self.index:
            # maybe we got given a valid ID?
            return self.index[user]
        elif str(user) in self.index:
            return self.index[str(user)]  # type:ignore

        # maybe we got given a User or Member object that has an ID?
        uid = getattr(user, "id", None)
        if uid is not None and not isinstance(uid, int):
            try:
                uid = int(uid)
            except (ValueError, TypeError):
                pass
            log.info(
                self.class_name,
                function_name="index_dammit",
                uuid=uid,
                index=self.index,
            )
        if uid:
            return self.index_dammit(uid)

        return None

    def get_user_score(self, user) -> float:
        """Get user's number of stamps"""
        index = self.index_dammit(user)
        if index:
            return self.scores[index]
        return 0.0

    def update_vote(self, user: int, voted_for: int, vote_quantity: int) -> None:
        query = (
            "INSERT OR REPLACE INTO uservotes VALUES (:user,:voted_for,IFNULL((SELECT votecount "
            "FROM uservotes WHERE user = :user AND votedFor = :voted_for),0)+:vote_quantity)"
        )
        args = {"user": user, "voted_for": voted_for, "vote_quantity": vote_quantity}
        self.db.query(query, args)
        self.db.commit()

    def get_votes_by_user(self, user_id: Union[str, int]) -> int:
        """Get number of votes given **by** that user"""
        query = "SELECT IFNULL(sum(votecount),0) FROM uservotes where user = ?"
        args = (user_id,)
        return self.db.query(query, args)[0][0]

    def get_votes_for_user(self, user_id: Union[str, int]) -> int:
        """Get number of votes given **for** that user"""
        query = "SELECT IFNULL(sum(votecount),0) FROM uservotes where votedFor = ?"
        args = (user_id,)
        return self.db.query(query, args)[0][0]

    def get_total_votes(self) -> int:
        """Get total number of votes"""
        query = "SELECT sum(votecount) from uservotes where user is not 0"
        return self.db.query(query)[0][0]

    def get_all_user_votes(self) -> list[tuple[int, int, int]]:
        """Get list of triples: `(<user-who-voted>, <user-who-was-voted-for>, <num-votes)`"""
        query = "SELECT user,votedFor,votecount from uservotes;"
        return self.db.query(query)

    def get_users(self) -> list[int]:
        """Get list of user IDs"""
        query = "SELECT user from (SELECT user FROM uservotes UNION SELECT votedFor as user FROM uservotes)"
        result = self.db.query(query)
        users = [item for sublist in result for item in sublist]
        return users

    def get_title(self, url: str) -> Optional[tuple[str, str]]:
        result = self.db.query(
            'select ShortTitle, FullTitle from video_titles where URL="?"', (url,)
        )
        if result:
            return result[0][0], result[0][1]
        return None

    def list_modules(self) -> str:
        message = f"I have {len(self.modules_dict)} modules. Here are their names:"
        for module_name in self.modules_dict.keys():
            message += "\n" + module_name
        return message

    def get_time_running(self) -> str:
        message = "I have been running for"
        seconds_running = timedelta(seconds=int(time() - self.start_time))
        time_running = datetime(1, 1, 1) + seconds_running
        if time_running.day - 1:
            message += " " + str(time_running.day) + " days,"
        if time_running.hour:
            message += " " + str(time_running.hour) + " hours,"
        message += " " + str(time_running.minute) + " minutes"
        message += " and " + str(time_running.second) + " seconds."
        return message

    def format_error_traceback_msg(self, e: Exception) -> str:
        parts = ["Traceback (most recent call last):\n"]
        parts.extend(traceback.format_stack(limit=25)[:-2])
        parts.extend(traceback.format_exception(*sys.exc_info())[1:])
        error_message = "".join(parts)
        return error_message

    async def log_exception(
        self, e: Exception, problem_source: Optional[str] = None
    ) -> None:
        error_message = self.format_error_traceback_msg(e)
        if problem_source:
            log.error(
                self.class_name,
                error=f"Caught Exception from {problem_source}: {e}\n\n{error_message}",
            )
        else:
            log.error(
                self.class_name, error=f"Caught Exception: {e}\n\n{error_message}"
            )
        await self.log_error(error_message)

    @cached_property
    def error_channel(self) -> discord.channel.TextChannel:
        return cast(
            discord.channel.TextChannel,
            self.client.get_channel(int(stampy_error_log_channel_id)),
        )

    async def log_error(self, error_message: str) -> None:
        for msg_chunk in Utilities.split_message_for_discord(
            error_message, max_length=discord_message_length_limit - 6
        ):
            if is_in_testing_mode():
                log.error(self.class_name, error_message=error_message)
            else:
                await self.error_channel.send(f"```{msg_chunk}```")

    @staticmethod
    def split_message_for_discord(
        msg: str, stop_char: str = "\n", max_length: int = discord_message_length_limit
    ) -> list[str]:
        """Splitting a message in chunks of maximum 2000,
        so that the end of each chunk is a newline if possible.
        We can do this greedily, and if a solution exists.
        """
        msg_len = len(msg)
        next_split_marker = 0
        last_split_index = 0
        output = []
        while last_split_index + max_length < msg_len:
            split_marker_try = msg.find(
                stop_char, next_split_marker + 1, last_split_index + max_length
            )
            if split_marker_try == -1:
                if (
                    next_split_marker == last_split_index
                ):  # there are no newlines in the next 2000 chars, just take all
                    next_split_marker = last_split_index + max_length

                output.append(msg[last_split_index:next_split_marker])
                last_split_index = next_split_marker
            else:
                next_split_marker = split_marker_try + 1
        output.append(msg[last_split_index:])
        return output

    def message_repeated(self, message: ServiceMessage, this_text: str) -> bool:
        """
        This function keeps a log of the last messages by channel and returns
        true if this text is identical to the last text. To use, find the block
        where a response is chosen and add a guard at the top

        ```
        # repetition guard
        if self.is_at_me(message) and Utilities.get_instance().messageRepeated(message, text):
            self.log.info(
                self.class_name, msg="We don't want to lock people in due to phrasing"
            )
            return Response()
        ```
        """
        chan = message.channel.id
        if not chan in self.lastMessages:
            self.lastMessages[chan] = this_text
            return False
        if self.lastMessages[chan] == this_text:
            return True
        self.lastMessages[chan] = this_text
        return False

    def parse_module_names(self, text: str) -> list[str]:
        module_name_candidates = re.findall(r"\w+", text.lower())
        return sorted(
            module_name
            for module_name in self.modules_dict
            if module_name.lower() in module_name_candidates
        )


def get_github_info() -> str:
    repo = Repo(".")
    master = repo.head.reference
    message = (
        f"\nThe latest commit was by {master.commit.author}."
        f"\nThe commit message was `{master.commit.message.strip()}`."
        f"\nThis commit was written on %(date)s"
        + master.commit.committed_datetime.strftime(
            "%A, %B %d, %Y at %I:%M:%S %p UTC%z"
        )
        + "."
    )
    return message


def get_git_branch_info() -> str:
    repo = Repo(".")
    branch = repo.active_branch
    name = repo.config_reader().get_value("user", "name")
    return f"from git branch `{branch}` by `{name}`"


def get_running_user_info() -> str:
    if not os.name == "nt":
        user_info = pwd.getpwuid(os.getuid())
        user_name = user_info.pw_gecos.split(",")[0]
        message = (
            f"The last user to start my server was {user_name}."
            f"\nThey used the {user_info.pw_shell} shell."
            f"\nMy Process ID is {os.getpid()} on this machine."
        )
        return message

    # This should be replaced with a better test down the line.
    shell = "Command Prompt (DOS)" if os.getenv("PROMPT") == "$P$G" else "PowerShell"
    user_name = os.getlogin()
    message = (
        f"The last user to start my server was {user_name}."
        f"\nThey used the {shell} shell."
        f"\nMy Process ID is {os.getpid()} on this machine."
    )
    return message


def get_memory_usage() -> str:
    process = psutil.Process(os.getpid())
    bytes_used = int(process.memory_info().rss) / 1000000
    return f"I'm using {bytes_used:,.2f} MegaBytes of memory."


def get_question_id(message: ServiceMessage) -> Union[int, Literal[""]]:
    text = message.clean_content
    first_number_found = re.search(r"\d+", text)
    if first_number_found:
        return int(first_number_found.group())
    return ""


def contains_prefix_with_number(text: str, prefix: str) -> bool:
    prefix = prefix.strip()  # remove white space for regex formatting
    return bool(re.search(rf"^{prefix}\s[0-9]+", text))


def is_test_response(text: str) -> bool:
    return contains_prefix_with_number(text, TEST_RESPONSE_PREFIX)


def is_test_question(text: str) -> bool:
    return contains_prefix_with_number(text, TEST_MESSAGE_PREFIX)


def is_test_message(text: str) -> bool:
    return is_test_response(text) or is_test_question(text)


def randbool(p: float) -> bool:
    return random.random() < p


def is_stampy_mentioned(message: ServiceMessage) -> bool:
    return Utilities.get_instance().is_stampy_mentioned(message)


def is_bot_dev(user: ServiceUser) -> bool:
    if user.id in bot_vip_ids:
        return True
    if user.id in bot_dev_ids:
        return True
    return any(user_has_role(user, r) for r in bot_dev_roles)


def stampy_is_author(message: ServiceMessage) -> bool:
    return Utilities.get_instance().stampy_is_author(message)


def get_guild_and_invite_role() -> tuple[discord.Guild, Optional[discord.Role]]:
    utils = Utilities.get_instance()
    guild = utils.client.guilds[0]
    invite_role = discord.utils.get(guild.roles, name="can-invite")
    return guild, invite_role


def get_user_handle(user: DiscordUser) -> str:
    return f"{user.name}#{user.discriminator}"


def is_from_reviewer(message: ServiceMessage) -> bool:
    """Is this message from @reviewer?"""
    return is_reviewer(message.author)


def is_reviewer(user: ServiceUser) -> bool:
    """Is this user `@reviewer`?"""
    return any(role.name == "reviewer" for role in user.roles)


def is_from_editor(message: ServiceMessage) -> bool:
    """Is this message from `@editor`?"""
    return is_editor(message.author)


def is_editor(user: ServiceUser) -> bool:
    """Is this user `@editor`?"""
    return any(role.name == "editor" for role in user.roles)


DiscordRole = Literal["reviewer", "editor", "bot dev"]


def has_permissions(
    user: ServiceUser,
    roles: tuple[DiscordRole, ...] = (
        "reviewer",
        "editor",
        "bot dev",
    ),
) -> bool:
    return any(role.name in roles for role in user.roles)


def is_in_testing_mode() -> bool:
    """Currently running in testing mode on GH?"""
    return "testing" in os.environ.values()


def fuzzy_contains(container: str, contained: str) -> bool:
    """Fuzzy-ish version of `contained in container`.
    Disregards spaces, and punctuation.
    """
    contained = remove_punct(contained.casefold().replace(" ", ""))
    container = remove_punct(container.casefold().replace(" ", ""))
    return contained in container


def pformat_to_codeblock(d: dict[str, Any]) -> str:
    """`pformat` a dictionary and embed it in a code block
    (for nice display in discord message)
    """
    return "```\n" + pformat(d, sort_dicts=False) + "\n```"


def remove_punct(s: str) -> str:
    """Remove punctuation from string"""
    for p in punctuation:
        s = s.replace(p, "")
    return s


def limit_text(
    text: str,
    limit: int,
    format_fail_message: Callable[[int], str] = (
        lambda x: f"Cut {x} characters from response\n"
    ),
) -> tuple[bool, str]:
    text_length = len(text)
    fail_length = text_length - limit

    if text_length >= limit:
        return True, format_fail_message(fail_length) + text[:limit]
    return False, text


def shuffle_df(df: pd.DataFrame) -> pd.DataFrame:
    inds = df.index.tolist()
    shuffled_inds = random.sample(inds, len(inds))
    return df.loc[shuffled_inds]


def mask_quoted_text(text: str) -> str:
    """Mask everything in text between paired double quotes with zero-width spaces"""
    quote_inds: list[tuple[int, int]] = []
    i = 0
    while text.count('"', i) > 1:
        start = text.find('"', i)
        end = text.find('"', start + 1)
        quote_inds.append((start, end + 1))
        i = end + 1
    for start, end in quote_inds:
        text = text[:start] + (end - start) * "\ufeff" + text[end:]
    return text


def can_use_paid_service(author: ServiceUser) -> bool:
    if paid_service_for_all:
        return True
    if author.id in bot_vip_ids or is_bot_dev(author):
        return True
    return any(user_has_role(author, x) for x in paid_service_whitelist_role_ids)

def is_shy() -> bool:
    return be_shy
