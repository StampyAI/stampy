"""
Manages user rankings through stamps
"""

from datetime import datetime, timedelta
import re
from typing import cast
import discord
import numpy as np
from structlog import get_logger

from api.coda import CodaAPI
from utilities import is_in_testing_mode, utilities, Utilities, is_bot_dev
from modules.module import Module, Response
from config import stamp_scores_csv_file_path, coda_api_token
from servicemodules.serviceConstants import Services
from servicemodules.discordConstants import stampy_id, bot_admin_role_id
from utilities.discordutils import DiscordMessage, DiscordUser

log = get_logger()
utils = Utilities.get_instance()

vote_strengths_per_emoji = {
    "aisafetyinfo": 1,
    "stampy": 1,
    "stampyog": 1,
    "stamp": 1,
    "goldstamp": 5,
}


class StampsModule(Module):
    STAMPS_RESET_MESSAGE = "full stamp history reset complete"
    UNAUTHORIZED_MESSAGE = "You can't do that!"
    last_total_stamp_update: datetime

    def __str__(self):
        return "StampsModule"

    def __init__(self):
        super().__init__()
        self.gamma = 0.99
        self.total_votes = self.utils.get_total_votes()
        self.calculate_stamps()
        if coda_api_token is None:
            self.coda_api = None
            self.log.warn(
                self.class_name,
                msg="CODA_API_TOKEN is not set. Coda not available. Module functionality will be restricted.",
            )
        else:
            self.coda_api = (
                CodaAPI.get_instance() if coda_api_token is not None else None
            )
        if is_in_testing_mode():
            return
        self.update_all_stamps_in_users_table()

    def reset_stamps(self):
        self.log.info(self.class_name, status="WIPING STAMP RECORDS")

        self.utils.clear_votes()
        self.update_utils()
        self.calculate_stamps()

    def update_vote(
        self,
        emoji: str,
        from_id: int,
        to_id: int,
        *,
        negative: bool = False,
        recalculate: bool = True,
    ):
        if (
            to_id == stampy_id  # votes for stampy do nothing
            or to_id == from_id  # votes for yourself do nothing
            or emoji not in vote_strengths_per_emoji
        ):  # votes with emojis other than stamps do nothing
            return

        vote_strength = vote_strengths_per_emoji[emoji]
        if negative:
            vote_strength *= -1

        self.total_votes += vote_strength
        self.utils.update_vote(from_id, to_id, vote_strength)
        self.update_utils()
        if recalculate:
            self.calculate_stamps()

    def update_all_stamps_in_users_table(self) -> None:
        if self.coda_api is None:
            return
        self.coda_api.reload_users_cache()
        users = self.utils.get_users()
        for user_id in users:
            stamp_count = self.get_user_stamps(user_id)
            user = self.utils.client.get_user(user_id)
            if user is not None:
                self.coda_api.update_user_stamps(cast(DiscordUser, user), stamp_count)
        self.last_total_stamp_update = datetime.now()

    def update_utils(self) -> None:
        self.utils.users = self.utils.get_users()
        self.utils.update_ids_list()

    def calculate_stamps(self):
        """Set up and solve the system of linear equations"""
        self.log.info(self.class_name, status="RECALCULATING STAMP SCORES")

        self.utils.users = self.utils.get_users()
        self.utils.update_ids_list()

        user_count = len(self.utils.users)

        users_matrix = np.zeros((user_count, user_count))

        votes = self.utils.get_all_user_votes()
        # self.log.debug(self.class_name, votes=votes)

        for from_id, to_id, votes_for_user in votes:
            from_id_index = self.utils.index[from_id]
            toi = self.utils.index[to_id]
            total_votes_by_user = self.utils.get_votes_by_user(from_id)
            if total_votes_by_user != 0:
                score = (self.gamma * votes_for_user) / total_votes_by_user
                users_matrix[toi, from_id_index] = score
        for i in range(1, user_count):
            users_matrix[i, i] = -1.0
        users_matrix[0, 0] = 1.0

        user_count_matrix = np.zeros(user_count)
        user_count_matrix[0] = 1.0  # God has 1 karma
        self.utils.scores = list(np.linalg.solve(users_matrix, user_count_matrix))

        self.export_scores_csv()
        # self.print_all_scores()

    # done
    def get_user_scores(self):
        message = "Here are the discord users and how many stamps they're worth:\n"
        self.utils.users = self.utils.get_users()
        for user_id in self.utils.users:
            name = self.utils.client.get_user(user_id)
            if not name:
                name = "<@" + str(user_id) + ">"
            stamps = self.get_user_stamps(user_id)
            message += str(name) + ": \t" + str(stamps) + "\n"
        return message

    def export_scores_csv(self):
        self.log.info(
            self.class_name, msg=f"Logging scores to {stamp_scores_csv_file_path}"
        )
        csv_lines = []
        for user_id in self.utils.get_users():
            score = self.get_user_stamps(user_id)
            user = self.utils.client.get_user(user_id)
            if user_id and user:  # don't bother for id 0 or if the user is None
                csv_lines.append(
                    f"""{user_id},"{user.name}",{user.discriminator},{score}\n"""
                )
        if not csv_lines:
            self.log.error(
                self.class_name, csv_error="No valid users to export to CSV?"
            )
            return
        try:
            with open(stamp_scores_csv_file_path, "w", encoding="utf-8") as csv_file:
                csv_file.write("".join(csv_lines))
        except Exception as e:
            self.log.error(self.class_name, error=e)

    def print_all_scores(self):
        total_stamps = 0
        self.utils.users = self.utils.get_users()
        for user_id in self.utils.users:
            name = self.utils.client.get_user(user_id)
            if not name:
                name = "<@" + str(user_id) + ">"
            stamps = self.get_user_stamps(user_id)
            total_stamps += stamps
            self.log.info(self.class_name, name=name, stamps=stamps)

        self.log.info(self.class_name, total_votes=self.total_votes)
        self.log.info(self.class_name, total_stamps=total_stamps)

    def get_user_stamps(self, user):
        index = self.utils.index_dammit(user)
        if index:
            return self.utils.scores[index] * self.total_votes
        return 0.0

    def load_votes_from_csv(self, filename: str = "stamps.csv"):
        with open(filename, "r", encoding="utf-8") as stamps_file:
            stamps_file.readline()  # throw away the first line, it's headers
            for line in stamps_file:
                msg_id, emoji, from_id, to_id = line.strip().split(",")
                self.update_vote(emoji, int(from_id), int(to_id), recalculate=False)

        self.calculate_stamps()

    async def load_votes_from_history(self) -> None:
        """Load up every time any stamp has been awarded by anyone in the whole history of the Discord
        This is omega slow, should basically only need to be called once"""
        guild = discord.utils.find(
            lambda g: g.name == self.utils.GUILD, self.utils.client.guilds
        )

        with open("stamps.csv", "w", encoding="utf-8") as stamplog:
            stamplog.write("msgid,type,from,to\n")

            for channel in guild.channels:
                self.log.info(
                    self.class_name,
                    operation="load_votes_from_history",
                    channel_name=channel.name,
                    channel_type=channel.type,
                    channel_type_type=type(channel.type),
                )
                if channel.type == discord.ChannelType.text:
                    async for message in channel.history(limit=None):
                        message = DiscordMessage(message)
                        reactions = message.reactions
                        if utilities.stampy_is_author(message):
                            text = message.clean_content
                            # If this is an old wiki feed stamp.
                            if re.match(r"[0-9]+.+stamped.+", text):
                                users = re.findall(r"[0-9]+", text)
                                from_id = int(users[0])
                                to_id = int(users[1])
                                stamps_before_update = self.get_user_stamps(to_id)
                                negative = bool(re.match(r"[0-9]+.+unstamped.+", text))
                                self.update_vote(
                                    "stamp", from_id, to_id, negative=negative
                                )
                                self.log.info(
                                    self.class_name,
                                    reaction_message_author_id=to_id,
                                    stamps_before_update=stamps_before_update,
                                    stamps_after_update=self.get_user_stamps(to_id),
                                    negative_reaction=negative,
                                )
                        elif reactions:
                            for reaction in reactions:
                                emoji = getattr(reaction.emoji, "name", "")
                                if emoji in vote_strengths_per_emoji:
                                    async for user in reaction.users():
                                        string = f"{message.id},{emoji},{user.id},{message.author.id}"
                                        self.log.info(
                                            self.class_name,
                                            user_id=user.id,
                                            message_id=message.id,
                                            reaction_type=emoji,
                                            author_name=message.author.display_name,
                                            message_author_id=message.author.id,
                                        )
                                        stamplog.write(string + "\n")
                                        self.update_vote(
                                            emoji,
                                            user.id,
                                            message.author.id,
                                            recalculate=False,
                                        )
        self.calculate_stamps()

    async def process_raw_reaction_event(self, event) -> None:
        event_type = event.event_type
        guild = discord.utils.find(
            lambda g: g.id == event.guild_id, self.utils.client.guilds
        )
        channel = discord.utils.find(lambda c: c.id == event.channel_id, guild.channels)

        if not channel:
            return
        message = DiscordMessage(await channel.fetch_message(event.message_id))
        emoji = getattr(event.emoji, "name", event.emoji)

        author_id_int = int(message.author.id)
        if utilities.stampy_is_author(message):
            # votes for stampy don't affect voting
            return
        if author_id_int == event.user_id:
            # votes for yourself don't affect voting
            # if event_type == 'REACTION_ADD' and emoji in ['stamp', 'goldstamp']:
            # 	await channel.send("<@" + str(event.user_id) + "> just awarded a stamp to themselves...")
            return

        if emoji in vote_strengths_per_emoji:
            msg_id = event.message_id
            from_id = event.user_id
            to_id = author_id_int

            self.log.info(
                self.class_name,
                update="STAMP AWARDED",
                reaction_message_id=msg_id,
                emoji=emoji,
                user_id=from_id,
                reaction_message_author_id=to_id,
                reaction_message_author_name=message.author.display_name,
            )

            stamps_before_update = self.get_user_stamps(to_id)
            self.update_vote(
                cast(str, emoji),
                from_id,
                to_id,
                negative=(event_type == "REACTION_REMOVE"),
            )
            stamps_after_update = self.get_user_stamps(to_id)
            if self.last_total_stamp_update < datetime.now() - timedelta(hours=23):
                self.update_all_stamps_in_users_table()
            else:
                if self.coda_api is None:
                    self.log.warn(
                        self.class_name,
                        "Coda API not available (CODA_API_TOKEN is not set). Couldn't update vote counts in coda",
                    )
                self.coda_api.update_user_stamps(
                    cast(DiscordUser, message.author), stamps_after_update
                )
            self.log.info(
                self.class_name,
                reaction_message_author_id=to_id,
                stamps_before_update=stamps_before_update,
                stamps_after_update=stamps_after_update,
                negative_reaction=bool(event_type == "REACTION_REMOVE"),
            )

    def process_message(self, message):
        if text := self.is_at_me(message):
            if re.match(r"(how many stamps am i worth)\??", text.lower()):
                authors_stamps = self.get_user_stamps(message.author)
                return Response(
                    confidence=9,
                    text=f"You're worth {authors_stamps:.2f} stamps to me",
                    why=f"{message.author.display_name} asked how many stamps they're worth",
                )

            elif text == "reloadallstamps":
                if message.service == Services.DISCORD:
                    if is_bot_dev(message.author):
                        return Response(
                            confidence=10, callback=self.reloadallstamps, args=[message]
                        )
                else:
                    return Response(
                        confidence=10, text=self.UNAUTHORIZED_MESSAGE, args=[message]
                    )

        return Response()

    def process_message_from_stampy(self, message):
        text = message.clean_content
        if re.match(r"[0-9]+.+stamped.+", text):
            users = re.findall(r"[0-9]+", text)
            from_id = int(users[0])
            to_id = int(users[1])
            stamps_before_update = self.get_user_stamps(to_id)
            negative = bool(re.match(r"[0-9]+.+unstamped.+", text))

            self.update_vote("stamp", from_id, to_id, negative=negative)
            self.log.info(
                self.class_name,
                reaction_message_author_id=to_id,
                stamps_before_update=stamps_before_update,
                stamps_after_update=self.get_user_stamps(to_id),
                negative_reaction=negative,
            )

    async def reloadallstamps(self, message):
        self.log.info(self.class_name, ALERT="FULL STAMP HISTORY RESET BAYBEEEEEE")
        await message.channel.send("Doing full stamp history reset, could take a while")
        self.reset_stamps()
        await self.load_votes_from_history()
        return Response(
            confidence=10,
            text=self.STAMPS_RESET_MESSAGE,
            why="robertskmiles reset the stamp history",
        )

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                test_message="how many stamps am I worth?",
                expected_regex=r"^You're worth ?[+-]?\d+(?:\.\d+)? stamps to me$",
            ),
            self.create_integration_test(
                test_message="reloadallstamps",
                expected_response=self.UNAUTHORIZED_MESSAGE,
            ),
        ]
