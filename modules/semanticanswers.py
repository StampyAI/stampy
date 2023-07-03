"""
Checks if there are human-written answers to your queston on AIsafety.info
"""

import re
import json
import urllib
from modules.module import Module, Response

class SemanticAnswers(Module):

    def process_message(self, message):
        text = self.is_at_me(message)
        if text and text.endswith("?"):
            return Response(
                confidence=6,
                callback=self.ask,
                args=[text],
                why="It's a question, there might be a similar question in the database",
            )
        else:
            return Response()

    def __str__(self):
        return "Semantic Answers"

    def ask(self, question):
        q = question.lower().strip()
        url = (
            "https://stampy-nlp-t6p37v2uia-uw.a.run.app/api/search?query=%s"
            % urllib.parse.quote_plus(q)
        )
        
        try:
            data = urllib.request.urlopen(url, timeout=4).read()
            j = json.loads(data)

            self.log.info("SemanticAnswers", query=q, url=url)
            self.log.debug("SemanticAnswers", data=json.dumps(j, sort_keys=True, indent=2))

            for possible_answer in j:
                if possible_answer["score"] > 0.5:
                    if not possible_answer["url"].endswith("_"):
                        possible_answer["url"] = possible_answer["url"] + "_"
                    response = f"""Perhaps this can answer your question?
{possible_answer["url"]}"""

                    return Response(
                        confidence=8,
                        text=response,
                        why="I found a similar question with semantic search",
                    )

        except Exception as e:
            self.log.error("SemanticAnswers", error=e)
            raise(e)

        return Response()
