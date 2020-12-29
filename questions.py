from module import Module
import re
import discord

class QQManager(Module):
	"""Module to manage commands about the question queue"""
	def __init__(self):
		Module.__init__(self)
		self.re_nextq = re.compile(r""".*(([wW]hat(’|'| i)?s|([Cc]an|[Mm]ay) (we|[iI]) (have|get)|[Ll]et(’|')?s have|[gG]ive us)?( ?[Aa](nother)?|( the)? ?[nN]ext) question,?( please)?\??|
?([Dd]o you have|([Hh]ave you )?[gG]ot)?( ?[Aa]ny( more| other)?| another) questions?( for us)?\??)!?""")

	def canProcessMessage(self, message, client=None):
		if self.isatme(message):
			text = self.isatme(message)

			if re.match(r"([hH]ow many questions (are (there )?)?in|[hH]ow (long is|long's)) (the|your)( question)? queue( now)?\??", text):
				qq = self.utils.getQuestionCount()
				if qq:
					if qq == 1:
						result = "There's one question in the queue"
					else:
						result = "There are %d questions in the queue" % qq
				else:
					result = "The question queue is empty"
				return (9, result)
			elif self.re_nextq.match(text):  # we're being asked for the next question
				return (9, "")  # Popping a question off the stack modifies things, so just return a "yes, we can handle this" and let processMessage do it

		# This is either not at me, or not something we can handle
		return (0, "")

	async def processMessage(self, message, client):
		if self.isatme(message):
			text = self.isatme(message)

			if self.re_nextq.match(text):
				result = self.utils.get_latest_question()
				if result:
					return (10, result)
				else:
					return (8, "There are no questions in the queue")
			else:
				print("Shouldn't be able to get here")
				return (0, "") 

	def __str__(self):
		return "Question Queue Manager"

