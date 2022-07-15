import re
import discord
import numpy as np
from modules.module import Module, Response
from config import rob_id, god_id, stampy_id
from config import stamp_scores_csv_file_path


class StampsModule(Module):

    STAMPS_RESET_MESSAGE = "full stamp history reset complete"
    UNAUTHORIZED_MESSAGE = "You can't do that!"

    def __str__(self):
        return "Stamps Module"

    def __init__(self):
        Module.__init__(self)
        self.class_name = "StampsModule"
        self.red_stamp_value = 1
        self.gold_stamp_value = self.red_stamp_value * 5
        self.user_karma = 1.0
        self.total_votes = self.utils.get_total_votes()
        self.calculate_stamps()

    def reset_stamps(self):
        self.log.info(self.class_name, status="WIPING STAMP RECORDS")

        self.utils.clear_votes()
        self.utils.update_vote(god_id, str(rob_id))

    def update_vote(self, stamp_type, from_id, to_id, negative=False, recalculate=True):

        if to_id == stampy_id:
            # votes for stampy do nothing
            return

        if to_id == from_id:
            # votes for yourself do nothing
            return

        vote_strength = 0
        if stamp_type == "stamp":
            vote_strength = self.red_stamp_value
        elif stamp_type == "goldstamp":
            vote_strength = self.gold_stamp_value

        if negative:
            # if negative is True we are going to subtract the vote value
            vote_strength = -vote_strength

        self.total_votes += vote_strength
        self.utils.update_vote(from_id, to_id, vote_strength)
        self.utils.users = self.utils.get_users()
        self.utils.update_ids_list()
        if recalculate:
            self.calculate_stamps()

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
                score = (self.user_karma * votes_for_user) / total_votes_by_user
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
        self.log.info(self.class_name, msg=f"Logging scores to {stamp_scores_csv_file_path}")
        csv_lines = []
        for user_id in self.utils.get_users():
            score = self.get_user_stamps(user_id)
            user = self.utils.client.get_user(user_id)
            if user_id and user:  # don't bother for id 0 or if the user is None
                csv_lines.append(f"""{user_id},"{user.name}",{user.discriminator},{score}\n""")
        if not csv_lines:
            self.log.error(self.class_name, csv_error="No valid users to export to CSV?")
            return
        try:
            with open(stamp_scores_csv_file_path, "w") as csv_file:
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
            stamps = self.utils.scores[index] * self.total_votes
        else:
            stamps = 0.0
        return stamps

    def load_votes_from_csv(self, filename="stamps.csv"):

        with open(filename, "r") as stamps_file:
            stamps_file.readline()  # throw away the first line, it's headers
            for line in stamps_file:
                msg_id, react_type, from_id, to_id = line.strip().split(",")
                self.update_vote(react_type, from_id, to_id, False, False)

        self.calculate_stamps()

    async def load_votes_from_history(self):
        """Load up every time any stamp has been awarded by anyone in the whole history of the Discord
        This is omega slow, should basically only need to be called once"""
        guild = discord.utils.find(lambda g: g.name == self.utils.GUILD, self.utils.client.guilds)

        with open("stamps.csv", "w") as stamplog:
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
                        reactions = message.reactions
                        if reactions:
                            for reaction in reactions:
                                reaction_type = getattr(reaction.emoji, "name", "")
                                if reaction_type in ["stamp", "goldstamp"]:
                                    users = await reaction.users().flatten()
                                    for user in users:
                                        string = "%s,%s,%s,%s" % (
                                            message.id,
                                            reaction_type,
                                            user.id,
                                            message.author.id,
                                        )
                                        self.log.info(
                                            self.class_name,
                                            user_id=user.id,
                                            message_id=message.id,
                                            reaction_type=reaction_type,
                                            author_name=message.author.name,
                                            message_author_id=message.author.id,
                                        )
                                        stamplog.write(string + "\n")
                                        self.update_vote(
                                            reaction_type, user.id, message.author.id, False, False,
                                        )
                        if self.utils.stampy_is_author(message):
                            text = message.clean_content
                            if re.match(r"[0-9]+.+stamped.+", text):
                                users = re.findall(r"[0-9]+", text)
                                from_id = int(users[0])
                                to_id = int(users[1])
                                stamps_before_update = self.get_user_stamps(to_id)
                                emoji = "stamp"
                                negative = False
                                if re.match(r"[0-9]+.+unstamped.+", text):
                                    negative = True

                                self.update_vote(emoji, from_id, to_id, negative=negative)
                                self.log.info(
                                    self.class_name,
                                    reaction_message_author_id=to_id,
                                    stamps_before_update=stamps_before_update,
                                    stamps_after_update=self.get_user_stamps(to_id),
                                    negative_reaction=negative,
                                )

        self.calculate_stamps()

    async def process_reaction_event(self, reaction, user, event_type="REACTION_ADD"):
        emoji = getattr(reaction.emoji, "name", reaction.emoji)
        if emoji == "stamp":
            self.log.info(
                self.class_name,
                update="STAMP AWARDED",
                reaction_message_id=reaction.message.id,
                emoji=emoji,
                user_id=user.id,
                reaction_message_author_id=reaction.message.audthor.id,
                reaction_message_author_name=reaction.message.audthor.name,
            )

    async def process_raw_reaction_event(self, event):
        event_type = event.event_type
        guild = discord.utils.find(lambda g: g.name == self.utils.GUILD, self.utils.client.guilds)
        channel = discord.utils.find(lambda c: c.id == event.channel_id, guild.channels)

        if not channel:
            return
        message = await channel.fetch_message(event.message_id)
        emoji = getattr(event.emoji, "name", event.emoji)

        if message.author.id == 736241264856662038:
            # votes for stampy don't affect voting
            return
        if message.author.id == event.user_id:
            # votes for yourself don't affect voting
            # if event_type == 'REACTION_ADD' and emoji in ['stamp', 'goldstamp']:
            # 	await channel.send("<@" + str(event.user_id) + "> just awarded a stamp to themselves...")
            return

        if emoji in ["stamp", "goldstamp"]:

            ms_gid = event.message_id
            from_id = event.user_id
            to_id = message.author.id

            self.log.info(
                self.class_name,
                update="STAMP AWARDED",
                reaction_message_id=ms_gid,
                emoji=emoji,
                user_id=from_id,
                reaction_message_author_id=to_id,
                reaction_message_author_name=message.author.name,
            )

            # I believe this call was a duplicate and it should not be called twice
            # self.update_vote(emoji, from_id, to_id, False, False)

            stamps_before_update = self.get_user_stamps(to_id)
            self.update_vote(emoji, from_id, to_id, negative=(event_type == "REACTION_REMOVE"))
            self.log.info(
                self.class_name,
                reaction_message_author_id=to_id,
                stamps_before_update=stamps_before_update,
                stamps_after_update=self.get_user_stamps(to_id),
                negative_reaction=bool(event_type == "REACTION_REMOVE"),
            )

    def process_message(self, message):
        if self.is_at_me(message):
            text = self.is_at_me(message)

            if re.match(r"(how many stamps am i worth)\??", text.lower()):
                authors_stamps = self.get_user_stamps(message.author)
                return Response(
                    confidence=9,
                    text=f"You're worth {authors_stamps:.2f} stamps to me",
                    why=f"{message.author.name} asked how many stamps they're worth",
                )

            elif text == "reloadallstamps":
                if message.author.id == rob_id:
                    return Response(confidence=10, callback=self.reloadallstamps, args=[message])
                else:
                    return Response(confidence=10, text=self.UNAUTHORIZED_MESSAGE, args=[message])

        return Response()

    def process_message_from_stampy(self, message):
        text = message.clean_content
        if re.match(r"[0-9]+.+stamped.+", text):
            users = re.findall(r"[0-9]+", text)
            from_id = int(users[0])
            to_id = int(users[1])
            stamps_before_update = self.get_user_stamps(to_id)
            emoji = "stamp"
            negative = False
            if re.match(r"[0-9]+.+unstamped.+", text):
                negative = True

            self.update_vote(emoji, from_id, to_id, negative=negative)
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
            confidence=10, text=self.STAMPS_RESET_MESSAGE, why="robertskmiles reset the stamp history",
        )

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                question="how many stamps am I worth?",
                expected_regex=r"^You're worth ?[+-]?\d+(?:\.\d+)? stamps to me$",
            ),
            self.create_integration_test(
                question="reloadallstamps", expected_response=self.UNAUTHORIZED_MESSAGE
            ),
        ]
