import os

subs_dir = "./database/subs"
youtube_api_service_name = "youtube"
youtube_api_version = "v3"
rob_id = "181142785259208704"
stampy_id = "736241264856662038"
plex_id = "756254556811165756"
god_id = "0"
rob_miles_youtube_channel_id = "UCLB7AzTwc6VFZrBsO2ucBMg"
stampy_youtube_channel_id = "UCFDiTXRowzFvh81VOsnf5wg"
youtube_testing_thread_url = "https://www.youtube.com/watch?v=vuYtSDMBLtQ&lc=Ugx2FUdOI6GuxSBkOQd4AaABAg"

bot_dev_channels = {"production": 808138366330994688, "development": 803448149946662923}

discord_token_env_variable = "DISCORD_TOKEN"
discord_guild_env_variable = "DISCORD_GUILD"
youtube_api_key_env_variable = "YOUTUBE_API_KEY"
database_path_env_variable = "DATABASE_PATH"
wiki_password_path_env_variable = "WIKI_BOT_PASSWORD"
environment_type_env_variable = "ENVIRONMENT_TYPE"

prod_local_path = "/home/rob/stampy.local"

admin_usernames = ["robertskmiles", "sudonym"]


discord_token = os.getenv(discord_token_env_variable)
discord_guild = os.getenv(discord_guild_env_variable)
youtube_api_key = os.getenv(youtube_api_key_env_variable)
database_path = os.getenv(database_path_env_variable)
wiki_password = os.getenv(wiki_password_path_env_variable)

#wiki_config = {"uri": "https://stampy.ai/w/api.php", "user": "Stampy@stampy", "password": wiki_password}

# TODO: remove hardcoded bot password -- Im aware it will be in the commit! I dont think its actually exploitable in any way
wiki_config = {"uri": "http://104.236.99.233/w/api.php", "user": "Stampy@Stampy", "password": "loaq8tcsb1tsi9vmldfedl19bi3g825k"}

ENVIRONMENT_TYPE = os.getenv(environment_type_env_variable)
acceptable_environment_types = ("production", "development")

required_environment_variables = [
    environment_type_env_variable,
    discord_token_env_variable,
    discord_guild_env_variable,
    database_path_env_variable,
    wiki_password_path_env_variable,
]
