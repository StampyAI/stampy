#!/usr/bin/env python3

#https://realpython.com/how-to-make-a-discord-bot-python/#how-to-make-a-discord-bot-in-python

import os
import sys
import traceback

from datetime import datetime, timezone, timedelta
import html
import json

import discord
from dotenv import load_dotenv

import sentience
import utilities


load_dotenv()

client = discord.Client()

utils = utilities.Utilities.getInstance(os.getenv('DATABASE_PATH'))
utils.client = client

utils.TOKEN = os.getenv('DISCORD_TOKEN')
utils.GUILD = os.getenv('DISCORD_GUILD')
utils.YTAPIKEY = os.getenv('YOUTUBE_API_KEY')
utils.DBPATH = os.getenv('DATABASE_PATH')

from module import Module
from stampcollection import Stamps
from questions import QQManager
from reply import Reply
from videosearch import VideoSearch
from invitemanager import InviteManager


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
		utils.lastmessagewasYTquestion = False

	if message.content == 'bot test':
		response = "I'm alive!"
		await message.channel.send(response)
	elif message.content.lower() == "Klaatu barada nikto".lower():
		await message.channel.send("I must go now, my planet needs me")
		exit()
	elif message.content.lower() == "mh":
		guild = discord.utils.find(lambda g: g.name == guildname, client.guilds)
		#general = discord.utils.find(lambda c: c.name == "general", guild.channels)
		

		with open("stamps.csv", 'w') as stamplog:
			stamplog.write("msgid,type,from,to\n")

			for channel in guild.channels:
				print("#### Considering", channel.type, channel.name, "####")
				if channel.type == discord.TextChannel:
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
										# print("From", user.id, user)
		return


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


@client.event
async def on_socket_raw_receive(msg):
	"""This event fires whenever basically anything at all happens.
		Anyone joining, leaving, sending anything, even typing and not sending...
		So I'm going to use it as a kind of 'update' or 'tick' function, for things the bot needs to do regularly. Yes this is hacky.
		Rate limit these things, because this function might be firing a lot"""
	

	# never fire more than once a second

	tickcooldown = timedelta(seconds=1)  
	now = datetime.now(timezone.utc)

	if (now - utils.lasttickts) > tickcooldown:
		print("|", end='')
		# print("last message was yt question?:", lastmessagewasYTquestion)
		utils.lasttickts = now
	else:
		print(".", end='')
		return

	# check for new youtube comments
	newcomments = utils.check_for_new_youtube_comments()
	if newcomments:
		for comment in newcomments:
			if "?" in comment['text']:
				utils.addQuestion(comment)
		#with open("qq.json", 'w') as qqfile:  # we modified the queue, put it in a file to persist
		#	json.dump(qq, qqfile, indent="\t")
	qq = utils.getNextQuestion("rowid")
	if qq:
		# ask a new question if it's been long enough since we last asked one
		qaskcooldown = timedelta(hours=8)

		if (now - utils.lastqaskts) > qaskcooldown:
			if not utils.lastmessagewasYTquestion:  # Don't ask anything if the last thing posted in the chat was us asking a question
				utils.lastqaskts = now
				report = utils.get_latest_question()
				guild = discord.utils.find(lambda g: g.name == guildname, client.guilds)
				general = discord.utils.find(lambda c: c.name == "general", guild.channels)
				await general.send(report)
				utils.lastmessagewasYTquestion = True
			else:
				utils.lastqaskts = now  # wait the full time again
				print("Would have asked a question, but the last post in the channel was a question we asked. So we wait")
		else:
			print("%s Questions in queue, waiting %s to post" % (len(qq), str(qaskcooldown - (now - utils.lastqaskts))))
			return

			# await message.channel.send(result)


@client.event
async def on_raw_reaction_add(payload):
	print("RAW REACTION")
	print(payload)

	for module in modules:
		await module.processRawReactionEvent(payload, client)


@client.event
async def on_raw_reaction_remove(payload):
	print("RAW REACTION")
	print(payload)

	for module in modules:
		await module.processRawReactionEvent(payload, client)

	# result = None

	# # What are the options for responding to this message?
	# # Prepopulate with a dummy module, with 0 confidence about its proposed response of ""
	# options = [(Module(), 0, "")]

	# for module in modules:
	# 	print("Asking module: %s" % str(module))
	# 	output = module.canProcessReaction(payload, client)
	# 	print("output is", output)
	# 	confidence, result = output
	# 	if confidence > 0:
	# 		options.append((module, confidence, result))

	# # Go with whichever module was most confident in its response
	# options = sorted(options, key=(lambda o: o[1]), reverse=True)
	# print(options)	
	# module, confidence, result = options[0]

	# if confidence > 0:  # if the module had some confidence it could reply
	# 	if not result:  # but didn't reply in canProcessMessage()
	# 		confidence, result = await module.processReactionEvent(payload, client)


if __name__ == "__main__":
	
	# when was the most recent comment we saw posted?
	utils.latestcommentts = datetime.now(timezone.utc)  # - timedelta(hours=8)

	# when did we last hit the API to check for comments?
	utils.lastcheckts = datetime.now(timezone.utc)

	# how many seconds should we wait before we can hit YT API again
	# this the start value. It doubles every time we don't find anything new
	utils.ytcooldown = utils.tds(60)


	# timestamp of when we last ran the tick function
	utils.lasttickts = datetime.now(timezone.utc)


	# timestamp of last time we asked a youtube question
	utils.lastqaskts = datetime.now(timezone.utc)

	guildname = utils.GUILD


	# Was the last message posted in #general by anyone, us asking a question from YouTube?
	utils.lastmessagewasYTquestion = True  # We start off not knowing, but it's better to assume yes than no

	modules = [Stamps(), QQManager(), VideoSearch(), Reply(), InviteManager()]


	client.run(utils.TOKEN)
