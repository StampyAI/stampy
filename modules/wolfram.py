"""
Asks WolframAlpha for the answer
"""


import re
import urllib
from config import wolfram_token
from modules.module import Module, Response


class Wolfram(Module):
    """Module to send question to Wolfram Alpha

    We use the "short answers" API. Docs here:

    https://products.wolframalpha.com/short-answers-api/documentation

    You'll need a WOLFRAM_TOKEN setting in your .env file. You can get one
    here:

    https://developer.wolframalpha.com/portal/myapps/index.html

    In my experience it took a couple of minutes for queries to start
    succeeding after I set it up.
    """
    IRRELEVANT_WORDS = {"film", "movie", "tv", "song", "album", "band"}
    words = re.compile('[A-Za-z]+')

    def __str__(self):
        return "Wolfram Alpha"

    def process_message(self, message):
        text = self.is_at_me(message)

        if not wolfram_token or not text:
            return Response()

        if text.endswith("?"):
            return Response(
                confidence=5,
                callback=self.ask,
                args=[text],
                why="It's a question, we might be able to answer it",
            )
        else:
            return Response(
                confidence=1,
                callback=self.ask,
                args=[text],
                why="It's not a question but we might be able to look it up",
            )

    def confidence_of_answer(self, answer: str) -> float:
        """We already looked up an answer. How confident are we that it's good?"""
        answer_words = set(word.lower() for word in self.words.findall(answer))
        irrelevant_words_in_answer = answer_words & self.IRRELEVANT_WORDS
        if irrelevant_words_in_answer:
            self.log.info(
                self.class_name,
                msg=f"Answer contains {irrelevant_words_in_answer}, downrating",
            )
            return 1
        else:
            return 8

    def ask(self, question):
        try:
            self.log.info(self.class_name, wolfram_alpha_question=question)
            question_escaped = urllib.parse.quote_plus(question.strip())
            url = "http://api.wolframalpha.com/v1/result?appid=%s&i=%s" % (wolfram_token, question_escaped,)
            answer = urllib.request.urlopen(url).read().decode("utf-8")
            if "olfram" not in answer:
                return Response(
                    confidence=self.confidence_of_answer(answer),
                    text=answer,
                    why="That's what Wolfram Alpha suggested",
                )
        except Exception as e:
            self.log.error(self.class_name, msg="Wolfram failed with error:", error=e)
        return Response()

        # @property
        # def test_cases(self):
        #     return [
        #         self.create_integration_test(
        #             question="If I asked you what 2+2 was and you answered incorrectly what would you have said?",
        #             expected_response=CONFUSED_RESPONSE,
        #         )
        #     ]
