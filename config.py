from api.utilities.gooseutils import GooseAIEngines
import dotenv
import os

dotenv.load_dotenv()
NOT_PROVIDED = '__NOT_PROVIDED__'


def getenv(env_var, default=NOT_PROVIDED):
    """
    Get an environment variable with a default,
    raise an exception if the environment variable isn't set and no default is provided
    """
    value = os.getenv(env_var, default)
    if value == NOT_PROVIDED:
        raise Exception(f"Environment Variable '{env_var}' not set and no default provided")
    return value


maximum_recursion_depth = 30
subs_dir = "./database/subs"
youtube_api_service_name = "youtube"
youtube_api_version = "v3"
god_id = "0"
youtube_testing_thread_url = "https://www.youtube.com/watch?v=vuYtSDMBLtQ&lc=Ugx2FUdOI6GuxSBkOQd4AaABAg"

# Multiply this by the total number of votes made, to get the number of stamps needed to post a reply comment
comment_posting_threshold_factor = 0.15

discord_token_env_variable = "DISCORD_TOKEN"
discord_guild_env_variable = "DISCORD_GUILD"
youtube_api_key_env_variable = "YOUTUBE_API_KEY"
database_path_env_variable = "DATABASE_PATH"
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

stamp_scores_csv_file_path = {
    "production": "/var/www/html/stamps-export.csv",
    "development": "stamps-export.csv",
}[ENVIRONMENT_TYPE]


discord_token = getenv("DISCORD_TOKEN")
discord_guild = getenv("DISCORD_GUILD")
youtube_api_key = getenv("YOUTUBE_API_KEY")
database_path = getenv("DATABASE_PATH")
openai_api_key = getenv("OPENAI_API_KEY", default=None)
goose_api_key = getenv("GOOSE_API_KEY", default=None)
wolfram_token = getenv("WOLFRAM_TOKEN", default=None)
# These defaults are just to not break production until slack is set up.
slack_app_token = getenv("SLACK_APP_TOKEN", default=None)
slack_bot_token = getenv("SLACK_BOT_TOKEN", default=None)


goose_engine_fallback_order = [  # What engine to use in order of preference in case one goes down.
    GooseAIEngines.GPT_20B,
    GooseAIEngines.GPT_6B,
    GooseAIEngines.GPT_2_7B,
    GooseAIEngines.GPT_1_3B,
    GooseAIEngines.GPT_125M,
    GooseAIEngines.FAIRSEQ_13B,
    GooseAIEngines.FAIRSEQ_6_7B,
    GooseAIEngines.FAIRSEQ_2_7B,
    GooseAIEngines.FAIRSEQ_1_3B,
    GooseAIEngines.FAIRSEQ_125M,
]
