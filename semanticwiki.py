import requests
import datetime
import json
from utilities import utils


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

    def add_question(self, url, username, text):
        raise NotImplementedError

    def add_answer(self, url, users, text, reply_date):
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
        return response

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

    def add_answer(self, url, users, text, reply_date):
        # Split the url into the comment id and video url
        url_arr = url.split("&lc=")
        video_url = url_arr[0]
        reply_id = url_arr[-1].split(".")[0]

        # we need the short title from our table, so get the full title there too
        titles = utils.get_title(video_url)

        if titles is None:
            return

        short_title = titles[0]
        #full_title = titles[1]

        # TODO: Pass these in ass parameters instead of getting it directly from YT here
        request = utils.youtube.commentThreads().list(part="snippet", id=reply_id)
        response = request.execute()
        items = response.get("items")
        timestamp = None
        username = None
        if items:
            timestamp = items[0]["snippet"]["topLevelComment"]["snippet"]["publishedAt"]
            asker = items[0]["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"]
        pub_timestamp = datetime.datetime.fromisoformat(timestamp[:-1])
        # Full question params
        """
        {{Answer
        |answer=
        |tags=
        |canonicalquestion=
        |answerto=
        |canonical=
        |nonaisafety=
        |unstamped=
        |writtenby=
        |date=
        }}
        """
        title = "{0}'s Answer to {1} on {2} by {3}".format(users[0], short_title, pub_timestamp, asker)
        question = "{0} on {1} by {2}".format(short_title, pub_timestamp, asker)

        # there has to be a better way...
        ftext = """Answer|
                answer={0}|
                answerto={1}|
                canonical=No|
                nonaisafety=No|
                unstamped=No|
                writtenby={2}|
                date={3}|
                stamps={4}"""
        ftext = "{{" + ftext.replace(" ", "").format(text, question, users[0], reply_date, ", ".join(users)) + "}}"

        # Post the question to wiki
        print("Trying to add reply " + text)
        self.edit(title, ftext)
        return

    def add_question(self, url, username, text, asked=False):

        # Split the url into the comment id and video url
        url_arr = url.split("&lc=")
        video_url = url_arr[0]
        reply_id = url_arr[-1]

        # we need the short title from our table, so get the full title there too
        titles = utils.get_title(video_url)
        short_title = titles[0]
        full_title = titles[1]

        # TODO: Pass these in ass parameters instead of getting it directly from YT here
        request = utils.youtube.commentThreads().list(part="snippet", id=reply_id)
        response = request.execute()
        items = response.get("items")
        timestamp = None
        likes = None
        if items:
            timestamp = items[0]["snippet"]["topLevelComment"]["snippet"]["publishedAt"]
            likes = items[0]["snippet"]["topLevelComment"]["snippet"]["likeCount"]
            published_timestamp = timestamp[:-1]
        else:
            published_timestamp = datetime.datetime.isoformat(datetime.datetime.utcnow())
            likes = 0
        # Full question params
        """
        {{Question|
        |question=
        |tags=
        |canonical=
        |forrob=
        |notquestion=
        |asked=
        |asker=
        |date=
        |video=
        |canonicalversion=
        |followupto=
        |commenturl=
        |ytlikes=
        }}
        """
        title = "{0} on {1} by {2}".format(short_title, published_timestamp, username)

        asked = "Yes" if asked else "No"

        # there has to be a better way...
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
        ftext = "{{" + ftext.replace(" ", "").format(text, asked, username, published_timestamp, full_title, likes, url) + "}}"

        # Post the question to wiki
        self.edit(title, ftext)
        return

    def edit_question(self, content):
        pass
        # I think this is probably fine, but maybe it is slightly different?
        #self.add_question(self, url, username, text)

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
