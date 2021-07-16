import re
import discord
import numpy as np
from config import admin_usernames
from modules.module import Module, Response
from config import rob_id, god_id, stampy_id


class StampsModule(Module):
    def __str__(self):
        return "Stamps Module"

    def __init__(self):
        Module.__init__(self)
        self.red_stamp_value = 1
        self.gold_stamp_value = self.red_stamp_value * 5
        self.user_karma = 1.0
        self.total_votes = self.utils.get_total_votes()
        self.calculate_stamps()

    def reset_stamps(self):
        print("WIPING STAMP RECORDS")

        self.utils.clear_votes()
        self.utils.update_vote(god_id, rob_id)

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
        print("RECALCULATING STAMP SCORES")

        self.utils.users = self.utils.get_users()
        self.utils.update_ids_list()

        user_count = len(self.utils.users)

        users_matrix = np.zeros((user_count, user_count))

        votes = self.utils.get_all_user_votes()
        print(votes)

        for from_id, to_id, votes_for_user in votes:
            from_id_index = self.utils.index[from_id]
            toi = self.utils.index[to_id]
            total_votes_by_user = self.utils.get_votes_by_user(from_id)
            print(from_id_index, toi, votes_for_user, total_votes_by_user)
            if total_votes_by_user != 0:
                score = (self.user_karma * votes_for_user) / total_votes_by_user
                users_matrix[toi, from_id_index] = score
        for i in range(1, user_count):
            users_matrix[i, i] = -1.0
        users_matrix[0, 0] = 1.0

        user_count_matrix = np.zeros(user_count)
        user_count_matrix[0] = 1.0  # God has 1 karma

        self.utils.scores = list(np.linalg.solve(users_matrix, user_count_matrix))

        self.print_all_scores()

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

    def print_all_scores(self):
        total_stamps = 0
        self.utils.users = self.utils.get_users()
        for user_id in self.utils.users:
            name = self.utils.client.get_user(user_id)
            if not name:
                name = "<@" + str(user_id) + ">"
            stamps = self.get_user_stamps(user_id)
            total_stamps += stamps
            print(name, "\t", stamps)

        print("Total votes:", self.total_votes)
        print("Total Stamps:", total_stamps)

    def get_user_stamps(self, user):
        index = self.utils.index_dammit(user)
        print("get_user_stamps for %s, index=%s" % (user, index))
        if index:
            stamps = self.utils.scores[index] * self.total_votes
            print(stamps, self.utils.scores[index], self.total_votes)
        else:
            stamps = 0.0
        return stamps

    def load_votes_from_csv(self, filename="stamps.csv"):

        with open(filename, "r") as stamps_file:
            stamps_file.readline()  # throw away the first line, it's headers
            for line in stamps_file:
                msg_id, react_type, from_id, to_id = line.strip().split(",")
                print(msg_id, react_type, from_id, to_id)
                self.update_vote(react_type, from_id, to_id, False, False)

        self.calculate_stamps()

    async def load_votes_from_history(self):
        """Load up every time any stamp has been awarded by anyone in the whole history of the Discord
        This is omega slow, should basically only need to be called once"""
        guild = discord.utils.find(lambda g: g.name == self.utils.GUILD, self.utils.client.guilds)

        with open("stamps.csv", "w") as stamplog:
            stamplog.write("msgid,type,from,to\n")

            for channel in guild.channels:
                print(
                    "#### Considering",
                    channel.type,
                    type(channel.type),
                    channel.name,
                    "####",
                )
                if channel.type == discord.ChannelType.text:
                    print("#### Logging", channel.name, "####")
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
                                        print(string)
                                        stamplog.write(string + "\n")
                                        self.update_vote(
                                            reaction_type,
                                            user.id,
                                            message.author.id,
                                            False,
                                            False,
                                        )
        self.calculate_stamps()

    async def process_reaction_event(self, reaction, user, event_type="REACTION_ADD", client=None):
        # guild = discord.utils.find(lambda g: g.name == guildname, client.guilds)
        emoji = getattr(reaction.emoji, "name", reaction.emoji)
        if emoji == "stamp":
            print("### STAMP AWARDED ###")
            print("%s,%s,%s,%s" % (reaction.message.id, emoji, user.id, reaction.message.audthor.id))

    async def process_raw_reaction_event(self, event, client=None):
        event_type = event.event_type
        guild = discord.utils.find(lambda g: g.name == self.utils.GUILD, client.guilds)
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

            print("%s,%s,%s,%s" % (ms_gid, emoji, from_id, to_id))

            print("### STAMP AWARDED ###")
            print("Score before stamp:", self.get_user_stamps(to_id))
            self.update_vote(emoji, from_id, to_id, negative=(event_type == "REACTION_REMOVE"))
            # self.save_votesdict_to_json()
            print("Score after stamp:", self.get_user_stamps(to_id))

    def process_message(self, message, client=None):
        if self.is_at_me(message):
            text = self.is_at_me(message)

            if re.match(r"(how many stamps am i worth)\??", text.lower()):
                authors_stamps = self.get_user_stamps(message.author)
                return Response(
                    confidence=9,
                    text="You're worth %.2f stamps to me" % authors_stamps,
                    why="%s asked how many stamps they're worth" % message.author.name,
                )

            elif text == "reloadallstamps" and message.author.id == 181142785259208704:
                return Response(confidence=10, callback=self.reloadallstamps, args=[message])

        return Response()

    @staticmethod
    def user_is_admin(username):
        return username in admin_usernames

    async def reloadallstamps(self, message):
        print("FULL STAMP HISTORY RESET BAYBEEEEEE")
        await message.channel.send("Doing full stamp history reset, could take a while")
        self.reset_stamps()
        await self.load_votes_from_history()
        return Response(
            confidence=10,
            text="full stamp history reset complete",
            why="robertskmiles reset the stamp history",
        )
