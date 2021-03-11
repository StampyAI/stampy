import requests
import json


###########################################################################
#   Question Persistence API Interface for future-proofing
###########################################################################
class QuestionPersistenceInterface(Object):

    baseUri
    session
    token
    token_exp

    def login(self):
        pass

    def add_question(self, content):
        pass

    def edit_question(self, content):
        pass

    def get_latest_question(self):
        pass

    def get_random_question(self):
        pass

    def set_question_asked(self):
        pass

    def set_question_replied(self):
        pass

    def get_question_count(self):
        pass


###########################################################################
#   Lightweight wrapper to the Semantic wiki API calls we need to store questions/answers there
###########################################################################


class SemanticWiki(QuestionPersistenceInterface):

    uri = "https://stampy.ai/wiki/api.php"
    session = None
    token = None

    def __init__(self):
        QuestionPersistenceInterface.__init__(self)
        return

    def login(self):

        # TODO: I don't think this will auto-renew the token if it expires. There is probably an expiration date/time in one of these responses that we can check for?

        self.session = requests.Session()

        # Retrieve login token first
        body = {"action": "query", "meta": "tokens", "type": "login", "format": "json"}

        data = self.session.get(url=self.uri, params=body)
        json = data.json()

        token = json["query"]["tokens"]["logintoken"]

        # Now log in to the Stampy bot account with the provided login token
        body = {
            "action": "login",
            "lgname": "Stampy",
            "lgpassword": "stampy@0uhl1a7pm3fqkk3r4le7abrhi74f9u7q",
            "lgtoken": token,
            "format": "json",
        }

        data = self.session.post(self.uri, data=body)

        # this basically gets our specific csrf token, which is what we actually need to make requests as this user in the future
        body = {"action": "query", "meta": "tokens", "format": "json"}

        data = self.session.get(url=self.uri, params=body)
        json = data.json()

        # store this token locally
        self.token = json["query"]["tokens"]["csrftoken"]
        return

    def add(self, content):
        return

    def edit(self):

        # available fields can be found here: https://www.mediawiki.org/wiki/API:Edit
        body = {
            "action": "edit",
            "title": "Project:Sandbox",
            "token": self.token,
            "format": "json",
            "appendtext": "Hello, World!",
        }

        data = self.session.post(self.uri, data=body)
        json = data.json()

        return
