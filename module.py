from utilities import Utilities
import re
import discord 

class Module(object):
	from datetime import datetime, timezone, timedelta
	

	utils = None

	def __init__(self): 
		self.utils = Utilities.getInstance()
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
		return (0, "")

	# def canProcessReaction(self, reaction, client=None):
	# 	return (0, "")

	async def processReactionEvent(self, reaction, user, eventtype='REACTION_ADD', client=None):
		"""eventtype can be 'REACTION_ADD' or 'REACTION_REMOVE'
		Use this to allow modules to handle adding and removing reactions on messages"""
		return (0, "")

	async def processRawReactionEvent(self, event, client=None):
		"""event is a discord.RawReactionActionEvent object
		Use this to allow modules to handle adding and removing reactions on messages"""
		return (0, "")

	def __str__(self):
		return "Dummy Module"


	def isatme(self,message):
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