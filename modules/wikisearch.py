import re
import os
import discord
import json
import textwrap
from modules.module import Module, Response
from config import subs_dir
from api.SemanticSearch.SemanticSearchClient import index, search
from api.SemanticSearch.SemanticSearchUtilities import Timer, safeprint, format_long_text, loop
from api.SemanticSearch.NltkHelpers import escape_urls_for_discord


class WikiSearch(Module):
    """
    A module that searches the wiki questions and/or answers, to find semantically related keywords/phrases
    """

    NOT_FOUND_MESSAGE = "No matches found"

    def __init__(self):
        super().__init__()

        self.re_search = re.compile(
            r"""search\s+wiki[ .,:;\-]+(?P<query>.+)""",
            re.IGNORECASE
        )

        self.response_len_limit = 20000
        self.message_chunk_len_limit = 2000

        # TODO: read from wiki instead and update dynamically when wiki is updated
        # until then you cam use "get_all_wiki_pages_to_json.py" to update "wiki_pairs.json" file.
        with Timer("data reading"):
            filename = r"wiki_pairs.json"
            with open(filename, 'r', 1024 * 1024, encoding='utf-8') as fh:
                question_answers = json.load(fh)


        self.stampy_questions_model_name = "stampy_questions"
        self.stampy_questions_with_answers_model_name = "stampy_questions_with_answers"


        questions = []
        questions_with_answers = []
        self.rows = []

        for source_row_index, question_answer in enumerate(question_answers):

            questions.append(question_answer["question"])

            questions_with_answers.append(question_answer["question"] + ". " + question_answer["answer"])

            # TODO!!! plex 21.07.2021: may be worth bearing in mind that answers can have brief or detailed versions, and you can pull both from the wiki. People interacting with stampy will probably get the brief ones by default, but could request to always get detailed or use a react to get the detailed for a specific case

            id = question_answer["answer_url"]

            self.rows.append({ 
                      "id": id,
                      "index": source_row_index,
                      "question": question_answer["question"],
                      "answer": question_answer["answer"], 
                      "url": question_answer["answer_url"] 
                    })

        #/ for question_answer in question_answers:


        model_name = self.stampy_questions_model_name
        loop.run_until_complete(index(model_name, questions, normalize_vectors = True))

        model_name = self.stampy_questions_with_answers_model_name
        loop.run_until_complete(index(model_name, questions_with_answers, normalize_vectors = True))

        qqq = True  # for debugging

    #/ def __init__(self):


    def process_message(self, message):

        if type(message.channel) == discord.DMChannel:
            if True: # or message.author.id != roland_id:
                safeprint(message.author.id, type(message.author.id))
                return Response()

        query = self.is_at_me(message)
        if query:

            matches = re.match(self.re_search, query)
            if matches:
                query_body = matches.group("query")
                if query_body.strip():
                  return Response(confidence=9, callback=self.process_search_request, args=[query_body.strip(), message.channel])

        # This is either not at me, or not something we can handle
        return Response()

    #/ def process_message(self, message):


    async def process_reaction_event(self, reaction, user, event_type="REACTION_ADD"):
        # TODO
        return Response()

    async def process_raw_reaction_event(self, event, client=None):
        # TODO
        return Response()


    def list_relevant_wiki_pages(self, result_row_indexes, result_distances, result_faiss_scores):

        reply = "Wiki semantic search module here."
        reply += "\nThese results seem relevant:"
        reply += "\n"

        prev_ids = set()
        reply_rows_added = False
        for result_row_index, score, distance in zip(result_row_indexes, result_distances, result_faiss_scores):

            id = self.rows[result_row_index]["id"]
            if id in prev_ids:   # NB! same result may be present in matches multiple times since longer profiles are encoded in multiple pieces
              continue
            prev_ids.add(id)

            question = self.rows[result_row_index]["question"]
            response = self.rows[result_row_index]["answer"]
            response_url = self.rows[result_row_index]["url"]

            safeprint("\n\t(" + str(result_row_index) + ") : " + str(score) + " : " + str(distance))
            # safeprint("\t(" + format_long_text(question, 1, "\t") + ")")
            safeprint("\t" + format_long_text(response, 0, "\t"))


            # new_reply_row = '\n- (%s)\n- %s\n<%s>\n' % (escape_urls_for_discord(question), escape_urls_for_discord(response), response_url)
            new_reply_row = '\n- %s (<%s>)' % (escape_urls_for_discord(question), response_url)
            reply += new_reply_row

            #if len(reply + new_reply_row) <= self.response_len_limit:
            #  reply += new_reply_row
            #  reply_rows_added = True
            #elif not reply_rows_added:
            #  reply = (reply + new_reply_row)[:self.response_len_limit - 3] + "..."
            #  break
            #else:
            #  break

        #/ for result_row_index, score in zip(result_row_indexes, result_faiss_scores):


        if len(reply) > self.response_len_limit:
            reply = reply[:self.response_len_limit - 3] + "..."  # TODO: handle cases where the ellipsis will be put into middle of an escaped link


        return reply

    #/ def list_relevant_wiki_pages(result_row_indexes, result_distances, result_faiss_scores):


    async def process_search_request(self, query, channel):

        safeprint('Wiki Query is:, "%s"' % query)


        model_name = self.stampy_questions_model_name
        (result_row_indexes, result_distances, result_faiss_scores) = await search(model_name, query, randomise_equal_results = True)

        if len(result_row_indexes) > 0:
            
            reply_rows = self.list_relevant_wiki_pages(result_row_indexes, result_distances, result_faiss_scores)
            safeprint("Result: \n" + reply_rows)

            if len(reply_rows) <= self.message_chunk_len_limit:
                return Response(
                    confidence=10,
                    text=reply_rows,
                    why="Those are the wiki entries that seem related!",
                )
            else:
                await self.send_wrapper(reply_rows, channel)
                return Response()

        else:   #/ if len(result_row_indexes) > 0:

            return Response(
                confidence=8, text=self.NOT_FOUND_MESSAGE, why="I couldn't find any relevant wiki entries"
            )

    #/ async def process_search_request(self, query):


    async def send_wrapper(self, text, channel):

        for line in textwrap.wrap(text, self.message_chunk_len_limit, replace_whitespace=False):    # TODO!! do not wrap inside links
            await channel.send(line)

    #/ async def send_wrapper(self, text, channel):
        

    def __str__(self):
        return "Wiki Semantic Search Manager"


    @property
    def test_cases(self):
        return [
            #self.create_integration_test(
            #    question="Which wiki_page did rob play civilization V in?",
            #    expected_regex="Superintelligence Mod for Civilization V+",
            #),
            #self.create_integration_test(
            #    question="which wiki_page is trash?", expected_response=self.NOT_FOUND_MESSAGE,
            #),
        ]
