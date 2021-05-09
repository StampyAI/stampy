import re
from modules.module import Module


class QQManager(Module):
    """Module to manage commands about the question queue"""

    def __init__(self):
        Module.__init__(self)
        self.re_nextq = re.compile(
            r"(([wW]hat(’|'| i)?s|([Cc]an|[Mm]ay) (we|[iI]) (have|get)|[Ll]et(’|')?s have|[gG]ive us)"
            r"?( ?[Aa](nother)?|( the)? ?[nN]ext) question,?( please)?\??|([Dd]o you have|([Hh]ave you )"
            r"?[gG]ot)?( ?[Aa]ny( more| other)?| another) questions?( for us)?\??)!?"
        )

    def can_process_message(self, message, client=None):
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
                return 9, result
            elif self.re_nextq.match(text):  # we're being asked for the next question
                # Popping a question off the stack modifies things, so just return a
                # "yes, we can handle this" and let processMessage do it
                return 9, ""

        # This is either not at me, or not something we can handle
        return 0, ""

    async def process_message(self, message, client=None):
        if self.is_at_me(message):
            text = self.is_at_me(message)

            if self.re_nextq.match(text):
                result = self.utils.get_question()
                if result:
                    return 10, result
                else:
                    return 8, "There are no questions in the queue"
            else:
                print("Shouldn't be able to get here")
                return 0, ""

    def __str__(self):
        return "Question Queue Manager"
