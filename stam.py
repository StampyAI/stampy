#!/usr/bin/env python3

#https://realpython.com/how-to-make-a-discord-bot-python/#how-to-make-a-discord-bot-in-python

import os
import sys
import traceback

from datetime import datetime, timezone, timedelta
import html
import json
import re

import discord
from dotenv import load_dotenv

import googleapiclient.discovery

import sentience


client = discord.Client()


class Module(object):
	"""Informal Interface specification for modules
	These represent packets of functionality. For each message,
	we show it to each module and ask if it can process the message,
	then give it to the module that's most confident"""

	def canProcessMessage(self, message, client=None):
		"""Look at the message and decide if you want to handle it
		Return a pair of values: (confidence rating out of 10, message)
		Including a response message is optional, use an empty string to just indicate a confidence
		If confidence is more than zero, and the message is empty, `processMessage` may be called
		`canProcessMessage` should contain only operations which can be executed safely even if another module reports a higher confidence and ends up being the one to respond.
		If your module is going to do something that only makes sense if it gets to repond, put that in `processMessage` instead

		Rough Guide:
		0 -> "This message isn't meant for this module, I have no idea what to do with it"
		1 -> "I could give a generic reply if I have to, as a last resort"
		2 -> "I can give a slightly better than generic reply, if I have to. e.g. I realise this is a question but don't know what it's asking"
		3 -> "I can probably handle this message with ok results, but I'm a frivolous/joke module"
		4 -> 
		5 -> "I can definitely handle this message with ok results, but probably other modules could too"
		6 -> "I can definitely handle this message with good results, but probably other modules could too"
		7 -> "This is a valid command specifically for this module, and the module is 'for fun' functionality"
		8 -> "This is a valid command specifically for this module, and the module is medium importance functionality"
		9 -> "This is a valid command specifically for this module, and the module is important functionality"
		10 -> "This is a valid command specifically for this module, and the module is critical functionality"

		Ties are broken in module priority order. You can also return a float if you really want
		"""
		# By default, we have 0 confidence that we can answer this, and our response is ""
		return (0, "")

	async def processMessage(self, message, client=None):
		"""Handle the message, return a string which is your response.
		This is an async function so it can interact with the Discord API if it needs to"""
		pass

	def __str__(self):
		return "Dummy Module"


def isatme(message):
	"""Determine if the message is directed at Stampy
	If it's not, return False. If it is, strip away the name part and return the remainder of the message"""

	text = message.content
	atme = False
	re_atme = re.compile(r"^@?[Ss]tampy\W? ")
	text, subs = re.subn("<@!?736241264856662038>|<@&737709107066306611>", 'Stampy', text)
	if subs:
		atme = True
	
	if (re_atme.match(text) is not None) or re.search(r'^[sS][,:]? ', text):
		atme = True
		print("X At me because re_atme matched or starting with [sS][,:]? ")
		text = text.partition(" ")[2]
	elif re.search(",? @?[sS](tampy)?[.!?]?$", text):  # name can also be at the end
		text = re.sub(",? @?[sS](tampy)?$", "", text)
		atme = True
		print("X At me because it ends with stampy")

	if type(message.channel) == discord.DMChannel:
		print("X At me because DM")
		atme = True  # DMs are always at you

	if atme:
		return text
	else:
		print("Message is Not At Me")
		return False


class QQManager(Module):
	"""Module to manage commands about the question queue"""
	def __init__(self):
		self.re_nextq = re.compile(r""".*(([wW]hat(’|'| i)?s|([Cc]an|[Mm]ay) (we|[iI]) (have|get)|[Ll]et(’|')?s have|[gG]ive us)?( ?[Aa](nother)?|( the)? ?[nN]ext) question,?( please)?\??|
?([Dd]o you have|([Hh]ave you )?[gG]ot)?( ?[Aa]ny( more| other)?| another) questions?( for us)?\??)!?""")

	def canProcessMessage(self, message, client=None):
		if isatme(message):
			text = isatme(message)

			if re.match(r"([hH]ow many questions (are (there )?)?in|[hH]ow (long is|long's)) (the|your)( question)? queue( now)?\??", text):
				if qq:
					if len(qq) == 1:
						result = "There's one question in the queue"
					else:
						result = "There are %d questions in the queue" % len(qq)
				else:
					result = "The question queue is empty"
				return (9, result)
			elif self.re_nextq.match(text):  # we're being asked for the next question
				return (9, "")  # Popping a question off the stack modifies things, so just return a "yes, we can handle this" and let processMessage do it

		# This is either not at me, or not something we can handle
		return (0, "")

	async def processMessage(self, message, client):
		if isatme(message):
			text = isatme(message)

			if self.re_nextq.match(text):
				result = get_latest_question()
				if result:
					return (10, result)
				else:
					return (8, "There are no questions in the queue")
			else:
				print("Shouldn't be able to get here")
				return (0, "") 

	def __str__(self):
		return "Question Queue Manager"


@client.event
async def on_ready():
	print(f'{client.user} has connected to Discord!')
	guild = discord.utils.find(lambda g: g.name == guildname, client.guilds)

	print(guild.id, guild.name)

	members = '\n - '.join([member.name for member in guild.members])
	print(f'Guild Members:\n - {members}')


@client.event
async def on_message(message):
	# don't react to our own messages
	if message.author == client.user:
		return

	print("########################################################")
	print(message.author, message.content)

	if hasattr(message.channel, 'name') and message.channel.name == "general":
		print("Last message was no longer us")
		global lastmessagewasYTquestion
		lastmessagewasYTquestion = False

	if message.content == 'bot test':
		response = "I'm alive!"
		await message.channel.send(response)
	elif message.content.lower() == "Klaatu barada nikto".lower():
		await message.channel.send("I must go now, my planet needs me")
		exit()
	# elif message.content.lower() == "invite test" and message.author.name == "robertskmiles":
	# 	guild = discord.utils.find(lambda g: g.name == guildname, client.guilds)
	# 	welcome = discord.utils.find(lambda c: c.name == "welcome", guild.channels)
	# 	invite = await welcome.create_invite(max_uses=1,
	# 										temporary=True,
	# 										unique=True,
	# 										reason="Requested by %s" % message.author.name)
	# 	print(invite)
	# 	await message.channel.send(invite.url)

	result = None

	# What are the options for responding to this message?
	# Prepopulate with a dummy module, with 0 confidence about its proposed response of ""
	options = [(Module(), 0, "")]

	for module in modules:
		print("Asking module: %s" % str(module))
		output = module.canProcessMessage(message, client)
		print("output is", output)
		confidence, result = output
		if confidence > 0:
			options.append((module, confidence, result))

	# Go with whichever module was most confident in its response
	options = sorted(options, key=(lambda o: o[1]), reverse=True)
	print(options)	
	module, confidence, result = options[0]

	if confidence > 0:  # if the module had some confidence it could reply
		if not result:  # but didn't reply in canProcessMessage()
			confidence, result = await module.processMessage(message, client)

	if not result:  # no results from the modules, try the sentience core
		try:
			result = sentience.processMessage(message, client)
		except Exception as e:
			if hasattr(message.channel, 'name') and message.channel.name in ("bot-dev", "bot-dev-priv", "181142785259208704"):
				try:
					errortype = sentience.dereference("{{$errorType}}")  # grab a random error type from the factoid db
				except:
					errortype = "SeriousError"  # if the dereference failed, it's bad
				x = sys.exc_info()[2].tb_next
				print(e, type(e))
				traceback.print_tb(x)
				lineno = sys.exc_info()[2].tb_next.tb_lineno
				result = "%s %s: %s" % (errortype, lineno, str(e))
			else:
				x = sys.exc_info()[2].tb_next
				print(e, type(e))
				traceback.print_tb(x)

	if result:
		await message.channel.send(result)

	print("########################################################")


def tds(s):
	"""Make a timedelta object of s seconds"""
	return timedelta(seconds=s)


def check_for_new_youtube_comments():
	"""Consider getting the latest comments from the channel
	Returns a list of dicts if there are new comments
	Returns [] if it checked and there are no new ones 
	Returns None if it didn't check because it's too soon to check again"""

	# print("Checking for new YT comments")

	global latestcommentts
	global lastcheckts
	global ytcooldown

	now = datetime.now(timezone.utc)

	# print("It has been this long since I last called the YT API: " + str(now - lastcheckts))
	# print("Current cooldown is: " + str(ytcooldown))
	if (now - lastcheckts) > ytcooldown:
		print("Hitting YT API")
		lastcheckts = now
	else:
		print("YT waiting >%s\t- " % str(ytcooldown - (now - lastcheckts)), end='')
		return None

	api_service_name = "youtube"
	api_version = "v3"
	DEVELOPER_KEY = YTAPIKEY

	youtube = googleapiclient.discovery.build(api_service_name, api_version, developerKey=DEVELOPER_KEY)

	request = youtube.commentThreads().list(
		part="snippet",
		allThreadsRelatedToChannelId="UCLB7AzTwc6VFZrBsO2ucBMg"
	)
	response = request.execute()

	items = response.get('items', None)
	if not items:
		print("YT comment checking broke. I got this response:")
		print(response)
		ytcooldown = ytcooldown * 10  # something broke, slow way down
		return None

	newestts = latestcommentts

	newitems = []
	for item in items:
		# Find when the comment was published
		pubTsStr = item['snippet']['topLevelComment']['snippet']['publishedAt']
		# For some reason fromisoformat() doesn't like the trailing 'Z' on timestmaps
		# And we add the "+00:00" so it knows to use UTC
		pubTs = datetime.fromisoformat(pubTsStr[:-1] + "+00:00")

		# If this comment is newer than the newest one from last time we called API, keep it
		if pubTs > latestcommentts:
			newitems.append(item)

		# Keep track of which is the newest in this API call
		if pubTs > newestts:
			newestts = pubTs

	print("Got %s items, most recent published at %s" % (len(items), newestts))

	# save the timestamp of the newest comment we found, so next API call knows what's fresh
	latestcommentts = newestts

	newcomments = []
	for item in newitems:
		videoId = item['snippet']['topLevelComment']['snippet']['videoId']
		commentId = item['snippet']['topLevelComment']['id']
		username = item['snippet']['topLevelComment']['snippet']['authorDisplayName']
		text = item['snippet']['topLevelComment']['snippet']['textOriginal']
		# print("dsiplay text:" + item['snippet']['topLevelComment']['snippet']['textDisplay'])
		# print("original text:" + item['snippet']['topLevelComment']['snippet']['textOriginal'])

		comment = {'url': "https://www.youtube.com/watch?v=%s&lc=%s" % (videoId, commentId),
					'username': username,
					'text': text,
					'title': ""
				  }

		newcomments.append(comment)

	print("Got %d new comments since last check" % len(newcomments))

	if not newcomments:
		# we got nothing, double the cooldown period (but not more than 20 minutes)
		ytcooldown = min(ytcooldown * 2, tds(1200))
		print("No new comments, increasing cooldown timer to %s" % ytcooldown)

	return newcomments



latestquestionposted = None

def get_latest_question():
	"""Pull the oldest question from the queue
	Returns False if the queue is empty, the question string otherwise"""
	global qq
	if not qq:
		return False

	# comment = qq.pop(0)	
	# pop from the end, meaning this is actually a stack not a queue
	# This was changed when all the historical questions were added in. So now it's newest first
	comment = qq.pop()

	global latestquestionposted
	latestquestionposted = comment

	text = comment['text']
	if len(text) > 1500:
		text = text[:1500] + " [truncated]"
	comment['textquoted'] = "> " + "\n> ".join(text.split("\n"))

	title = comment.get("title", "")
	if title:
		report = """YouTube user \'%(username)s\' asked this question, on the video \'%(title)s\'!:
%(textquoted)s
Is it an interesting question? Maybe we can answer it!
<%(url)s>""" % comment

	else:
		report = """YouTube user \'%(username)s\' just asked a question!:
%(textquoted)s
Is it an interesting question? Maybe we can answer it!
<%(url)s>""" % comment

	print("==========================")
	print(report)
	print("==========================")

	with open("qq.json", 'w') as qqfile:   # we modified the queue, put it in a file to persist
		json.dump(qq, qqfile, indent="\t")

	global lastqaskts
	lastqaskts = datetime.now(timezone.utc)  # reset the question waiting timer

	return report


@client.event
async def on_socket_raw_receive(msg):
	"""This event fires whenever basically anything at all happens.
		Anyone joining, leaving, sending anything, even typing and not sending...
		So I'm going to use it as a kind of 'update' or 'tick' function, for things the bot needs to do regularly. Yes this is hacky.
		Rate limit these things, because this function might be firing a lot"""
	
	global lastmessagewasYTquestion

	# never fire more than once a second
	global lasttickts
	tickcooldown = timedelta(seconds=1)  
	now = datetime.now(timezone.utc)

	if (now - lasttickts) > tickcooldown:
		print("|", end='')
		# print("last message was yt question?:", lastmessagewasYTquestion)
		lasttickts = now
	else:
		print(".", end='')
		return

	# check for new youtube comments
	newcomments = check_for_new_youtube_comments()
	if newcomments:
		for comment in newcomments:
			if "?" in comment['text']:
				qq.append(comment)
		with open("qq.json", 'w') as qqfile:  # we modified the queue, put it in a file to persist
			json.dump(qq, qqfile, indent="\t")

	if qq:
		# ask a new question if it's been long enough since we last asked one
		global lastqaskts
		qaskcooldown = timedelta(hours=8)

		if (now - lastqaskts) > qaskcooldown:
			if not lastmessagewasYTquestion:  # Don't ask anything if the last thing posted in the chat was us asking a question
				lastqaskts = now
				report = get_latest_question()
				guild = discord.utils.find(lambda g: g.name == guildname, client.guilds)
				general = discord.utils.find(lambda c: c.name == "general", guild.channels)
				await general.send(report)
				lastmessagewasYTquestion = True
			else:
				lastqaskts = now  # wait the full time again
				print("Would have asked a question, but the last post in the channel was a question we asked. So we wait")
		else:
			print("%s Questions in queue, waiting %s to post" % (len(qq), str(qaskcooldown - (now - lastqaskts))))
			return

			# await message.channel.send(result)


class ReplyModule(Module):

	def __str__(self):
		return "YouTube Reply Posting Module"

	def isPostRequest(self, text):
		"""Is this message asking us to post a reply?"""
		print(text)
		return text.endswith("post this")

	def isAllowed(self, message, client):
		"""Is the message author authorised to make stampy post replies?"""
		postingrole = discord.utils.find(lambda r: r.name == 'poaster', message.guild.roles)
		return postingrole in message.author.roles

	def extractReply(self, text):
		"""Pull the text of the reply out of the message"""
		lines = text.split("\n")
		replymessage = ""
		for line in lines:
			# pull out the quote syntax "> " and a user if there is one
			match = re.match("([^#]+#\d\d\d\d )?> (.*)", line)
			if match:
				replymessage += match.group(2) + "\n"

		return replymessage

	def postReply(self, text, questionid):
		"""Actually post the reply to YouTube. Currently this involves a horrible hack"""

		#first build the dictionary that will be passed to youtube.comments().insert as the 'body' arg
		body = {'snippet': {
					'parentId': questionid,
					'textOriginal': text,
					'authorChannelId': {
						'value': 'UCFDiTXRowzFvh81VOsnf5wg'
						}
					}
				}

		# now we're going to put it in a json file, which CommentPoster.py will read and send it
		with open("topost.json") as postfile:
			topost = json.load(postfile)

		topost.append(body)

		with open("topost.json", 'w') as postfile:
			json.dump(topost, postfile, indent="\t")

		print("dummy, posting %s to %s" % (text, questionid))

	def canProcessMessage(self, message, client=None):
		"""From the Module() Interface. Is this a message we can process?"""
		if isatme(message):
			text = isatme(message)

			if self.isPostRequest(text):
				print("this is a posting request")
				if self.isAllowed(message, client):
					print("the user is allowed")
					return (9, "")
				else:
					return (9, "Only people with the `poaster` role can do that")
	
		return (0, "")

	async def processMessage(self, message, client):
		"""From the Module() Interface. Handle a reply posting request message"""
		text = isatme(message)  # strip off stampy's name
		replymessage = self.extractReply(text)
		replymessage += "\n -- _I am a bot. This reply was approved by %s_" % message.author.name

		report = ""

		global latestquestionposted
		if not latestquestionposted:
			# return (10, "I can't do that because I don't remember the URL of the last question I posted here. I've probably been restarted since that happened")
			report = "I don't remember the URL of the last question I posted here, so I've probably been restarted since that happened. I'll just post to the dummy thread instead...\n\n"
			latestquestionposted = {'url': "https://www.youtube.com/watch?v=vuYtSDMBLtQ&lc=Ugx2FUdOI6GuxSBkOQd4AaABAg"}  # use the dummy thread

		questionid = re.match(r".*lc=([^&]+)", latestquestionposted['url']).group(1)

		quotedreplymessage = "> " + replymessage.replace("\n", "\n> ")
		report += "Ok, posting this:\n %s\n\nas a response to this question: <%s>" % (quotedreplymessage, latestquestionposted['url'])

		self.postReply(replymessage, questionid)

		return (10, report)



@client.event
async def on_raw_reaction_add(payload):
	print("RAW REACTION")
	print(payload)


@client.event
async def on_reaction_add(reaction, user):
	if user == client.user:
		return
	print("REACTION")
	print(reaction)
	print(user)




if __name__ == "__main__":
	load_dotenv()
	TOKEN = os.getenv('DISCORD_TOKEN')
	GUILD = os.getenv('DISCORD_GUILD')
	YTAPIKEY = os.getenv('YOUTUBE_API_KEY')


	# when was the most recent comment we saw posted?
	latestcommentts = datetime.now(timezone.utc)  # - timedelta(hours=8)

	# when did we last hit the API to check for comments?
	lastcheckts = datetime.now(timezone.utc)

	# how many seconds should we wait before we can hit YT API again
	# this the start value. It doubles every time we don't find anything new
	ytcooldown = tds(60)


	# timestamp of when we last ran the tick function
	lasttickts = datetime.now(timezone.utc)

	# Load the question queue from the file
	with open("qq.json") as qqfile:
		qq = json.load(qqfile)
	print("Loaded Question Queue from file")
	print("%s questions loaded" % len(qq))

	# timestamp of last time we asked a youtube question
	lastqaskts = datetime.now(timezone.utc)

	guildname = "Rob Miles AI Discord"

	# Was the last messages posted in #general by anyone, us asking a question from YouTube?
	lastmessagewasYTquestion = True  # We start off not knowing, but it's better to assume yes than no

	from videosearch import VideoSearchModule
	from InviteManagerModule import InviteManagerModule

	modules = [QQManager(), VideoSearchModule(), ReplyModule(), InviteManagerModule()]


	client.run(TOKEN)
