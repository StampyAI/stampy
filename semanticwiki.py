import requests
import json

###########################################################################
#   Question Persistence API Interface for future-proofing
###########################################################################


class QuestionPersistence(object):

    def __init__(self, uri, user, api_key):
        self._uri = uri
        self._user = user
        self._api_key = api_key
        self._session = None
        self._token = None
        self._token_expiration = None

    def login(self):
        raise NotImplementedError

    def add_question(self, url, username, title, text):
        raise NotImplementedError

    def edit_question(self, content):
        raise NotImplementedError

    def get_latest_question(self):
        raise NotImplementedError

    def get_random_question(self):
        raise NotImplementedError

    def set_question_asked(self):
        raise NotImplementedError

    def set_question_replied(self):
        raise NotImplementedError

    def get_question_count(self):
        raise NotImplementedError


###########################################################################
#   Lightweight wrapper to the Semantic wiki API calls we need to store questions/answers there
###########################################################################


class SemanticWiki(QuestionPersistence):
    def __init__(self, uri, user, api_key):
        QuestionPersistence.__init__(self, uri, user, api_key)
        return

    def login(self):
        # TODO: Auto-renew token

        self._session = requests.Session()

        # Retrieve login token first
        body = {"action": "query", "meta": "tokens", "type": "login", "format": "json"}
        data = self._session.get(url=self._uri, params=body)
        response = data.json()

        # Now log in to the Stampy bot account with the provided login token
        body = {
            "action": "login",
            "lgname": self._user,
            "lgpassword": self._api_key,
            "lgtoken": response["query"]["tokens"]["logintoken"],
            "format": "json",
        }

        data = self._session.post(self._uri, data=body)
        response = data.json()

        # this gets our actual csrf token, now that we are logged in
        body = {"action": "query", "meta": "tokens", "format": "json"}

        data = self._session.get(url=self._uri, params=body)
        response = data.json()

        # store this token
        self._token = response["query"]["tokens"]["csrftoken"]

        return

    def add(self, content):
        return

    def get_page(self, title):
        body = {
            "action": "query",
            "prop": "revisions",
            "titles": title,
            "rvprop": "timestamp|content",
            "rvslots": "main",
            "formatversion": "2",
            "format": "json",
        }
        data = self._session.post(self._uri, data=body)
        response = data.json()
        print(response)

    def edit(self, title, formatted_text):
        # available fields can be found here: https://www.mediawiki.org/wiki/API:Edit

        body = {
            "action": "edit",
            "title": title,
            "token": self._token,
            "format": "json",
            "text": formatted_text,
        }
        data = self._session.post(self._uri, data=body)
        response = data.json()
        return

    def add_question(self, url, username, title, text):
        title = "Maximizers and Satisficers on 10/03/2021 by Sudonym"
        formatted_text = (
            "{{Question|question=Testing this via the API|notquestion=Yes|asked=Yes|asker=Sudonym"
            + "|date=2021-03-10T21:47:22.000Z|video=Quantilizers: AI That Doesn't Try Too Hard"
            + "|canonicalversion=Test question2|followupto=test answer|stamps=plex, Sudonym|ytlikes=1}}"
        )
        self.edit(title, formatted_text)
        return

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
