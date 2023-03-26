import re
import json
from urllib.parse import quote_plus
from urllib.request import urlopen

from modules.module import Module, Response
from utilities.serviceutils import ServiceMessage


class DuckDuckGo(Module):
    """DuckDuckGo module"""

    # Some types of things we don't really care about
    IRRELEVANT_WORDS = {"film", "movie", "tv", "song", "album", "band"}
    words = re.compile("[A-Za-z]+")

    def __init__(self) -> None:
        super().__init__()
        self.class_name = self.__class__.__name__

    def process_message(self, message: ServiceMessage) -> Response:
        """Process message and return a response if this module can handle it."""
        text = self.is_at_me(message)
        if text is False:
            return Response()
        
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

    def __str__(self):
        return "DuckDuckGo"

    def get_confidence(self, answer: str, max_confidence: float) -> float:
        """How confident should I be with this response string?"""
        answer_words = set(word.lower() for word in self.words.findall(answer))
        irrelevant_words_in_answer = answer_words & self.IRRELEVANT_WORDS
        if irrelevant_words_in_answer:
            self.log.info(
                self.class_name,
                msg=f"Answer contains {irrelevant_words_in_answer}, downrating to 1",
            )
            return 1
        return max_confidence

    def ask(self, question: str) -> Response:
        """Ask DuckDuckGo a question and return a response."""

        # strip out question mark and common 'question phrases', e.g. 'who are',
        # 'what is', 'tell me about'
        q = question.lower().strip().strip("?")
        q = re.sub(r"w(hat|ho)('s|'re| is| are| was| were) ?", "", q)
        q = re.sub(r"(what do you know|(what )?(can you)? ?tell me) about", "", q)

        # create url which searches DuckDuckGo for the question
        url = f"https://api.duckduckgo.com/?q={quote_plus(q)}&format=json&nohtml=1&skip_disambig=1"
        try:
            data = urlopen(url).read()
            j = json.loads(data)

            self.log.info(self.class_name, query=q, url=url)
            debug_keys = ["Abstract", "AbstractSource", "AbstractURL", "Entity", "Type"]
            debug_data = {k: j.get(k) for k in debug_keys}

            if j["Abstract"]:
                answer = j["Abstract"]
                self.log.debug(
                    self.class_name,
                    data=json.dumps(debug_data, sort_keys=True, indent=2),
                )
                return Response(
                    confidence=self.get_confidence(answer, 7),
                    text=answer,
                    why="That's what DuckDuckGo suggested",
                )

            if j["Type"] == "D":
                answer: str = j["RelatedTopics"][0]["Text"]
                debug_data["RelatedTopics_texts"] = [
                    rt["Text"] for rt in j["RelatedTopics"]
                ]
                self.log.debug(
                    self.class_name,
                    data=json.dumps(debug_data, sort_keys=True, indent=2),
                )

                # If the response cuts off with ... then throw out the last sentence
                if answer.endswith("...") and (". " in answer):
                    answer = ". ".join(answer.split(". ")[:-1])

                return Response(
                    confidence=self.get_confidence(answer, 6),
                    text=answer,
                    why="That's what DuckDuckGo suggested",
                )
        except Exception as e:
            self.log.error(self.class_name, error=e)

        return Response()

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                question="what is linear algebra?",
                expected_regex="Linear algebra is the branch of mathematics concerning linear equations",
            ),
            self.create_integration_test(
                question="what is deep learning?",
                expected_regex="Deep learning is part of a broader family of machine learning method",
            ),
        ]