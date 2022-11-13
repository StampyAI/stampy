import discord
from git import Repo, cmd
from structlog import get_logger
from config import stampy_dev_priv_channel_id, discord_token

client = discord.Client()
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
    await client.get_channel(int(stampy_dev_priv_channel_id)).send(message)
    log.info("notify_discord_script", status="COMPLETE")
    exit()


client.run(discord_token)
