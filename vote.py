from module import Module
import discord

class Stamps(Module):

	def __str__(self):
		return "Stamps Module"

	def __init__(self):
		Module.__init__(self)
		self.goldmultiplier = 5  # gold stamp is worth how many red stamps?
		self.gamma = 1.0  # what proportion of the karma you get is passed on by your votes?

		self.reset_stamps()  # this initialises all the vote counting data structures empty
		#self.load_votesdict_from_json()
		self.calculate_stamps()


	def reset_stamps(self):
		print("WIPING STAMP RECORDS")

		robid = '181142785259208704'
		godid = "0"

		# votesdict is a dictionary of users and their voting info
		# keys are user ids
		# values are dicts containing:
		#    'votecount: how many times this user has voted
		#    'votes': A dict mapping user ids to how many times this user voted for them
		self.votesdict = {}
		# god is user id 0, and votes once, for rob (id 181142785259208704)
		self.votesdict[godid] = {'votecount': 1, 'votes': {robid: 1}}

		self.users = set([godid, robid])  # a set of all the users mentioned in votes
		self.ids = [godid, robid]  # an ordered list of the users' IDs

		self.totalvotes = 0

		self.scores = []

	def addvote(self, stamptype, fromid, toid, negative=False):
		toid = str(toid)
		fromid = str(fromid)

		if toid == '736241264856662038':  # votes for stampy do nothing
			return

		if toid == fromid:  # votes for yourself do nothing
			return

		if stamptype == "stamp":
			votestrength = 1
		elif stamptype == "goldstamp":
			votestrength = self.goldmultiplier

		if negative:  # are we actually undoing a vote?
			votestrength = -votestrength

		self.totalvotes += votestrength

		# ensure both users are in the users set
		'''self.users.add(fromid)
		self.users.add(toid)

		if stamptype == "stamp":
			votestrength = 1
		elif stamptype == "goldstamp":
			votestrength = self.goldmultiplier

		if negative:  # are we actually undoing a vote?
			votestrength = -votestrength

		self.totalvotes += votestrength

		u = self.votesdict.get(fromid, {'votecount': 0, 'votes': {}})
		u['votecount'] = u.get('votecount', 0) + votestrength
		u['votes'][toid] = u['votes'].get(toid, 0) + votestrength

		self.votesdict[fromid] = u'''

	def update_ids_list(self):
		for fromid, u in self.votesdict.items():
			self.users.add(fromid)
			for toid, _ in u['votes'].items():
				self.users.add(toid)

		self.ids = sorted(list(self.users))
		self.index = {"0": 0}
		for userid in self.ids:
			self.index[str(userid)] = self.ids.index(userid)

	def calculate_stamps(self):
		"""Set up and solve the system of linear equations"""
		print("RECALCULATING STAMP SCORES")

		self.update_ids_list()

		usercount = len(self.ids)

		A = np.zeros((usercount, usercount))
		for fromid, u in self.votesdict.items():
			fromi = self.index[fromid]

			for toid, votes in u['votes'].items():
				toi = self.index[toid]
				score = (self.gamma * votes) / u['votecount']

				A[toi, fromi] = score

		# set the diagonal to -1
		# c_score = a_score*a_votes_for_c + b_score*b_votes_for_c
		# becomes
		# a_score*a_votes_for_c + b_score*b_votes_for_c - c_score = 0
		# so the second array can be all zeros
		for i in range(1, usercount):
			print(sum(A[i]), sum(A[:,i]))
			A[i, i] = -1.0
		A[0, 0] = 1.0

		B = np.zeros(usercount)
		B[0] = 1.0  # God has 1 karma

		self.scores = list(np.linalg.solve(A, B))

		self.print_all_scores()


	def print_all_scores(self):
		totalstamps = 0
		for uid in self.users:
			name = client.get_user(int(uid))
			if not name:
				name = "<@" + uid + ">"
			stamps = self.get_user_stamps(uid)
			totalstamps += stamps
			print(name, "\t", stamps)

		print("Total votes:", self.totalvotes)
		print("Total Stamps:", totalstamps)

	def index_dammit(self, user):
		"""Get an index into the scores array from whatever you get"""

		if user in self.index:  # maybe we got given a valid ID?
			return self.index[user]
		elif str(user) in self.index:
			return self.index[str(user)]

		uid = getattr(user, 'id', None)  # maybe we got given a User or Member object that has an ID?
		if uid:
			return self.index[str(uid)]

		return None

	def get_user_score(self, user):
		index = self.index_dammit(user)
		return self.scores[index]

	def get_user_stamps(self, user):
		index = self.index_dammit(user)
		# stamps = int(self.scores[index] * self.totalvotes)
		# if not stamps:
		# 	stamps = self.scores[index] * self.totalvotes
		stamps = self.scores[index] * self.totalvotes
		return stamps

	def load_votes_from_csv(self, filename="stamps.csv"):
		# stampyid = 736241264856662038
		# robid = 181142785259208704

		with open(filename, "r") as stampsfile:
			stampsfile.readline()  # throw away the first line, it's headers
			for line in stampsfile:
				msgid, reacttype, fromid, toid = line.strip().split(",")
				msgid = int(msgid)
				fromid = int(fromid)
				toid = int(toid)
				
				print(msgid, reacttype, fromid, toid)
				self.addvote(reacttype, fromid, toid)

		self.save_votesdict_to_json()
		self.calculate_stamps()

	async def load_votes_from_history(self):
		"""Load up every time any stamp has been awarded by anyone in the whole history of the Discord
		This is omega slow, should basically only need to be called once"""
		guild = discord.utils.find(lambda g: g.name == guildname, client.guilds)

		with open("stamps.csv", 'w') as stamplog:
			stamplog.write("msgid,type,from,to\n")

			for channel in guild.channels:
				print("#### Considering", channel.type, type(channel.type), channel.name, "####")
				if channel.type == discord.ChannelType.text:
					print("#### Logging", channel.name, "####")
					async for message in channel.history(limit=None):
						# print("###########")
						# print(message.content[:20])
						reactions = message.reactions
						if reactions:
							# print(reactions)
							for reaction in reactions:
								reacttype = getattr(reaction.emoji, 'name', '')
								if reacttype in ["stamp", "goldstamp"]:
									# print("STAMP")
									users = await reaction.users().flatten()
									for user in users:
										string = "%s,%s,%s,%s" % (message.id, reacttype, user.id, message.author.id)
										print(string)
										stamplog.write(string + "\n")
										self.addvote(reacttype, user.id, message.author.id)
										# print("From", user.id, user)

		self.save_votesdict_to_json()
		self.calculate_stamps()


	def load_votesdict_from_json(self, filename="stamps.json"):
		with open(filename) as stampsfile:
			self.votesdict = json.load(stampsfile)

		self.totalvotes = 0
		for fromid, u in self.votesdict.items():
			self.totalvotes += u['votecount']

	def save_votesdict_to_json(self, filename="stamps.json"):
		with open(filename, 'w') as stampsfile:   # we modified the queue, put it in a file to persist
			json.dump(self.votesdict, stampsfile, indent="\t")

	async def processReactionEvent(self, reaction, user, eventtype='REACTION_ADD', client=None):
		# guild = discord.utils.find(lambda g: g.name == guildname, client.guilds)
		emoji = getattr(reaction.emoji, 'name', reaction.emoji)
		if emoji == 'stamp':
			print("### STAMP AWARDED ###")
			msgid = reaction.message.id
			fromid = user.id
			toid = reaction.message.audthor.id
			# print(msgid, re)
			string = "%s,%s,%s,%s" % (msgid, emoji, fromid, toid)
			print(string)
			# "msgid,type,from,to"

	async def processRawReactionEvent(self, event, client=None):
		eventtype = event.event_type
		guild = discord.utils.find(lambda g: g.name == guildname, client.guilds)
		channel = discord.utils.find(lambda c: c.id == event.channel_id, guild.channels)
		message = await channel.fetch_message(event.message_id)
		emoji = getattr(event.emoji, 'name', event.emoji)

		if message.author.id == 736241264856662038:  # votes for stampy don't affect voting
			return
		if message.author.id == event.user_id:  # votes for yourself don't affect voting
			if eventtype == 'REACTION_ADD' and emoji in ['stamp', 'goldstamp']:
				await channel.send("<@" + str(event.user_id) + "> just awarded a stamp to themselves...")
			return


		if emoji in ['stamp', 'goldstamp']:

			msgid = event.message_id
			fromid = event.user_id
			toid = message.author.id
			# print(msgid, re)
			string = "%s,%s,%s,%s" % (msgid, emoji, fromid, toid)
			print(string)

			print("### STAMP AWARDED ###")
			self.addvote(emoji, fromid, toid, negative=(eventtype=='REACTION_REMOVE'))
			self.save_votesdict_to_json()
			print("Score before stamp:", self.get_user_stamps(toid))
			self.calculate_stamps()
			print("Score after stamp:", self.get_user_stamps(toid))
			# "msgid,type,from,to"


	def canProcessMessage(self, message, client=None):
		if self.isatme(message):
			text = self.isatme(message)

			if re.match(r"(how many stamps am i worth)\??", text.lower()):
				return (9, "You're worth %.2f stamps to me" % self.get_user_stamps(message.author))

			elif text == "reloadallstamps" and message.author.name == "robertskmiles":
				return (10, "")

		return (0, "")

	async def processMessage(self, message, client=None):
		if self.isatme(message):
			text = self.isatme(message)

		if text == "reloadallstamps" and message.author.name == "robertskmiles":
			print("FULL STAMP HISTORY RESET BAYBEEEEEE")
			self.reset_stamps()
			await self.load_votes_from_history()
			return (10, "Working on it, could take a bit")

		return (0, "")
