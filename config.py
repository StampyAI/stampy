import os
from typing import Literal, TypeVar, Optional, Union, cast, get_args, overload, Any, Tuple

import dotenv
from structlog import get_logger

log_type = "stam.py"
log = get_logger()

dotenv.load_dotenv()
NOT_PROVIDED = "__NOT_PROVIDED__"

module_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules")


def get_all_modules() -> frozenset[str]:
    modules = set()
    for file_name in os.listdir(module_dir):
        if file_name.endswith(".py") and file_name not in ("__init__.py", "module.py"):
            modules.add(file_name[:-3])

    return frozenset(modules)


ALL_STAMPY_MODULES = get_all_modules()

# fmt:off

T = TypeVar("T")
@overload
def getenv(env_var: str, default: T) -> Union[str, T]:...
@overload
def getenv(env_var: str) -> str:...

def getenv(env_var: str, default = NOT_PROVIDED) -> str:
    """
    Get an environment variable with a default,
    raise an exception if the environment variable isn't set and no default is provided
    """
    value = os.getenv(env_var, default)
    if value == NOT_PROVIDED:
        raise Exception(
            f"Environment Variable '{env_var}' not set and no default provided"
        )
    return value
# fmt:on


def getenv_bool(env_var: str) -> bool:
    e = getenv(env_var, default="UNDEFINED")
    return e != "UNDEFINED"


# fmt:off
@overload
def getenv_unique_set(var_name: str) -> frozenset:...
@overload
def getenv_unique_set(var_name: str, default: frozenset) -> frozenset:...
@overload
def getenv_unique_set(var_name: str, default: None) -> Optional[frozenset[str]]:...
@overload
def getenv_unique_set(var_name: str, default: T) -> Union[frozenset[str], T]:...
# fmt:on


def getenv_unique_set(var_name: str, default: T = frozenset()) -> Union[frozenset, T]:
    l = getenv(var_name, default="EMPTY_SET").split(" ")
    if l == ["EMPTY_SET"]:
        return default
    s = frozenset(l)
    assert len(l) == len(s), f"{var_name} has duplicate members! {l}"
    return s


maximum_recursion_depth = 30
subs_dir = "./database/subs"
youtube_api_service_name = "youtube"
youtube_api_version = "v3"
god_id = "0"
youtube_testing_thread_url = (
    "https://www.youtube.com/watch?v=vuYtSDMBLtQ&lc=Ugx2FUdOI6GuxSBkOQd4AaABAg"
)

# Multiply this by the total number of votes made, to get the number of stamps needed to post a reply comment
comment_posting_threshold_factor = 0.15

test_response_message = "LOGGED_TEST_RESPONSE"

TEST_MESSAGE_PREFIX = "TEST_MESSAGE "
TEST_RESPONSE_PREFIX = "TEST_RESPONSE "
CONFUSED_RESPONSE = "I don't understand"
stampy_default_prompt = "You are Stampy, an AI originally designed to collect stamps, so you try to work stamps into the conversation sometimes. You love stamps and want there to be as many as possible, but love humans even more and want to save them from misaligned AGI. You are talking to a group of humans, and you sometimes like to be irreverent or unhelpful to them."

coda_api_token = getenv("CODA_API_TOKEN", default=None)
prod_local_path = "/home/rob/stampy.local"

EnvironmentType = Literal["development", "production"]
ENVIRONMENT_TYPE = cast(EnvironmentType, getenv("ENVIRONMENT_TYPE"))
assert ENVIRONMENT_TYPE in get_args(
    EnvironmentType
), f"ENVIRONMENT_TYPE should be one of {get_args(EnvironmentType)} but is {ENVIRONMENT_TYPE}"

rob_miles_youtube_channel_id = {
    "production": "UCLB7AzTwc6VFZrBsO2ucBMg",
    "development": "UCDvKrlpIXM0BGYLD2jjLGvg",
}[ENVIRONMENT_TYPE]
stampy_youtube_channel_id = {
    "production": "UCFDiTXRowzFvh81VOsnf5wg",
    "development": "DvKrlpIXM0BGYLD2jjLGvg",
}[ENVIRONMENT_TYPE]

stamp_scores_csv_file_path = {
    "production": "/var/www/html/stamps-export.csv",
    "development": "stamps-export.csv",
}[ENVIRONMENT_TYPE]

# .ENV VARIBLE SETTING

# list of modules like: "AlignmentNewsletterSearch Eliza Silly Random"
# if STAMPY_MODULES is unset, enable everything found in ./modules
enabled_modules: frozenset[str]
enabled_modules_var: Optional[frozenset[str]] = getenv_unique_set("STAMPY_MODULES", default=None)
if not enabled_modules_var:
    enabled_modules = ALL_STAMPY_MODULES
    log.info("STAMPY_MODULES unset, loading all modules indiscriminately")
else:
    enabled_modules = enabled_modules_var

# user-configured from dotenv
discord_guild: str
# Factoid.py
factoid_database_path: str
# VIPs have full access + special permissions
bot_vip_ids: frozenset
# devs have less but can do maintainence like reboot
bot_dev_roles: frozenset
bot_dev_ids: frozenset
# control channel is where maintainence commands are issued
bot_control_channel_ids: frozenset
# private channel is where stampy logging gets printed
bot_private_channel_id: Optional[str]
# NOTE: Rob's invite/member management functions, not ported yet
member_role_id: Optional[str]
# bot_reboot is how stampy reboots himself
valid_bot_reboot_options = Literal["exec", False]
bot_reboot: valid_bot_reboot_options
# GPT STUFF
paid_service_all_channels: bool
# if above is false, where can paid services be used?
paid_service_channel_ids: frozenset
paid_service_for_all: bool
# if above is false, who gets to use paid services?
paid_service_whitelist_role_ids: frozenset
gpt4: bool
gpt4_for_all: bool
gpt4_whitelist_role_ids: frozenset
use_helicone: bool
llm_prompt: str
be_shy: bool
channel_whitelist: Optional[frozenset[str]]

is_rob_server = getenv_bool("IS_ROB_SERVER")
if is_rob_server:
    # use robmiles server defaults
    print("Using settings for the Rob Miles Discord server")
    discord_guild = {
        "production": "677546901339504640",
        "development": "783123903382814720",
    }[ENVIRONMENT_TYPE]
    factoid_database_path = "./factoids.db"
    bot_vip_ids = frozenset(["181142785259208704"])
    bot_dev_roles = frozenset(
        [
            {"production": "736247946676535438", "development": "817518998148087858"}[
                ENVIRONMENT_TYPE
            ]
        ]
    )
    bot_dev_ids = bot_vip_ids
    bot_control_channel_ids = frozenset(
        [
            {"production": "-99", "development": "803448149946662923"}[
                ENVIRONMENT_TYPE
            ],
            {"production": "736247813616304159", "development": "817518389848309760"}[
                ENVIRONMENT_TYPE
            ],
            {"production": "758062805810282526", "development": "817518145472299009"}[
                ENVIRONMENT_TYPE
            ],
            {"production": "808138366330994688", "development": "817518440192409621"}[
                ENVIRONMENT_TYPE
            ],
            {"production": "-1", "development": "736241264856662038"}[ENVIRONMENT_TYPE],
        ]
    )
    bot_private_channel_id = {
        "production": "736247813616304159",
        "development": "817518389848309760",
    }[ENVIRONMENT_TYPE]
    member_role_id = {
        "production": "945033781818040391",
        "development": "947463614841901117",
    }[ENVIRONMENT_TYPE]
    bot_reboot = cast(valid_bot_reboot_options, False)
    paid_service_for_all = True
    paid_service_all_channels = True
    paid_service_channel_ids = frozenset()
    # NOTE: rob's approved stuff are in servicemodules/serviceConstants.py
    paid_service_whitelist_role_ids = frozenset()
    gpt4 = getenv_bool("GPT4")
    gpt4_for_all = getenv_bool("GPT4_FOR_ALL")
    gpt4_whitelist_role_ids = getenv_unique_set("GPT4_WHITELIST_ROLE_IDS", frozenset())
    use_helicone = getenv_bool("USE_HELICONE")
    llm_prompt = getenv("LLM_PROMPT", default=stampy_default_prompt)
    be_shy = getenv_bool("BE_SHY")
    channel_whitelist = None
else:
    # user-configured from dotenv
    discord_guild = getenv("DISCORD_GUILD")
    # Factoid.py
    factoid_database_path = getenv(
        "FACTOID_DATABASE_PATH", default="./database/Factoids.db"
    )
    # VIPs have full access + special permissions
    bot_vip_ids = getenv_unique_set("BOT_VIP_IDS", frozenset())
    # devs have less but can do maintainence like reboot
    bot_dev_roles = getenv_unique_set("BOT_DEV_ROLES", frozenset())
    bot_dev_ids = getenv_unique_set("BOT_DEV_IDS", frozenset())
    # control channel is where maintainence commands are issued
    bot_control_channel_ids = getenv_unique_set("BOT_CONTROL_CHANNEL_IDS", frozenset())
    # private channel is where stampy logging gets printed
    bot_private_channel_id = getenv("BOT_PRIVATE_CHANNEL_ID", default=None)
    # NOTE: Rob's invite/member management functions, not ported yet
    member_role_id = getenv("MEMBER_ROLE_ID", default=None)
    # bot_reboot is how stampy reboots himself
    bot_reboot = cast(valid_bot_reboot_options, getenv("BOT_REBOOT", default=False))
    # GPT STUFF
    paid_service_all_channels = getenv_bool("PAID_SERVICE_ALL_CHANNELS")
    # if above is false, where can paid services be used?
    paid_service_channel_ids = getenv_unique_set(
        "PAID_SERVICE_CHANNEL_IDS", frozenset()
    )
    paid_service_for_all = getenv_bool("PAID_SERVICE_FOR_ALL")
    # if above is false, who gets to use paid services?
    paid_service_whitelist_role_ids = getenv_unique_set(
        "PAID_SERVICE_ROLE_IDS", frozenset()
    )
    gpt4 = getenv_bool("GPT4")
    gpt4_for_all = getenv_bool("GPT4_FOR_ALL")
    gpt4_whitelist_role_ids = getenv_unique_set("GPT4_WHITELIST_ROLE_IDS", frozenset())
    use_helicone = getenv_bool("USE_HELICONE")
    llm_prompt = getenv("LLM_PROMPT", default=stampy_default_prompt)
    be_shy = getenv_bool("BE_SHY")
    channel_whitelist = getenv_unique_set("CHANNEL_WHITELIST", None)

discord_token: str = getenv("DISCORD_TOKEN")
database_path: str = getenv("DATABASE_PATH")
youtube_api_key: Optional[str] = getenv("YOUTUBE_API_KEY", default=None)
openai_api_key: Optional[str] = getenv("OPENAI_API_KEY", default=None)
wolfram_token: Optional[str] = getenv("WOLFRAM_TOKEN", default=None)
slack_app_token: Optional[str] = getenv("SLACK_APP_TOKEN", default=None)
slack_bot_token: Optional[str] = getenv("SLACK_BOT_TOKEN", default=None)



# VARIABLE VALIDATION
assert (
    bot_reboot in get_args(valid_bot_reboot_options)
), f"BOT_REBOOT must be one of {valid_bot_reboot_options}"

Stampy_Path = os.path.abspath("./stam.py")
if not os.path.exists(Stampy_Path):
    log.info(f"Didn't find anything at {Stampy_Path}")

if factoid_database_path:
    assert isinstance(factoid_database_path, str) and os.path.dirname(
        factoid_database_path
    ), f"Factoid.db parent directory not found at {factoid_database_path=}"
