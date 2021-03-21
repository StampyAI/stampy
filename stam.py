import discord
import unicodedata
from modules.reply import Reply
from modules.module import Module
from utilities import client, utils
from modules.questions import QQManager
from modules.videosearch import VideoSearch
from modules.invitemanager import InviteManager
from modules.stampcollection import StampsModule
from datetime import datetime, timezone, timedelta
from config import discord_token, rob_id, ENVIRONMENT_TYPE, acceptable_environment_types, bot_dev_channels

if ENVIRONMENT_TYPE == "production":
    raise Exception("This line must be changed before deploying to prod")
elif ENVIRONMENT_TYPE == "development":
    from modules.sentience import sentience
else:
    raise Exception(
        "Please set the ENVIRONMENT_TYPE environment variable to %s or %s" % acceptable_environment_types
    )


@client.event
async def on_ready():
    print(f"{client.user} has connected to Discord!")
    print("searching for a guild named '%s'" % utils.GUILD)
    print(client.guilds)
    guild = discord.utils.get(client.guilds, name=utils.GUILD)
    if guild is None:
        raise Exception("Guild Not Found : '%s'" % utils.GUILD)

    print("found a guild named '%s' with id '%s'" % (guild.name, guild.id))

    members = "\n - ".join([member.name for member in guild.members])
    print(f"Guild Members:\n - {members}")
    await client.get_channel(bot_dev_channels[ENVIRONMENT_TYPE]).send("I'm back!")


@client.event
async def on_message(message):
    # don't react to our own messages
    if message.author == client.user:
        return

    print("########################################################")
    print(message)
    print(message.reference)
    print(message.author, message.content)

    if hasattr(message.channel, "name") and message.channel.name == "general":
        print("Last message was no longer us")
        utils.last_message_was_youtube_question = False

    if message.content == "bot test":
        response = "I'm alive!"
        await message.channel.send(response)
    elif message.content.lower() == "Klaatu barada nikto".lower():
        await message.channel.send("I must go now, my planet needs me")
        exit()
    if message.content == "reply test":
        if message.reference:
            reference = await message.channel.fetch_message(message.reference.message_id)
            reference_text = reference.content
            reply_url = reference_text.split("\n")[-1].strip()

            response = 'This is a reply to message %s:\n"%s"' % (
                message.reference.message_id,
                reference_text,
            )
            response += 'which should be taken as an answer to the question at: "%s"' % reply_url
        else:
            response = "This is not a reply"
        await message.channel.send(response)
    if message.content == "resetinviteroles" and message.author.id == int(rob_id):
        print("[resetting can-invite roles]")
        await message.channel.send("[resetting can-invite roles, please wait]")
        guild = discord.utils.find(lambda g: g.name == utils.GUILD, client.guilds)
        print(utils.GUILD, guild)
        role = discord.utils.get(guild.roles, name="can-invite")
        print("there are", len(guild.members), "members")
        reset_users_count = 0
        for member in guild.members:
            if utils.get_user_stamps(member) > 0:
                print(member.name, "can invite")
                await member.add_roles(role)
                reset_users_count += 1
            else:
                print(member.name, "has 0 stamps, can't invite")
        await message.channel.send("[Invite Roles Reset for %s users]" % reset_users_count)
        return

    # What are the options for responding to this message?
    # Pre-populate with a dummy module, with 0 confidence about its proposed response of ""
    options = [(Module(), 0, "")]

    for module in modules:
        print("Asking module: %s" % str(module))
        output = module.can_process_message(message, client)
        print("output is", output)
        confidence, result = output
        if confidence > 0:
            options.append((module, confidence, result))

    # Go with whichever module was most confident in its response
    options = sorted(options, key=(lambda o: o[1]), reverse=True)
    print(options)
    module, confidence, result = options[0]

    if confidence > 0:
        # if the module had some confidence it could reply
        if not result:
            # but didn't reply in can_process_message()
            confidence, result = await module.processMessage(message, client)

    if result:
        await message.channel.send(result)

    print("########################################################")


@client.event
async def on_socket_raw_receive(_):
    """This event fires whenever basically anything at all happens.
    Anyone joining, leaving, sending anything, even typing and not sending...
    So I'm going to use it as a kind of 'update' or 'tick' function,
    for things the bot needs to do regularly. Yes this is hacky.
    Rate limit these things, because this function might be firing a lot"""

    # never fire more than once a second
    tick_cooldown = timedelta(seconds=1)
    now = datetime.now(timezone.utc)

    if (now - utils.last_timestamp) > tick_cooldown:
        print("|", end="")
        utils.last_timestamp = now
    else:
        print(".", end="")
        return

    # check for new youtube comments
    new_comments = utils.check_for_new_youtube_comments()
    if new_comments:
        for comment in new_comments:
            if "?" in comment["text"]:
                utils.add_question(comment)
    qq = utils.get_next_question("rowid")
    if qq:
        # ask a new question if it's been long enough since we last asked one
        question_ask_cooldown = timedelta(hours=6)

        if (now - utils.last_question_asked_timestamp) > question_ask_cooldown:
            if not utils.last_message_was_youtube_question:
                # Don't ask anything if the last thing posted in the chat was stampy asking a question
                utils.last_question_asked_timestamp = now
                report = utils.get_latest_question()
                guild = discord.utils.find(lambda g: g.name == utils.GUILD, client.guilds)
                general = discord.utils.find(lambda c: c.name == "general", guild.channels)
                await general.send(report)
                utils.last_message_was_youtube_question = True
            else:
                # wait the full time again
                utils.last_question_asked_timestamp = now
                print("Not asking question: previous post in the channel was a question stampy asked.")
        else:
            remaining_cooldown = str(question_ask_cooldown - (now - utils.last_question_asked_timestamp))
            print("%s Questions in queue, waiting %s to post" % (len(qq), remaining_cooldown))
            return


@client.event
async def on_raw_reaction_add(payload):
    print("RAW REACTION ADD")
    if len(payload.emoji.name) == 1:
        # if this is an actual unicode emoji
        print(unicodedata.name(payload.emoji.name))
    else:
        print(payload.emoji.name.upper())
    print(payload)

    for module in modules:
        await module.process_raw_reaction_event(payload, client)


@client.event
async def on_raw_reaction_remove(payload):
    print("RAW REACTION REMOVE")
    print(payload)

    for module in modules:
        await module.process_raw_reaction_event(payload, client)


if __name__ == "__main__":
    # when was the most recent comment we saw posted?
    utils.latest_comment_timestamp = datetime.now(timezone.utc)

    # when did we last hit the API to check for comments?
    utils.last_check_timestamp = datetime.now(timezone.utc)

    # how many seconds should we wait before we can hit YT API again
    # this the start value. It doubles every time we don't find anything new
    utils.youtube_cooldown = timedelta(seconds=60)

    # timestamp of when we last ran the tick function
    utils.last_timestamp = datetime.now(timezone.utc)

    # timestamp of last time we asked a youtube question
    utils.last_question_asked_timestamp = datetime.now(timezone.utc)

    # Was the last message posted in #general by anyone, us asking a question from YouTube?
    # We start off not knowing, but it's better to assume yes than no
    utils.last_message_was_youtube_question = True

    utils.modules_dict = {
        "StampsModule": StampsModule(),
        "QQManager": QQManager(),
        "VideoSearch": VideoSearch(),
        "Reply": Reply(),
        "InviteManager": InviteManager(),
        "Sentience": sentience,
    }

    modules = utils.modules_dict.values()

    client.run(discord_token)
