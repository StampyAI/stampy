from stam import isatme, Module
import asyncio
import discord


class InviteManagerModule(Module):

	def canProcessMessage(self, message, client=None):
		if isatme(message):
			text = isatme(message)

			if text == "create me an invite please":
				print(message.author.name, dir(message.author))
				if message.author.name == "robertskmiles":
					return (10, "")
				else:
					return (10, "You aren't allowed to do that")

					# invitecoro = message.channel.create_invite(max_uses=1,
					# 										temporary=True,
					# 										unique=True,
					# 										reason="Requested by %s" % message.author.name)

					# invitefuture = asyncio.run_coroutine_threadsafe(invitecoro, asyncio.get_running_loop())

					# print(invitefuture)
					# try:
					# 	invite = invitefuture.result(5)
					# except:
					# 	invitefuture.cancel()
					# 	return (10, "Error: Invite generation failed")

		# This is either not at me, or not something we can handle
		return (0, "")

	async def processMessage(self, message, client=None):
		"""Handle the message, return a string which is your response"""
		guild = client.guilds[0]
		welcome = discord.utils.find(lambda c: c.name == "welcome", guild.channels)
		invite = await welcome.create_invite(max_uses=1,
											temporary=True,
											unique=True,
											reason="Requested by %s" % message.author.name)

		print(invite)
		return (10, "Will do buddy: %s" % invite.url) 



		pass

	def __str__(self):
		return "Invite Manager Module"