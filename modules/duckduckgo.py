import re
import json
import urllib
from modules.module import Module, Response


class DuckDuckGo(Module):
    # Some types of things we don't really care about
    IRRELEVANT_WORDS = {"film", "movie", "tv", "song", "album", "band"}
    words = re.compile('[A-Za-z]+')

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

    def get_confidence(self, answer: str, max_confidence: float) -> float:
        """How confident should I be with this response string?"""
        answer_words = set(word.lower() for word in self.words.findall(answer))
        irrelevant_words_in_answer = answer_words & self.IRRELEVANT_WORDS
        if irrelevant_words_in_answer:
            self.log.info(
                "DuckDuckGo",
                msg=f"Answer contains {irrelevant_words_in_answer}, downrating",
            )
            return 1
        else:
            return max_confidence

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

            self.log.info("DuckDuckGo", query=q, url=url)
            self.log.debug("DuckDuckGo", data=json.dumps(j, sort_keys=True, indent=2))

            if j["Abstract"]:
                answer = j["Abstract"]
                return Response(
                    confidence=self.get_confidence(answer, 7),
                    text=answer,
                    why="That's what DuckDuckGo suggested",
                )
            elif j["Type"] == "D":
                answer = j["RelatedTopics"][0]["Text"]

                # If the response cuts off with ... then throw out the last sentence
                if answer.endswith("...") and (". " in answer):
                    answer = ". ".join(answer.split(". ")[:-1])

                return Response(
                    confidence=self.get_confidence(answer, 6),
                    text=answer,
                    why="That's what DuckDuckGo suggested",
                )
        except Exception as e:
            self.log.error("DuckDuckGo", error=e)

        return Response()
