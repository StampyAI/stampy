import re
import discord
import numpy as np
from modules.module import Module
from config import rob_id, god_id, stampy_id


class StampsModule(Module):
    def __str__(self):
        return "Stamps Module"

    def __init__(self):
        Module.__init__(self)
        self.gold_multiplier = 5  # gold stamp is worth how many red stamps?
        self.gamma = (
            1.0  # what proportion of the karma you get is passed on by your votes?
        )
        self.total_votes = self.utils.get_total_votes()
        self.calculate_stamps()

    def reset_stamps(self):
        print("WIPING STAMP RECORDS")

        self.utils.clear_votes()
        self.utils.add_vote(god_id, rob_id)

    def add_vote(self, stamp_type, from_id, to_id, negative=False, recalculate=True):

        if to_id == stampy_id:  # votes for stampy do nothing
            return

        if to_id == from_id:  # votes for yourself do nothing
            return

        vote_strength = 0
        if stamp_type == "stamp":
            vote_strength = 1
        elif stamp_type == "goldstamp":
            vote_strength = self.gold_multiplier

        if negative:  # are we actually undoing a vote?
            vote_strength = -vote_strength

        self.total_votes += vote_strength

        if stamp_type == "stamp":
            vote_strength = 1
        elif stamp_type == "goldstamp":
            vote_strength = self.gold_multiplier

        # isn't it a bit confusing that we use addVote to remove a vote?
        if negative:  # are we actually undoing a vote?
            vote_strength = -vote_strength

        self.utils.add_vote(from_id, to_id, vote_strength)
        self.utils.users = self.utils.get_users()
        self.utils.update_ids_list()
        if recalculate:
            self.calculate_stamps()

        return

    # done?
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
                score = (self.gamma * votes_for_user) / total_votes_by_user
                users_matrix[toi, from_id_index] = score
        for i in range(1, user_count):
            users_matrix[i, i] = -1.0
        users_matrix[0, 0] = 1.0

        user_count_matrix = np.zeros(user_count)
        user_count_matrix[0] = 1.0  # God has 1 karma

        self.utils.scores = list(np.linalg.solve(users_matrix, user_count_matrix))

        self.print_all_scores()

    # done
    def print_all_scores(self):
        total_stamps = 0
        self.utils.users = self.utils.get_users()
        for user in self.utils.users:
            uid = user
            name = self.utils.client.get_user(uid)
            if not name:
                name = "<@" + str(uid) + ">"
            stamps = self.get_user_stamps(uid)
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
                self.add_vote(react_type, from_id, to_id, False, False)

        self.calculate_stamps()

    async def load_votes_from_history(self):
        """Load up every time any stamp has been awarded by anyone in the whole history of the Discord
        This is omega slow, should basically only need to be called once"""
        guild = discord.utils.find(
            lambda g: g.name == self.utils.GUILD, self.utils.client.guilds
        )

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
                        # print("###########")
                        # print(message.content[:20])
                        reactions = message.reactions
                        if reactions:
                            # print(reactions)
                            for reaction in reactions:
                                reacttype = getattr(reaction.emoji, "name", "")
                                if reacttype in ["stamp", "goldstamp"]:
                                    # print("STAMP")
                                    users = await reaction.users().flatten()
                                    for user in users:
                                        string = "%s,%s,%s,%s" % (
                                            message.id,
                                            reacttype,
                                            user.id,
                                            message.author.id,
                                        )
                                        print(string)
                                        stamplog.write(string + "\n")
                                        self.add_vote(
                                            reacttype,
                                            user.id,
                                            message.author.id,
                                            False,
                                            False,
                                        )
                                        # print("From", user.id, user)

        # self.save_votesdict_to_json()
        self.calculate_stamps()

    async def process_reaction_event(
        self, reaction, user, event_type="REACTION_ADD", client=None
    ):
        # guild = discord.utils.find(lambda g: g.name == guildname, client.guilds)
        emoji = getattr(reaction.emoji, "name", reaction.emoji)
        if emoji == "stamp":
            print("### STAMP AWARDED ###")
            print(
                "%s,%s,%s,%s"
                % (reaction.message.id, emoji, user.id, reaction.message.audthor.id)
            )

    async def process_raw_reaction_event(self, event, client=None):
        event_type = event.event_type
        guild = discord.utils.find(lambda g: g.name == self.utils.GUILD, client.guilds)
        channel = discord.utils.find(lambda c: c.id == event.channel_id, guild.channels)

        if not channel:
            return
        message = await channel.fetch_message(event.message_id)
        emoji = getattr(event.emoji, "name", event.emoji)

        if (
            message.author.id == 736241264856662038
        ):  # votes for stampy don't affect voting
            return
        if message.author.id == event.user_id:  # votes for yourself don't affect voting
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
            self.add_vote(
                emoji, from_id, to_id, negative=(event_type == "REACTION_REMOVE")
            )
            # self.save_votesdict_to_json()
            print("Score after stamp:", self.get_user_stamps(to_id))

    def can_process_message(self, message, client=None):
        if self.is_at_me(message):
            text = self.is_at_me(message)

            if re.match(r"(how many stamps am i worth)\??", text.lower()):
                return (
                    9,
                    "You're worth %.2f stamps to me"
                    % self.get_user_stamps(message.author),
                )

            elif text == "reloadallstamps" and message.author.name == "robertskmiles":
                return 10, ""

        return 0, ""

    async def process_message(self, message, client=None):
        text = self.is_at_me(message)

        # TODO: maybe have an admin list?
        if text == "reloadallstamps" and (
            message.author.name == "robertskmiles" or message.author.name == "sudonym"
        ):
            print("FULL STAMP HISTORY RESET BAYBEEEEEE")
            self.reset_stamps()
            await self.load_votes_from_history()
            return 10, "Working on it, could take a bit"

        return 0, ""
