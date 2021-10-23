if __name__ == "__main__":
    # take a json file from querying the wiki and turn it into a jsonl file for openai
    # json file of canonical questions got from
    # https://stampy.ai/w/api.php?action=ask&query=%5B%5BCategory%3AQuestions%5D%5D%5B%5BCanonical%3A%3Atrue%5D%5D%5B%5BOutOfScope%3A%3Afalse%5D%5D%7Cformat%3Dplainlist%7C%3FQuestion%7Climit%3D3&format=jsonfm

    max_question_chars = 1500  # no super long questions

    openai_jsonl_lines = []
    # j = json.load(open("3questions.json"))
    j = json.load(open("allcanonical.json"))
    for result in j["query"]["results"].values():
        question_title = result["fulltext"]  # this is the title, misleadingly named in the query result
        question_text = result["printouts"]["Question"][0][:max_question_chars]
        question_url = result["fullurl"]

        # The text and title are often the same. If not, append one to the other
        question_full_text = question_title
        if question_text != question_title:
            question_full_text += f"\n\n{question_text}"

        # We only get to store a single string with openai as 'metadata'.
        # It would be fine to make this just the url to the question
        # but we'll for sure want to store other things in future
        # is it canonical? has it been replied to? etc.
        # so we'll store a json string of a dict instead
        metadata = json.dumps({"url": question_url})

        # print(question_text, question_title)
        openai_document_json = json.dumps({"text": question_full_text, "metadata": metadata})
        openai_jsonl_lines.append(openai_document_json)

    openai_jsonl = "\n".join(openai_jsonl_lines)

    print(openai_jsonl)

    import os
    import openai
    import io

    openai.api_key = os.getenv("OPENAI_API_KEY")

    # upload the jsonl 'file' to openai
    # response = openai.File.create(file=io.StringIO(openai_jsonl), purpose="search")  #
    # if response["status"] == "uploaded":
    #     file_id = response["id"]
    # print(response)
    # print("NEW FILE ID:", file_id)

    # file_id = "file-Yw6PDpvQd6hBkS5ktuQNZHVh"
    file_id = "file-jxPskhvZ5ConiOencpsoOZwN"
    result = openai.Engine("curie").search(
        file=file_id,
        return_metadata=True,
        max_rerank=100,
        query="can't we securely contain an AI?",
    )
    # print(result)
    questions = result["data"]
    questions.sort(key=(lambda x: x["score"]))
    print(questions)

    exit()


import openai
import discord
from modules.module import Module, Response

from config import CONFUSED_RESPONSE
from config import openai_api_key, rob_id
import json
import re

openai.api_key = openai_api_key


class WikiSemanticSearch(Module):
    def __init__(self):
        super().__init__()
        #         self.re_search = re.compile(
        #             r"""((([Ww]hich|[Ww]hat) vid(eo)? (is|was) (it|that))|
        # ?([Ii]n )?([Ww]hich|[Ww]hat)('?s| is| was| are| were)? ?(it|that|the|they|those)? ?vid(eo)?s? ?(where|in which|which)?|
        # ?[Vv]id(eo)? ?[Ss]earch) (?P<query>.+)"""
        #         )
        self.re_search = re.compile(
            r"""(((is|are) there|do we (already )?have|have we (already )?had|) ((a|any) (canonical )?questions?) ?"""
            r"""((in|on) the wiki )?(like|about)) ?"?(?P<query>.+)"?""",
            re.IGNORECASE,
        )

    def process_message(self, message, client=None):
        text = self.is_at_me(message)
        if not text:
            return Response()

        m = re.match(self.re_search, text)
        if m:
            query = m.group("query")
            return Response(confidence=9, callback=self.process_search_request, args=[query])

    async def process_search_request(self, query):
        print(f'Semantic Searching wiki for questions like: "{query}"')

        file_id = "file-jxPskhvZ5ConiOencpsoOZwN"
        result = openai.Engine("curie").search(
            file=file_id,
            return_metadata=True,
            max_rerank=100,
            query=query,
        )
        # print(result)
        questions = result["data"]
        questions.sort(key=(lambda x: x["score"]))
        # print(questions)

        topresult = questions[-1]

        print("Result:", topresult)
        if topresult.score > 100:
            metadata = json.loads(topresult["metadata"])
            url = metadata["url"]

            message = f"{topresult['text']}\n\n<{url}>"

            return Response(
                confidence=10,
                text=message,
                why=f"The question seemed related, it's score was {topresult.score}",
            )
        else:
            return Response(
                confidence=8,
                text="Not that I can see, sorry",
                why="I couldn't find any similar enough questions",
            )

    def upload_file(self, file_to_upload):
        return openai.File.create(file=open("puppy.jsonl"), purpose="search")

    def __str__(self):
        return "Sentience"
