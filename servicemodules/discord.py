import asyncio
from datetime import datetime, timezone
import inspect
import sys
from textwrap import wrap
import threading
from typing import Iterable, Generator, Union, cast
import unicodedata

import discord
from structlog import get_logger

from api.youtube import YoutubeAPI
import config
from config import (
    discord_token,
    TEST_RESPONSE_PREFIX,
    maximum_recursion_depth,
    youtube_api_key,
    bot_private_channel_id,
    channel_whitelist,
)
from modules.module import Response
from servicemodules import discordConstants
from utilities import (
    Utilities,
    get_question_id,
    is_test_response,
    is_test_message,
    is_test_question,
    get_git_branch_info,
    limit_text,
)
from utilities.discordutils import DiscordMessage
from utilities.serviceutils import ServiceChannel

log = get_logger()

if youtube_api_key:
    youtube_api = YoutubeAPI.get_instance()
else:
    youtube_api = None

# An appropriate max for how much text we should be able to give to Discord.
# Discord messages can be 2000 max, so 20000 allows for 10 max length messages
discordLimit = 20000


# TODO: store long responses temporarily for viewing outside of discord
def limit_text_and_notify(response: Response, why_traceback: list[str]) -> str:
    if isinstance(response.text, str):
        wastrimmed = False
        wastrimmed, text_to_return = limit_text(response.text, discordLimit)
        if wastrimmed:
            why_traceback.append(f"I had to trim the output from {response.module}")
        return text_to_return
    return ""


class DiscordHandler:
    def __init__(self):
        self.class_name = "DiscordHandler"
        self.utils = Utilities.get_instance()
        self.service_utils = self.utils
        self.modules = self.utils.modules_dict.values()
        self.messages: dict[str, dict[str, Union[str, list[str]]]] = {}
        """
        All Discord Functions need to be under another function in order to
        use self.
        """

        @self.utils.client.event
        async def on_ready() -> None:
            log.info(
                self.class_name,
                status=f"{self.utils.client.user} has connected to Discord!",
                searching_for_guild=self.utils.GUILD,
                guilds=self.utils.client.guilds,
            )
            guild = discord.utils.get(self.utils.client.guilds, name=self.utils.GUILD)
            if guild is None:
                raise Exception(f"Guild Not Found : '{self.utils.GUILD}'")

            log.info(
                self.class_name,
                msg="found a guild named '%s' with id '%s'" % (guild.name, guild.id),
            )

            self.test_channel_constants()

            members = "\n - " + "\n - ".join([member.name for member in guild.members])
            log.info(self.class_name, guild_members=members)
            if bot_private_channel_id is not None:
                await cast(
                    ServiceChannel,
                    self.utils.client.get_channel(int(bot_private_channel_id)),
                ).send(f"I just (re)started {get_git_branch_info()}!")
            for error_msg in self.utils.initialization_error_messages:
                await self.utils.log_error(error_msg)

        @self.utils.client.event
        async def on_message(
            message: Union[discord.message.Message, DiscordMessage]
        ) -> None:
            if not isinstance(message, DiscordMessage):
                message = DiscordMessage(message)

            # don't react to our own messages unless running test
            message_author_is_stampy = self.utils.stampy_is_author(message)
            if is_test_message(message.clean_content) and self.utils.test_mode:
                log.info(
                    self.class_name,
                    type="TEST MESSAGE",
                    message_content=message.clean_content,
                )
            elif message_author_is_stampy:
                for module in self.modules:
                    module.process_message_from_stampy(message)
                return

            message_is_dm = True
            message_reference = None
            if hasattr(message.channel, "name"):
                message_is_dm = False
            if message.reference:
                message_reference = message.reference
            log.info(
                self.class_name,
                message_id=message.id,
                message_channel_name=message.channel.name,
                message_author_name=message.author.display_name,
                message_author_discriminator=message.author.discriminator,
                message_author_id=message.author.id,
                message_channel_id=message.channel.id,
                message_is_dm=message_is_dm,
                message_reference=message_reference,
                message_content=message.content,
            )

            if (
                hasattr(message.channel, "id")
                and str(message.channel.id)
                == discordConstants.automatic_question_channel_id
            ):
                log.info(
                    self.class_name,
                    msg="the latest general discord channel message was not from stampy",
                )
                self.utils.last_message_was_youtube_question = False

            #log.info("Checking whitelist...") # DEBUG
            if not message.is_dm and (isinstance(channel_whitelist, frozenset)
                    and hasattr(message.channel, "id")
                    and str(message.channel.id) not in channel_whitelist):
                #log.info("message channel {} not in whitelist".format(message.channel.id)) # debug
                return None
            #log.info("message channel {} was found in whitelist".format(message.channel.id)) # DEBUG

            responses = [Response()]
            why_traceback: list[str] = []
            for module in self.modules:
                log.info(self.class_name, msg=f"# Asking module: {module}")
                try:
                    response = module.process_message(message)
                except Exception as e:
                    why_traceback.append(
                        f"There was a(n) {e} asking the {module} module!"
                    )
                    await self.utils.log_exception(
                        e, problem_source=f"{self.class_name} {module}"
                    )
                if response:
                    response.module = module  # tag it with the module it came from, for future reference

                    if (
                        response.callback
                    ):  # break ties between callbacks and text in favour of text
                        response.confidence -= 0.001

                    responses.append(response)

                    response.text = limit_text_and_notify(response, why_traceback)

                    why_traceback.append(
                        f"I asked the {module} module, and it responded with: {response}"
                    )

            for i in range(maximum_recursion_depth):  # don't hang if infinite regress
                responses = sorted(
                    responses, key=(lambda x: x.confidence), reverse=True
                )
                for response in responses:
                    args_string = ""

                    if response.callback:
                        args_string = ", ".join([a.__repr__() for a in response.args])
                        if response.kwargs:
                            args_string += ", " + ", ".join(
                                [
                                    f"{k}={v.__repr__()}"
                                    for k, v in response.kwargs.items()
                                ]
                            )
                    log.info(
                        self.class_name,
                        response_module=str(response.module),
                        response_confidence=response.confidence,
                        response_is_callback=bool(response.callback),
                        response_callback=(
                            response.callback.__name__ if response.callback else None
                        ),
                        response_args=args_string,
                        response_text=(
                            response.text
                            if not isinstance(response.text, Generator)
                            else "[Generator]"
                        ),
                        response_reasons=response.why,
                    )

                top_response = responses.pop(0)
                why_traceback.append(f"The top response was {top_response}")
                try:
                    if top_response.callback:
                        log.info(
                            self.class_name,
                            msg="Top response is a callback. Calling it",
                        )
                        why_traceback.append(
                            "That response was a callback, so I called it."
                        )

                        # Callbacks can take a while to run, so we tell discord to say "Stampy is typing..."
                        # Note that sometimes a callback will run but not send a message, in which case he'll seem to be typing but not say anything. I think this will be rare though.
                        async with message.channel._channel.typing():
                            if inspect.iscoroutinefunction(top_response.callback):
                                new_response = await top_response.callback(
                                    *top_response.args, **top_response.kwargs
                                )
                            else:
                                new_response = top_response.callback(
                                    *top_response.args, **top_response.kwargs
                                )

                        new_response.module = top_response.module
                        new_response.text = limit_text_and_notify(
                            new_response, why_traceback
                        )
                        responses.append(new_response)
                        why_traceback.append(
                            f"The callback responded with: {new_response}"
                        )
                    else:
                        if top_response:
                            if self.utils.test_mode:
                                if is_test_response(message.clean_content):
                                    return  # must return after process message is called so that response can be evaluated
                                if is_test_question(message.clean_content):
                                    top_response.text = (
                                        TEST_RESPONSE_PREFIX
                                        + str(get_question_id(message))
                                        + ": "
                                        + (
                                            top_response.text
                                            if not isinstance(
                                                top_response.text, Generator
                                            )
                                            else "".join(list(top_response.text))
                                        )
                                    )
                            log.info(self.class_name, top_response=top_response.text)
                            sent: list[discord.message.Message] = []
                            # TODO: check to see if module is allowed to embed via a config?
                            if top_response.embed:
                                sent.append(
                                    await message.channel.send(
                                        top_response.text, embed=top_response.embed
                                    )
                                )
                            elif isinstance(top_response.text, str):
                                # Discord allows max 2000 characters
                                chunks = wrap(
                                    top_response.text,
                                    width=2000,
                                    replace_whitespace=False,
                                    drop_whitespace=False,
                                )
                                for chunk in chunks:
                                    sent.append(await message.channel.send(chunk))
                            elif isinstance(top_response.text, Iterable):
                                for chunk in top_response.text:
                                    sent.append(await message.channel.send(chunk))
                            why_traceback.append("Responded with that response!")
                            for m in sent:
                                self.messages[str(m.id)] = {
                                    "why": top_response.why,
                                    "traceback": why_traceback,
                                }
                        sys.stdout.flush()
                        return
                except Exception as e:
                    why_traceback.append(
                        f"There was a(n) {e} trying to send or callback the top response!"
                    )
                    log.error(self.class_name, error=f"Caught error {e}!")
                    await self.utils.log_exception(e)

            # if we ever get here, we've gone maximum_recursion_depth layers deep without the top response being text
            # so that's likely an infinite regress
            sent = await message.channel.send(
                "[Stampy's ears start to smoke. There is a strong smell of recursion]"
            )
            self.messages[str(sent)] = {
                "why": "I detected recursion and killed the response process!",
                "traceback": why_traceback,
            }
            why_traceback.append("Detected recursion and killed the response process!")
            log.critical(self.class_name, error="Hit our recursion limit!")

        @self.utils.client.event
        async def on_socket_raw_receive(_) -> None:
            """
            This event fires whenever basically anything at all happens.
            Anyone joining, leaving, sending anything, even typing and not sending...
            So I'm going to use it as a kind of 'update' or 'tick' function,
            for things the bot needs to do regularly. Yes this is hacky.
            Rate limit these things, because this function might be firing a lot
            """
            # die if needed
            if self.utils.stop.is_set():
                exit()

            # keep the log file fresh
            sys.stdout.flush()

            # give all the modules a chance to do things
            for module in self.modules:
                await module.tick()

            # never fire more than once a second
            if self.utils.rate_limit("on_socket_raw_receive", seconds=1):
                return

            # this is needed for later checks, which should all be replaced with rate_limit calls (TODO)
            now = datetime.now(timezone.utc)

            if youtube_api:
                # check for new youtube comments
                new_comments = youtube_api.check_for_new_youtube_comments()
                if new_comments:
                    for comment in new_comments:
                        if "?" in comment["text"]:
                            youtube_api.add_youtube_question(comment)

        @self.utils.client.event
        async def on_raw_reaction_add(
            payload: discord.raw_models.RawReactionActionEvent,
        ) -> None:
            log.info(self.class_name, msg="RAW REACTION ADD")
            if len(payload.emoji.name) == 1:
                # if this is an actual unicode emoji
                log.info(self.class_name, emoji=unicodedata.name(payload.emoji.name))
            else:
                log.info(self.class_name, emoji=payload.emoji.name.upper())
            log.info(self.class_name, payload=payload)

            for module in self.modules:
                try:
                    await module.process_raw_reaction_event(payload)
                except Exception as e:
                    await self.utils.log_exception(e)

        @self.utils.client.event
        async def on_raw_reaction_remove(
            payload: discord.raw_models.RawReactionActionEvent,
        ) -> None:
            log.info(self.class_name, msg="RAW REACTION REMOVE")
            log.info(self.class_name, payload=payload)

            for module in self.modules:
                await module.process_raw_reaction_event(payload)

    def start(self, event: threading.Event) -> threading.Thread:
        try:
            # This line is deprecated in 3.10, but doesn't work otherwise.
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        loop.create_task(self.utils.client.start(discord_token))
        t = threading.Thread(target=loop.run_forever)
        t.name = "Discord Thread"
        t.start()
        return t

    def test_channel_constants(self) -> None:
        for name in dir(config):
            if name.endswith("channel_id"):
                channel_id = getattr(config, name)
                self.test_channel_id(name, channel_id)
            elif name.endswith("channel_ids"):
                channel_ids = getattr(config, name)
                if not isinstance(channel_ids, Iterable):
                    log.warning(
                        self.class_name,
                        msg="Purported channel_ids is not Iterable",
                        name=name,
                        value=channel_ids,
                        type=type(channel_ids),
                    )
                else:
                    for channel_id in channel_ids:
                        self.test_channel_id(name, channel_id)

    def test_channel_id(self, name: str, channel_id: str) -> None:
        if not isinstance(channel_id, str):
            log.warning(
                self.class_name,
                msg="Purported channel_id is not string",
                channel_name=name,
                channel_id_value=channel_id,
                type=type(channel_id),
            )
        elif not channel_id.isnumeric():
            log.warning(
                self.class_name,
                msg="Purported channel_id is not a numeric string",
                channel_name=name,
                channel_id_value=channel_id,
            )
        elif self.utils.client.get_channel(int(channel_id)) is None:
            log.warning(
                self.class_name,
                msg="Could not find a channel with id",
                channel_name=name,
                channel_id_value=channel_id,
            )
