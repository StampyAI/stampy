import re
from modules.module import Module, Response


class QQManager(Module):
    """Module to manage commands about the question queue"""

    def __init__(self):
        Module.__init__(self)

        self.re_next_question = re.compile(
            r"(([wW]hat(’|'| i)?s|([Cc]an|[Mm]ay) (we|[iI]) (have|get)|[Ll]et[’']?s have|[gG]ive us)"
            r"?( ?[Aa](nother)?|( the)? ?[nN]ext) question,?( please)?\??|([Dd]o you have|([Hh]ave you )"
            r"?[gG]ot)?( ?[Aa]ny( more| other)?| another) questions?( for us)?\??)!?"
        )

    def process_message(self, message, client=None):
        if self.is_at_me(message):
            text = self.is_at_me(message)
            if re.match(
                r"([hH]ow many questions (are (there )?)?(left )?in)|([hH]ow "
                r"(long is|long's)) (the|your)( question)? queue( now)?\??",
                text,
            ):
                qq = self.utils.get_question_count()
                if qq:
                    if qq == 1:
                        result = "There's one question in the queue"
                    else:
                        result = "There are %d questions in the queue" % qq
                else:
                    result = "The question queue is empty"
                return Response(
                    confidence=9, text=result, why="%s asked about the question queue" % message.author.name
                )
            elif self.re_next_question.match(text):  # we're being asked for the next question
                # Popping a question off the stack modifies things, so do it with a callback
                return Response(confidence=10, callback=self.post_question, args=[message])

        # This is either not at me, or not something we can handle
        return Response()

    async def post_question(self, message):
        result = self.utils.get_question()
        if result:
            return Response(
                confidence=10, text=result, why="%s asked for a question to answer" % message.author.name
            )
        else:
            return Response(
                confidence=8,
                text="There are no questions in the queue",
                why="%s asked for a question to answer, but I haven't got any" % message.author.name,
            )

    def __str__(self):
        return "Question Queue Manager"
