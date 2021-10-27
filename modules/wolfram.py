from modules.module import Module, Response
import urllib
from config import wolfram_token


class Wolfram(Module):
    def process_message(self, message, client=None):
        text = self.is_at_me(message)
        if text:
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
        else:
            return Response()

    def __str__(self):
        return "Wolfram Alpha"

    def ask(self, question):
        try:
            print('asking Wolfram API: "%s"' % question)
            question_escaped = urllib.parse.quote_plus(question.strip())
            url = "http://api.wolframalpha.com/v1/result?appid=%s&i=%s" % (
                wolfram_token,
                question_escaped,
            )
            answer = urllib.request.urlopen(url).read().decode("utf-8")
            if "olfram" not in answer:
                return Response(confidence=8, text=answer, why="That's what Wolfram Alpha suggested")
        except Exception as e:
            print("Wolfram failed with error:", str(e))
        return Response()

        # @property
        # def test_cases(self):
        #     return [
        #         self.create_integration_test(
        #             question="If I asked you what 2+2 was and you answered incorrectly what would you have said?",
        #             expected_response=CONFUSED_RESPONSE,
        #         )
        #     ]
