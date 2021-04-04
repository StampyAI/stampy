import requests
import datetime
import json
from utilities import utils
from persistence import Persistence


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

        print("Logged in to Wiki!")
        print(response)

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
        data = self._session.post(self._uri, data=body)
        response = data.json()
        return response

    def ask(self, query):
        body = {
            "action": "ask",
            "format": "json",
            "query": query,
            "api_version": "2"
        }
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
        data = self._session.post(self._uri, data=body)
        response = data.json()
        return response

    def add_answer(self, url, users, text, reply_date):
        # add a answer, we need to figure out which question this is an answer to TODO: pass in question?

        # Split the url into the comment id and video url, this is hacky
        url_arr = url.split("&lc=")
        video_url = url_arr[0]
        reply_id = url_arr[-1].split(".")[0]

        # we need the short title from our table, so get the full title there too
        titles = utils.get_title(video_url)

        if titles is None:
            print("No title for video " + video_url)
            return  # We dont have a title for this video

        short_title = titles[0]
        #full_title = titles[1] # don't need this for answers

        # TODO: Pass these in as parameters instead of getting it directly from YT here
        # This code is repeated but it will all go away one this YT stuff is moved
        request = utils.youtube.commentThreads().list(part="snippet", id=reply_id)
        response = request.execute()
        items = response.get("items")
        if items:
            timestamp = items[0]["snippet"]["topLevelComment"]["snippet"]["publishedAt"][:-1]
            asker = items[0]["snippet"]["topLevelComment"]["snippet"]["authorDisplayName"]
        else:  # This happens if the comment was deleted from YT
            timestamp = datetime.datetime.isoformat(datetime.datetime.utcnow())
            asker = "Unknown"

        title = "{0}'s Answer to {1} on {2} by {3}".format(users[0], short_title, timestamp, asker)
        question = "{0} on {1} by {2}".format(short_title, timestamp, asker) # must match the q title

        # there has to be a better way to get this to fit on one line..
        # TODO: Should we create a struct of some kind of these? Or an object that creates the string?
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

        # Post the answer to wiki
        print("Trying to add reply " + text + " to wiki")
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

        # TODO: Pass these in as parameters instead of getting it directly from YT here
        request = utils.youtube.commentThreads().list(part="snippet", id=reply_id)
        response = request.execute()
        items = response.get("items")
        timestamp = None
        likes = None

        if items:
            timestamp = items[0]["snippet"]["topLevelComment"]["snippet"]["publishedAt"]
            likes = items[0]["snippet"]["topLevelComment"]["snippet"]["likeCount"]
            published_timestamp = timestamp[:-1]
        else: # This happens if the comment was deleted from YT
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
        ftext = "{{" + ftext.replace(" ", "").format(text, asked, username,
                                                     published_timestamp, full_title, likes, url) + "}}"

        # Post the question to wiki
        print("Trying to add question " + title + " to wiki")
        self.edit(title, ftext)
        return

    def edit_question(self,  url, username, text):
        # I think this is probably fine, but maybe it is slightly different? Could check to see if it exists?
        self.add_question(url, username, text)
        return

    def get_latest_question(self):
        # TODO: For Augustus
        pass

    def get_random_question(self):
        # TODO: For Augustus
        pass

    def set_question_asked(self, title):
        page = self.get_page(title)
        # TODO: update the 'asked' attribute but post back the same page otherwise
        pass

    def get_question_count(self):
        # TODO: For Augustus
        pass


