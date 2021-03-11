import abc
import requests
import json


###########################################################################
#   Question Persistence API Interface for future-proofing
###########################################################################
class QuestionPersistenceInterface(object):
    __metaclass__ = abc.ABCMeta

    def __init__(self):
        self._base_uri = None
        self._session = None
        self._token = None
        self._token_expiration = None

    @property
    def base_uri(self):
        return self._base_uri

    @base_uri.setter
    def base_uri(self, uri):
        self._base_uri = uri

    @property
    def session(self):
        return self._session

    @session.setter
    def session(self, session):
        self._session = session

    @property
    def token(self):
        return self._token

    @token.setter
    def token(self, token):
        self._token = token

    @property
    def token_expiration(self):
        return self._token_expiration

    @token_expiration.setter
    def token_expiration(self, expiration):
        self._token_expiration = expiration

    @abc.abstractmethod
    def login(self):
        pass

    @abc.abstractmethod
    def add_question(self, url, username, title, text):
        pass

    @abc.abstractmethod
    def edit_question(self, content):
        pass

    @abc.abstractmethod
    def get_latest_question(self):
        pass

    @abc.abstractmethod
    def get_random_question(self):
        pass

    @abc.abstractmethod
    def set_question_asked(self):
        pass

    @abc.abstractmethod
    def set_question_replied(self):
        pass

    @abc.abstractmethod
    def get_question_count(self):
        pass


###########################################################################
#   Lightweight wrapper to the Semantic wiki API calls we need to store questions/answers there
###########################################################################


class SemanticWiki(QuestionPersistenceInterface):
    def __init__(self):
        QuestionPersistenceInterface.__init__(self)
        self.base_uri = "https://stampy.ai/w/api.php"
        return

    def login(self):
        # TODO: Auto-renew token

        self.session = requests.Session()

        # Retrieve login token first
        body = {"action": "query", "meta": "tokens", "type": "login", "format": "json"}
        data = self.session.get(url=self.base_uri, params=body)
        response = data.json()

        # Now log in to the Stampy bot account with the provided login token
        body = {
            "action": "login",
            "lgname": "Stampy@stampy",
            "lgpassword": "n1navvcr4l670jd9q1b4f8649kudoq9s",
            "lgtoken": response["query"]["tokens"]["logintoken"],
            "format": "json",
        }

        data = self.session.post(self.base_uri, data=body)
        response = data.json()

        # this gets our actual csrf token, now that we are logged in
        body = {"action": "query", "meta": "tokens", "format": "json"}

        data = self.session.get(url=self.base_uri, params=body)
        response = data.json()

        # store this token
        self.token = response["query"]["tokens"]["csrftoken"]

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
        data = self.session.post(self.base_uri, data=body)
        response = data.json()
        print(response)

    def edit(self, title, formatted_text):
        # available fields can be found here: https://www.mediawiki.org/wiki/API:Edit

        body = {
            "action": "edit",
            "title": title,
            "token": self.token,
            "format": "json",
            "text": formatted_text,
        }
        data = self.session.post(self.base_uri, data=body)
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
