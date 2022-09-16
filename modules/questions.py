import re
from api.semanticwiki import SemanticWiki
from modules.module import Module, Response


class QuestionQueueManager(Module):
    """Module to manage commands about the question queue"""

    EMPTY_QUEUE_MESSAGE = "There are no questions in the queue"

    def __init__(self):
        Module.__init__(self)

        generic_question_regex = (
            r"(([wW]hat(’|'| i)?s|([Cc]an|[Mm]ay) (we|[iI]) (have|get)|[Ll]et[’']?s have|[gG]ive us)"
            r"?( ?[Aa](nother)?|( the)? ?[nN]ext) {question_type},?( please)?\??|([Dd]o you have|([Hh]ave you )"
            r"?[gG]ot)?( ?[Aa]ny( more| other)?| another) {question_type}s?( for us)?\??)!?"
        )

        self.re_next_question_generic_regex = re.compile(
            generic_question_regex.format(question_type="question")
        )
        self.re_next_question_wiki_regex = re.compile(
            generic_question_regex.format(question_type="wiki question")
        )
        self.re_next_question_yt_regex = re.compile(
            generic_question_regex.format(question_type="[yY](ou)?[tT](ube)? question")
        )
        self.question_count_regex = re.compile(
            r"""
            (
                ( # how many questions are there left in ...
                how\s+many\s+questions\s+
                (are\s+(there\s+)?)?
                ((left\s+)?in\s+)?
                )
            |
                ( # how long is/'s the/your questions queue now
                how\s+
                (long\s+is|long's)\s+
                (the\s+|your\s+)?
                (question\s+)?
                queue
                (\s+now)?
                )
            )
            \?? # optional question mark
            """, re.X | re.I
        )

    def question_count_response(self, count):
        if count:
            if count == 1:
                result = "There's one question in the queue"
            else:
                result = f"There are {count} questions in the queue"
        else:
            result = self.EMPTY_QUEUE_MESSAGE
        return result

    def process_message(self, message):
        if self.is_at_me(message):
            text = self.is_at_me(message)
            if self.question_count_regex.match(text):
                count = self.utils.get_question_count()
                return Response(
                    confidence=9,
                    text=self.question_count_response(count),
                    why=f"{message.author.name} asked about the question queue",
                )
            elif self.re_next_question_generic_regex.match(text):  # we're being asked for the next question
                # Popping a question off the stack modifies things, so do it with a callback
                return Response(confidence=10, callback=self.post_question, args=[message])
            elif self.re_next_question_wiki_regex.match(text):
                return Response(
                    confidence=10,
                    callback=self.post_question,
                    args=[message],
                    kwargs={"wiki_question_bias": 1},
                )  # always give a wiki question
            elif self.re_next_question_yt_regex.match(text):
                return Response(
                    confidence=10,
                    callback=self.post_question,
                    args=[message],
                    kwargs={"wiki_question_bias": -1},
                )  # never give a wiki question

        # This is either not at me, or not something we can handle
        return Response()

    async def post_question(
        self, message, wiki_question_bias=SemanticWiki.default_wiki_question_percent_bias
    ):
        if self.utils.test_mode:
            return Response(confidence=9, text=self.EMPTY_QUEUE_MESSAGE, why="test")
        result = self.utils.get_question(wiki_question_bias=wiki_question_bias)
        self.log.info("QQManager", post_question_result=result, message_author=message.author.name)
        if result:
            return Response(
                confidence=10, text=result, why="%s asked for a question to answer" % message.author.name
            )
        else:
            return Response(
                confidence=8,
                text=self.EMPTY_QUEUE_MESSAGE,
                why="%s asked for a question to answer, but I haven't got any" % message.author.name,
            )

    def __str__(self):
        return "Question Queue Manager"

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                question="how many questions are in the queue?",
                expected_response=self.question_count_response(self.utils.get_question_count()),
            ),
            self.create_integration_test(
                question="what is the next questions in the queue",
                expected_response=self.EMPTY_QUEUE_MESSAGE,
            ),  # TODO update test to allow for actual checking of questions
        ]
