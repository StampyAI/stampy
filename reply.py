from module import Module
import discord
import re
import json

class Reply(Module):

	def __str__(self):
		return "YouTube Reply Posting Module"

	def __init__(self):
		Module.__init__(self)

	def isPostRequest(self, text):
		"""Is this message asking us to post a reply?"""
		print(text)
		if text:
			return text.lower().endswith("post this") or text.lower().endswith("send this")
		else:
			return False

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
		if self.isatme(message):
			text = self.isatme(message)

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
		text = self.isatme(message)  # strip off stampy's name
		replymessage = self.extractReply(text)
		replymessage += "\n -- _I am a bot. This reply was approved by %s_" % message.author.name

		report = ""

		# global latestquestionposted
		if not self.utils.latestquestionposted:
			# return (10, "I can't do that because I don't remember the URL of the last question I posted here. I've probably been restarted since that happened")
			report = "I don't remember the URL of the last question I posted here, so I've probably been restarted since that happened. I'll just post to the dummy thread instead...\n\n"
			self.utils.latestquestionposted = {'url': "https://www.youtube.com/watch?v=vuYtSDMBLtQ&lc=Ugx2FUdOI6GuxSBkOQd4AaABAg"}  # use the dummy thread

		questionid = re.match(r".*lc=([^&]+)", self.utils.latestquestionposted['url']).group(1)

		quotedreplymessage = "> " + replymessage.replace("\n", "\n> ")
		report += "Ok, posting this:\n %s\n\nas a response to this question: <%s>" % (quotedreplymessage, self.utils.latestquestionposted['url'])

		self.postReply(replymessage, questionid)

		return (10, report)

