from config import bot_private_channel_id
from config import discord_token
from git import cmd, Repo
from structlog import get_logger
import discord

intents = discord.Intents.default()
client = discord.Client(intents=intents)
log = get_logger()
offline_message = (
    "I'm going offline for maintenance. %s is updating me.\n"
    + "This is their latest commit message that I've received: \n'%s'\n"
    + "This message was committed at %s\nI'll be back!"
)
git_directory = "."


@client.event
async def on_ready():
    log.info("notify_discord_script", msg="Logged in as", user_name=client.user.name, user_id=client.user.id)
    cmd.Git(git_directory).pull()
    repo = Repo(git_directory)
    master = repo.head.reference
    actor = master.commit.author
    git_message = master.commit.message.strip()
    date = master.commit.committed_datetime.strftime("%A, %B %d, %Y at %I:%M:%S %p UTC%z")
    message = offline_message % (actor, git_message, date)
    log.info("notify_discord_script", msg=message)
    if bot_private_channel_id:
        await client.get_channel(int(bot_private_channel_id)).send(message)
    log.info("notify_discord_script", status="COMPLETE")
    await client.close()


client.run(discord_token)
