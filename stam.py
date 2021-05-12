import os
import sys
import discord
import unicodedata
from dotenv import load_dotenv
from utilities import Utilities
from modules.reply import Reply
from modules.questions import QQManager
from modules.videosearch import VideoSearch
from modules.invitemanager import InviteManager
from modules.stampcollection import StampsModule
from modules.StampyControls import StampyControls
from modules.gpt3module import GPT3Module
from modules.wikiUpdate import WikiUpdate
from datetime import datetime, timezone, timedelta
from config import (
    discord_token,
    ENVIRONMENT_TYPE,
    acceptable_environment_types,
    bot_dev_channel_id,
    prod_local_path,
    database_path,
    rob_id,
    plex_id,
)

load_dotenv()

utils = Utilities.get_instance()

if not os.path.exists(database_path):
    raise Exception("Couldn't find the stampy database file at %s" % database_path)

if ENVIRONMENT_TYPE == "production":
    sys.path.insert(0, prod_local_path)
    import sentience
elif ENVIRONMENT_TYPE == "development":
    from modules.sentience import sentience
else:
    raise Exception(
        "Please set the ENVIRONMENT_TYPE environment variable to %s or %s" % acceptable_environment_types
    )


@utils.client.event
async def on_ready():
    print(f"{utils.client.user} has connected to Discord!")
    print("searching for a guild named '%s'" % utils.GUILD)
    print(utils.client.guilds)
    guild = discord.utils.get(utils.client.guilds, name=utils.GUILD)
    if guild is None:
        raise Exception("Guild Not Found : '%s'" % utils.GUILD)

    print("found a guild named '%s' with id '%s'" % (guild.name, guild.id))

    members = "\n - ".join([member.name for member in guild.members])
    print(f"Guild Members:\n - {members}")
    await utils.client.get_channel(bot_dev_channel_id[ENVIRONMENT_TYPE]).send("I just (re)started!")


@utils.client.event
async def on_message(message):
    # don't react to our own messages
    if message.author == utils.client.user:
        return

    utils.modules_dict["StampsModule"].calculate_stamps()

    print("########################################################")
    print(message)
    print(message.reference)
    print(message.author, message.content)

    if hasattr(message.channel, "name") and message.channel.name == "general":
        print("the latest general discord channel message was not from stampy")
        utils.last_message_was_youtube_question = False

    # What are the options for responding to this message?
    # Pre-populate with a dummy module, with 0 confidence about its proposed response of ""
    options = []
    for module in modules:
        print("Asking module: %s" % str(module))
        output = module.can_process_message(message, utils.client)
        print("output is", output)
        confidence, result = output
        if confidence > 0:
            options.append((module, confidence, result))

    # Go with whichever module was most confident in its response
    options = sorted(options, key=(lambda o: o[1]), reverse=True)
    print(options)
    for option in options:
        module, confidence, result = option

        if confidence > 0:
            # if the module had some confidence it could reply
            if not result:
                # but didn't reply in can_process_message()
                confidence, result = await module.process_message(message, utils.client)

        if confidence:
            if result:
                await message.channel.send(result)
            break

    print("########################################################")
    sys.stdout.flush()


@utils.client.event
async def on_socket_raw_receive(_):
    """
    This event fires whenever basically anything at all happens.
    Anyone joining, leaving, sending anything, even typing and not sending...
    So I'm going to use it as a kind of 'update' or 'tick' function,
    for things the bot needs to do regularly. Yes this is hacky.
    Rate limit these things, because this function might be firing a lot
    """

    # keep the log file fresh
    sys.stdout.flush()

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
                utils.add_youtube_question(comment)
    # add_question should maybe just take in the dict, but to make sure nothing is broken extra fields have been added as optional params
    # This is just checking if there _are_ questions
    question_count = utils.get_question_count()
    if question_count:
        # ask a new question if it's been long enough since we last asked one
        question_ask_cooldown = timedelta(hours=6)

        if (now - utils.last_question_asked_timestamp) > question_ask_cooldown:
            if not utils.last_message_was_youtube_question:
                # Don't ask anything if the last thing posted in the chat was stampy asking a question
                utils.last_question_asked_timestamp = now
                # this actually gets the question and sets it to asked, then sends the report
                report = utils.get_question(order_type="LATEST")
                guild = discord.utils.find(lambda g: g.name == utils.GUILD, utils.client.guilds)
                general = discord.utils.find(lambda c: c.name == "general", guild.channels)
                await general.send(report)
                utils.last_message_was_youtube_question = True
            else:
                # wait the full time again
                utils.last_question_asked_timestamp = now
                print("Not asking question: previous post in the channel was a question stampy asked.")
        else:
            remaining_cooldown = str(question_ask_cooldown - (now - utils.last_question_asked_timestamp))
            print("%s Questions in queue, waiting %s to post" % (question_count, remaining_cooldown))
            return


@utils.client.event
async def on_raw_reaction_add(payload):
    print("RAW REACTION ADD")
    if len(payload.emoji.name) == 1:
        # if this is an actual unicode emoji
        print(unicodedata.name(payload.emoji.name))
    else:
        print(payload.emoji.name.upper())
    print(payload)

    for module in modules:
        await module.process_raw_reaction_event(payload, utils.client)


@utils.client.event
async def on_raw_reaction_remove(payload):
    print("RAW REACTION REMOVE")
    print(payload)

    for module in modules:
        await module.process_raw_reaction_event(payload, utils.client)


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
        "StampyControls": StampyControls(),
        "StampsModule": StampsModule(),
        "QQManager": QQManager(),
        "VideoSearch": VideoSearch(),
        "Reply": Reply(),
        "InviteManager": InviteManager(),
        "GPT3Module": GPT3Module(),
        "Sentience": sentience,
        "WikiUpdate" : WikiUpdate(),
    }

    modules = utils.modules_dict.values()

    utils.client.run(discord_token)
