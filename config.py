import os

subs_dir = "./database/subs"
youtube_api_service_name = "youtube"
youtube_api_version = "v3"
rob_miles_youtube_channel_id = "UCLB7AzTwc6VFZrBsO2ucBMg"

discord_token_env_variable = "DISCORD_TOKEN"
discord_guild_env_variable = "DISCORD_GUILD"
youtube_api_key_env_variable = "YOUTUBE_API_KEY"
database_path_env_variable = "DATABASE_PATH"

discord_token = os.getenv(discord_token_env_variable)
discord_guild = os.getenv(discord_guild_env_variable)
youtube_api_key = os.getenv(youtube_api_key_env_variable)
database_path = os.getenv(database_path_env_variable)

required_environment_variables = [
    discord_token_env_variable,
    discord_guild_env_variable,
    youtube_api_key_env_variable,
    database_path_env_variable,
]
