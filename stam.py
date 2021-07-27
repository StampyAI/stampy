import os
import sys
import inspect
import discord
import unicodedata
from utilities import Utilities, get_question_id
from modules.module import Response
from modules.reply import Reply
from modules.questions import QQManager
from modules.videosearch import VideoSearch
from modules.invitemanager import InviteManager
from modules.stampcollection import StampsModule
from modules.StampyControls import StampyControls
from modules.gpt3module import GPT3Module
from modules.Factoids import Factoids
from modules.wikiUpdate import WikiUpdate
from modules.testModule import TestModule
from datetime import datetime, timezone, timedelta
from config import (
    discord_token,
    database_path,
    prod_local_path,
    ENVIRONMENT_TYPE,
    bot_dev_channel_id,
    TEST_RESPONSE_PREFIX,
    TEST_QUESTION_PREFIX,
    test_response_message,
    maximum_recursion_depth,
    acceptable_environment_types,
)


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
    await utils.client.get_channel(bot_dev_channel_id).send("I just (re)started!")


@utils.client.event
async def on_message(message):
    # don't react to our own messages unless running test
    message_author_is_stampy = message.author == utils.client.user
    if utils.test_mode and message_author_is_stampy:
        print("test question")
    elif message_author_is_stampy:
        return

    # utils.modules_dict["StampsModule"].calculate_stamps()

    print("########################################################")
    print(datetime.now().isoformat(sep=" "))
    if hasattr(message.channel, "name"):
        print(f"Message: id={message.id} in '{message.channel.name}' (id={message.channel.id})")
    else:
        print(f"DM: id={message.id}")
    print(f"from {message.author.name}#{message.author.discriminator} (id={message.author.id})")
    if message.reference:
        print("In reply to:", message.reference)
    print(f"    {message.content}")
    print("#####################################")

    if hasattr(message.channel, "name") and message.channel.name == "general":
        print("the latest general discord channel message was not from stampy")
        utils.last_message_was_youtube_question = False

    responses = [Response()]
    for module in modules:
        print("# Asking module: %s" % str(module))
        response = module.process_message(message, utils.client)
        if response:
            response.module = module  # tag it with the module it came from, for future reference

            if response.callback:  # break ties between callbacks and text in favour of text
                response.confidence -= 0.001

            responses.append(response)

    print("#####################################")

    for i in range(maximum_recursion_depth):  # don't hang if infinite regress
        responses = sorted(responses, key=(lambda x: x.confidence), reverse=True)

        # print some debug
        print("Responses:")
        for response in responses:
            if response.callback:
                args_string = ", ".join([a.__repr__() for a in response.args])
                if response.kwargs:
                    args_string += ", " + ", ".join(
                        [f"{k}={v.__repr__()}" for k, v in response.kwargs.items()]
                    )
                print(
                    f"  {response.confidence}: {response.module}: `{response.callback.__name__}("
                    f"{args_string})`"
                )
            else:
                print(f'  {response.confidence}: {response.module}: "{response.text}"')
                if response.why:
                    print(f'       (because "{response.why}")')

        top_response = responses.pop(0)

        if top_response.callback:
            print("Top response is a callback. Calling it")
            if inspect.iscoroutinefunction(top_response.callback):
                new_response = await top_response.callback(*top_response.args, **top_response.kwargs)
            else:
                new_response = top_response.callback(*top_response.args, **top_response.kwargs)

            new_response.module = top_response.module
            responses.append(new_response)
        else:
            if top_response.text:
                if (
                    utils.test_mode
                    and (TEST_QUESTION_PREFIX not in top_response.text)
                    and utils.stampy_is_author(message)
                ):
                    if test_response_message == top_response.text:
                        return
                    top_response.text = (
                        TEST_RESPONSE_PREFIX + str(get_question_id(message)) + ": " + top_response.text
                    )
                print("Replying:", top_response.text)
                await message.channel.send(top_response.text)
            print("########################################################")
            sys.stdout.flush()
            return

    # if we ever get here, we've gone maximum_recursion_depth layers deep without the top response being text
    # so that's likely an infinite regress
    message.channel.send("[Stampy's ears start to smoke. There is a strong smell of recursion]")


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
    # add_question should maybe just take in the dict, but to make sure
    # nothing is broken extra fields have been added as optional params
    # This is just checking if there _are_ questions
    question_count = utils.get_question_count()
    if question_count:
        # ask a new question if it's been long enough since we last asked one
        question_ask_cooldown = timedelta(hours=12)

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
        "Factoids": Factoids(),
        "Sentience": sentience,
        "WikiUpdate": WikiUpdate(),
        "TestModule": TestModule(),
    }

    modules = utils.modules_dict.values()

    utils.client.run(discord_token)
