import openai
import discord
from modules.module import Module, Response
from config import openai_api_key, rob_id
from transformers import GPT2TokenizerFast

import numpy as np
from numpy.linalg import norm
import json

openai.api_key = openai_api_key


class GPT3SemanticSearch(Module):
    def __init__(self):
        super().__init__()

        self.is_active = True
        if not openai_api_key:
            print("GPT3SemanticSearch: No API Key")
            self.is_active = False

        self.engine = "text-similarity-davinci-001"
        self.EMBED_SIZE = 12288  # davinci gives chonky embeddings

        self.load_questions()

    def load_questions(self):
        """Load the question embeddings from disk into memory
        TODO: Replace the JSON file with an SQLite table"""

        try:
            self.questions = json.load(open("questions_with_embeds.json"))
        except FileNotFoundError:
            print(
                "File Not Found: questions_with_embeds.json\n"
                "This file is large so it was left out of the github. "
                "Please download it from: https://www.dropbox.com/s/ku9w4a7si21m4g0/questions_with_embeds.json"
            )
            self.is_active = False
            return

        # build a numpy array for the questions
        self.questions_array = np.zeros((len(self.questions), self.EMBED_SIZE))

        # Normalise questions
        embedding_key = "embed-" + self.engine
        for i in range(len(self.questions)):
            self.questions_array[i] = self.questions[i][embedding_key] / norm(
                self.questions[i][embedding_key]
            )

        # self.questions_array=self.questions_array /(np.sqrt((self.questions_array**2).sum(axis=1))[:, None]+1e-7)

    def search_questions(self, query, top_n=3):
        """Search the questions for `query`
        Return a list of the top_n indices, and their similarity"""

        response = openai.Embedding.create(input=[query], engine=self.engine)
        embedding = response["data"][0]["embedding"]
        embedding /= norm(embedding)

        similarities = self.questions_array @ embedding

        sorted_indices = np.argsort(similarities)

        return (
            sorted_indices[-1 : (-(top_n + 1)) : -1],
            similarities[sorted_indices[-1 : (-(top_n + 1)) : -1]],
        )

    def semantic_search_questions(self, query):
        """Run the search through questions, and reply

        TODO: Figure out how to interpret similarities
        - What threshold of bad match to not even respond?
        - What threshold of good response to just give with the answer instead of 'did you mean'?
        - Set the Repsonse `confidence` based on similarity?
        TODO: Pull the full answers from wiki API?"""
        top_n = 3
        indices, similarities = self.search_questions(query, top_n)

        responsetext = """Did you mean:"""
        for i in range(top_n):
            question = self.questions[indices[i]]
            responsetext += f"\n- [{question['title']}](http://stampy.ai/{question['url']}) ({similarities[i]})"  # this link syntax doesn't work. Embeds?

        return Response(confidence=9, text=responsetext, why="Someone already asked a similar question")

    def process_message(self, message):
        if not self.is_active:
            return Response()

        text = self.is_at_me(message)
        if not text:
            return Response()

        if text.endswith("?"):
            return Response(confidence=3, callback=self.semantic_search_questions, args=[text], kwargs={}, why="Maybe someone already asked a question like this one")

        return Response()

    async def tick(self):
        """TODO: Use this to, from time to time, pull down the questions from the API and update
        any embeddings that need updating"""
        pass

    def __str__(self):
        return "GPT3 Semantic Search Module"
