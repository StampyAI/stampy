import requests
import datetime
from api.persistence import Persistence


###########################################################################
#   Lightweight wrapper to the Semantic wiki API calls we need to store questions/answers there
###########################################################################
class SemanticWiki(Persistence):
    def __init__(self, uri, user, api_key):
        Persistence.__init__(self, uri, user, api_key)
        # Should we just log in on init? Or separate it out?
        # TODO: Auto-renew token
        self._session = requests.Session()

        # Retrieve login token first
        response = self.post({"action": "query", "meta": "tokens", "type": "login", "format": "json"})

        # Now log in to the Stampy bot account with the provided login token
        body = {
            "action": "login",
            "lgname": self._user,
            "lgpassword": self._api_key,
            "lgtoken": response["query"]["tokens"]["logintoken"],
            "format": "json",
        }
        self.post(body)

        response = self.post({"action": "query", "meta": "tokens", "format": "json"})
        self._token = response["query"]["tokens"]["csrftoken"]  # store this token

        print("Logged in to Wiki!")
        return

    def get_page(self, title):
        # Gets a page by the title (the unique id)
        body = {
            "action": "query",
            "prop": "revisions",
            "titles": title,
            "rvprop": "timestamp|content",
            "rvslots": "main",
            "formatversion": "2",
            "format": "json",
        }
        return self.post(body)

    def ask(self, query):
        body = {"action": "ask", "format": "json", "query": query, "api_version": "2"}
        return self.post(body)

    def post(self, body):
        data = self._session.post(self._uri, data=body)
        response = data.json()
        return response

    def edit(self, title, content):
        # available fields can be found here: https://www.mediawiki.org/wiki/API:Edit
        # This edits the page of the given title with the new content
        body = {
            "action": "edit",
            "title": title,
            "token": self._token,
            "format": "json",
            "text": content,
        }
        return self.post(body)

    def add_answer(self, url, users, text, question_title, reply_date):
        # add a answer, we need to figure out which question this is an answer to

        # there has to be a better way to get this to fit on one line..
        # Should we create a struct of some kind of these? Or an object that creates the string?
        title = "{0}'s Answer to {1}".format(users[0], question_title)

        ftext = """Answer|
                answer={0}|
                answerto={1}|
                canonical=No|
                nonaisafety=No|
                unstamped=No|
                writtenby={2}|
                date={3}|
                stamps={4}"""

        ftext = (
            "{{"
            + ftext.replace(" ", "").format(text, question_title, users[0], reply_date, ", ".join(users))
            + "}}"
        )

        # Post the answer to wiki
        print("Trying to add reply " + text + " to wiki")
        self.edit(title, ftext)
        return

    def add_question(self, url, full_title, short_title, asker, asked_time, text, likes=0, asked=False):

        # Split the url into the comment id and video url
        title = "{0} on {1} by {2}".format(short_title, asked_time, asker)
        asked = "Yes" if asked else "No"

        # there has to be a better way to make this fit on a line..
        ftext = """Question|
                question={0}|
                notquestion=No|
                canonical=No|
                forrob=No|
                asked={1}|
                asker={2}|
                date={3}|
                video={4}|
                ytlikes={5}|
                commenturl={6}"""
        ftext = (
            "{{"
            + ftext.replace(" ", "").format(text, asked, asker, asked_time, full_title, likes, url)
            + "}}"
        )

        # Post the question to wiki
        print("Trying to add question " + title + " to wiki")
        self.edit(title, ftext)
        return

    def edit_question(self, url, username, text):
        # I think this is probably fine, but maybe it is slightly different? Could check to see if it exists?
        self.add_question(url, username, text)
        return

    def get_unasked_question(self, sort, order):
        query = (
            "[[Category:Unanswered questions]]|[[AskedOnDiscord::f]]|?Question|?asker|?AskDate|?CommentURL|"
            + "?AskedOnDiscord|?video|sort={0}|limit=1|order={1}".format(sort, order)
        )
        response = self.ask(query)

        # url, username, title, text, replies, asked = None, None, None, None, None, None
        question = {}
        if "query" in response:
            question["question_title"] = list(response["query"]["results"].keys())[0]
            relevant_vals = list(response["query"]["results"].values())[0]["printouts"]

            if relevant_vals["CommentURL"]:
                question["url"] = relevant_vals["CommentURL"][0]
            if relevant_vals["Asker"]:
                question["username"] = relevant_vals["Asker"][0]["fulltext"][5:]
            if relevant_vals["Video"]:
                question["title"] = relevant_vals["Video"][0]["fulltext"]
            if relevant_vals["Question"]:
                question["text"] = relevant_vals["Question"][0]
            if relevant_vals["AskedOnDiscord"]:
                question["asked"] = relevant_vals["AskedOnDiscord"][0] == "t"

        return question

    def get_latest_question(self):
        return self.get_unasked_question("AskDate", "desc")

    def get_random_question(self):
        return self.get_unasked_question("AskDate", "rand")

    def get_top_question(self):
        return self.get_unasked_question("Reviewed,YouTubeLikes", "desc,desc")

    def set_question_property(self, title, parameter, value):
        body = {
            "action": "pfautoedit",
            "form": "Question",
            "target": title,
            "format": "json",
            "query": "Question[{0}]={1}".format(parameter, value),
        }
        return self.post(body)

    def set_question_asked(self, title):
        return self.set_question_property(title, "asked", "Yes")

    def get_question_count(self):
        query = "[[Meta:API Queries]]|?UnaskedQuestions"
        response = self.ask(query)

        return response["query"]["results"]["Meta:API Queries"]["printouts"]["UnaskedQuestions"][0]
