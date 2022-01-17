from modules.module import Module, Response
import urllib
import re
import json


class DuckDuckGo(Module):
    def process_message(self, message):
        text = self.is_at_me(message)
        if text:
            if text.endswith("?"):
                return Response(
                    confidence=6,
                    callback=self.ask,
                    args=[text],
                    why="It's a question, we might be able to answer it",
                )
            else:
                return Response(
                    confidence=2,
                    callback=self.ask,
                    args=[text],
                    why="It's not a question but we might be able to look it up",
                )
        else:
            return Response()

    def __str__(self):
        return "DuckDuckGo"

    def ask(self, question):
        q = question.lower().strip().strip("?")
        q = re.sub(r"w(hat|ho)('s|'re| is| are| was| were) ?", "", q)
        q = re.sub(r"(what do you know||(what )?(can you)? ?tell me) about", "", q)
        url = (
            "https://api.duckduckgo.com/?q=%s&format=json&nohtml=1&skip_disambig=1"
            % urllib.parse.quote_plus(q)
        )
        try:
            data = urllib.request.urlopen(url).read()
            j = json.loads(data)

            print('asking DuckDuckGo: "%s"' % q)
            print(url)
            # print(json.dumps(j, sort_keys=True, indent=2))
            if j["Abstract"]:
                answer = j["Abstract"]
                return Response(confidence=7, text=answer, why="That's what DuckDuckGo suggested")
            elif j["Type"] == "D":
                answer = j["RelatedTopics"][0]["Text"]
                if answer.endswith("...") and (". " in answer):
                    answer = ". ".join(answer.split(". ")[:-1])
                return Response(
                    confidence=6,
                    text=answer,
                    why="That's what DuckDuckGo suggested",
                )
        except Exception as e:
            print("DuckDuckGo failed with error:", str(e))

        return Response()

        # @property
        # def test_cases(self):
        #     return [
        #         self.create_integration_test(
        #             question="If I asked you what 2+2 was and you answered incorrectly what would you have said?",
        #             expected_response=CONFUSED_RESPONSE,
        #         )
        #     ]
