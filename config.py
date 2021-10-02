import os
import dotenv

dotenv.load_dotenv()


def getenv(env_var, default=None):
    """
    Get an environment variable with a default,
    raise an exception if the environment variable isn't set and no default is provided
    """
    value = os.getenv(env_var, default)
    if value is None:
        raise Exception(f"Environment Variable '{env_var}' not set and no default provided")
    return value


maximum_recursion_depth = 30
subs_dir = "./database/subs"
youtube_api_service_name = "youtube"
youtube_api_version = "v3"
rob_id = 181142785259208704
stampy_id = "736241264856662038"
plex_id = "756254556811165756"
god_id = "0"
youtube_testing_thread_url = "https://www.youtube.com/watch?v=vuYtSDMBLtQ&lc=Ugx2FUdOI6GuxSBkOQd4AaABAg"

# Multiply this by the total number of votes made, to get the number of stamps needed to post a reply comment
comment_posting_threshold_factor = 0.15

discord_token_env_variable = "DISCORD_TOKEN"
discord_guild_env_variable = "DISCORD_GUILD"
youtube_api_key_env_variable = "YOUTUBE_API_KEY"
database_path_env_variable = "DATABASE_PATH"
wiki_password_path_env_variable = "WIKI_BOT_PASSWORD"
environment_type_env_variable = "ENVIRONMENT_TYPE"
openai_env_variable = "OPENAI_API_KEY"
test_response_message = "LOGGED_TEST_RESPONSE"

TEST_QUESTION_PREFIX = "TEST_QUESTION "
TEST_RESPONSE_PREFIX = "TEST_RESPONSE "
CONFUSED_RESPONSE = "I don't understand"

prod_local_path = "/home/rob/stampy.local"

ENVIRONMENT_TYPE = getenv("ENVIRONMENT_TYPE")
acceptable_environment_types = ("production", "development")
assert (
    ENVIRONMENT_TYPE in acceptable_environment_types
), f"ENVIRONMENT_TYPE {ENVIRONMENT_TYPE} is not in {acceptable_environment_types}"

rob_miles_youtube_channel_id = {
    "production": "UCLB7AzTwc6VFZrBsO2ucBMg",
    "development": "UCDvKrlpIXM0BGYLD2jjLGvg",
}[ENVIRONMENT_TYPE]
stampy_youtube_channel_id = {
    "production": "UCFDiTXRowzFvh81VOsnf5wg",
    "development": "DvKrlpIXM0BGYLD2jjLGvg",
}[ENVIRONMENT_TYPE]

bot_dev_channel_id = {"production": 808138366330994688, "development": 803448149946662923}[ENVIRONMENT_TYPE]


discord_token = getenv("DISCORD_TOKEN")
discord_guild = getenv("DISCORD_GUILD")
youtube_api_key = getenv("YOUTUBE_API_KEY")
database_path = getenv("DATABASE_PATH")
wiki_password = getenv("WIKI_BOT_PASSWORD")
openai_api_key = getenv("OPENAI_API_KEY", default="null")
wolfram_token = getenv("WOLFRAM_TOKEN", default="null")

wiki_config = {"uri": "https://stampy.ai/w/api.php", "user": "Stampy@stampy", "password": wiki_password}


stampy_control_channel_names = [
    "test",
    "bot-dev-priv",
    "bot-dev",
    "talk-to-stampy",
    "robertskmiles",
]
