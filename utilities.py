import os
import discord
from dotenv import load_dotenv
from database.database import Database
from datetime import datetime, timezone, timedelta
from googleapiclient.errors import HttpError
from googleapiclient.discovery import build as get_youtube_api
from config import (
    required_environment_variables,
    youtube_api_version,
    youtube_api_service_name,
    rob_miles_youtube_channel_id,
    discord_token,
    discord_guild,
    youtube_api_key,
    database_path,
)


def check_environment(environment_variables):
    for env in environment_variables:
        if env not in os.environ:
            raise Exception("%s Environment Variable not set" % env)


class Utilities:
    __instance = None
    db = None
    discord = None
    client = None

    TOKEN = None
    GUILD = None
    YOUTUBE_API_KEY = None
    DB_PATH = None

    last_message_was_youtube_question = None
    latest_comment_timestamp = None
    last_check_timestamp = None
    youtube_cooldown = None
    last_timestamp = None
    last_question_asked_timestamp = None
    latest_question_posted = None

    users = None
    ids = None
    index = None
    scores = None

    modules_dict = {}

    @staticmethod
    def get_instance():
        if Utilities.__instance is None:
            check_environment(required_environment_variables)
            Utilities()
        return Utilities.__instance

    def __init__(self):
        if Utilities.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            Utilities.__instance = self
            self.TOKEN = discord_token
            self.GUILD = discord_guild
            self.YOUTUBE_API_KEY = youtube_api_key
            self.DB_PATH = database_path

            try:
                self.youtube = get_youtube_api(
                    youtube_api_service_name, youtube_api_version, developerKey=self.YOUTUBE_API_KEY,
                )
            except HttpError as e:
                if self.YOUTUBE_API_KEY:
                    print("YouTube API Key is set but not correct")
                else:
                    print("YouTube API Key is not set")
                print(e)

            print("Trying to open db - " + self.DB_PATH)
            self.db = Database(self.DB_PATH)

    def check_for_new_youtube_comments(self):
        """Consider getting the latest comments from the channel
        Returns a list of dicts if there are new comments
        Returns [] if it checked and there are no new ones
        Returns None if it didn't check because it's too soon to check again"""

        now = datetime.now(timezone.utc)

        if (now - self.last_check_timestamp) > self.youtube_cooldown:
            print("Hitting YT API")
            self.last_check_timestamp = now
        else:

            print(
                "YT waiting >%s\t- " % str(self.youtube_cooldown - (now - self.last_check_timestamp)), end="",
            )
            return None

        request = self.youtube.commentThreads().list(
            part="snippet", allThreadsRelatedToChannelId=rob_miles_youtube_channel_id
        )
        response = request.execute()

        items = response.get("items", None)
        if not items:
            # something broke, slow way down
            print("YT comment checking broke. I got this response:")
            print(response)
            self.youtube_cooldown = self.youtube_cooldown * 10
            return None

        newest_timestamp = self.latest_comment_timestamp

        new_items = []
        for item in items:
            # Find when the comment was published
            timestamp = item["snippet"]["topLevelComment"]["snippet"]["publishedAt"]
            # For some reason fromisoformat() doesn't like the trailing 'Z' on timestmaps
            # And we add the "+00:00" so it knows to use UTC
            published_timestamp = datetime.fromisoformat(timestamp[:-1] + "+00:00")

            # If this comment is newer than the newest one from last time we called API, keep it
            if published_timestamp > self.latest_comment_timestamp:
                new_items.append(item)

            # Keep track of which is the newest in this API call
            if published_timestamp > newest_timestamp:
                newest_timestamp = published_timestamp

        print("Got %s items, most recent published at %s" % (len(items), newest_timestamp))

        # save the timestamp of the newest comment we found, so next API call knows what's fresh
        self.latest_comment_timestamp = newest_timestamp

        new_comments = []
        for item in new_items:
            top_level_comment = item["snippet"]["topLevelComment"]
            video_id = top_level_comment["snippet"]["videoId"]
            comment_id = top_level_comment["id"]
            username = top_level_comment["snippet"]["authorDisplayName"]
            text = top_level_comment["snippet"]["textOriginal"]
            comment = {
                "url": "https://www.youtube.com/watch?v=%s&lc=%s" % (video_id, comment_id),
                "username": username,
                "text": text,
                "title": "",
            }

            new_comments.append(comment)

        print("Got %d new comments since last check" % len(new_comments))

        if not new_comments:
            # we got nothing, double the cooldown period (but not more than 20 minutes)
            self.youtube_cooldown = min(self.youtube_cooldown * 2, timedelta(seconds=1200))
            print("No new comments, increasing cooldown timer to %s" % self.youtube_cooldown)

        return new_comments

    def get_latest_question(self):
        """Pull the oldest question from the queue
        Returns False if the queue is empty, the question string otherwise"""

        comment = self.get_next_question("text,username,title,url")

        comment_dict = {
            "text": comment[0],
            "username": comment[1],
            "title": comment[2],
            "url": comment[3],
        }
        self.latest_question_posted = comment_dict

        text = comment[0]
        if len(text) > 1500:
            text = text[:1500] + " [truncated]"
        text_quoted = "> " + "\n> ".join(text.split("\n"))

        title = comment[2]
        if title:
            report = (
                "YouTube user {0} asked this question, on the video {1}!:\n"
                + "{2}\n"
                + "Is it an interesting question? Maybe we can answer it!\n"
                + "{3}"
            ).format(comment[1], comment[2], text_quoted, comment[3])

        else:
            report = (
                "YouTube user {0} just asked a question!:\n"
                + "{2}\n"
                + "Is it an interesting question? Maybe we can answer it!\n"
                + "{3}"
            ).format(comment[1], comment[2], text_quoted, comment[3])

        print("==========================")
        print(report)
        print("==========================")

        # reset the question waiting timer
        self.last_question_asked_timestamp = datetime.now(timezone.utc)

        # mark it in the database as having been asked
        self.set_question_asked(comment_dict["url"])

        return report

    def get_question_count(self):
        query = "SELECT COUNT(*) FROM questions WHERE asked==0"
        return self.db.query(query)[0][0]

    def clear_votes(self):
        query = "DELETE FROM uservotes"
        self.db.query(query)
        self.db.commit()

    def update_ids_list(self):

        self.ids = sorted(list(self.users))
        self.index = {0: 0}
        for userid in self.ids:
            self.index[userid] = self.ids.index(userid)

    def index_dammit(self, user):
        """Get an index into the scores array from whatever you get"""

        if user in self.index:
            # maybe we got given a valid ID?
            return self.index[user]
        elif str(user) in self.index:
            return self.index[str(user)]

        # maybe we got given a User or Member object that has an ID?
        uid = getattr(user, "id", None)
        print(uid)
        print(self.index)
        if uid:
            return self.index_dammit(uid)

        return None

    def get_user_score(self, user):
        index = self.index_dammit(user)
        if index:
            return self.scores[index]
        else:
            return 0.0

    def update_vote(self, user, voted_for, vote_quantity):
        query = (
            "INSERT OR REPLACE INTO uservotes VALUES ({0},{1},IFNULL((SELECT votecount "
            "FROM uservotes WHERE user = {0} AND votedFor = {1}),0)+{2})".format(
                user, voted_for, vote_quantity
            )
        )
        self.db.query(query)
        self.db.commit()

    def get_votes_by_user(self, user):
        query = "SELECT IFNULL(sum(votecount),0) FROM uservotes where user = {0}".format(user)
        return self.db.query(query)[0][0]

    def get_votes_for_user(self, user):
        query = "SELECT IFNULL(sum(votecount),0) FROM uservotes where votedFor = {0}".format(user)
        return self.db.query(query)[0][0]

    def get_total_votes(self):
        query = "SELECT sum(votecount) from uservotes where user is not 0"
        return self.db.query(query)[0][0]

    def get_all_user_votes(self):
        return self.db.get("uservotes", "user,votedFor,votecount")

    def get_users(self):
        query = "SELECT user from (SELECT user FROM uservotes UNION SELECT votedFor as user FROM uservotes)"
        result = self.db.query(query)
        users = [item for sublist in result for item in sublist]
        return users

    def add_question(self, url, username, title, text):
        self.db.query(
            "INSERT INTO questions VALUES (?,?,?,?,?,?)", (url, username, title, text, False, False),
        )
        self.db.commit()

    def get_next_question(self, columns="*"):
        return self.db.get_last("questions WHERE replied=False AND asked=False ORDER BY rowid DESC", columns)

    # TODO: see above
    def get_random_question(self, columns="*"):
        return self.db.get_last("questions WHERE replied=False AND asked=False ORDER BY RANDOM()", columns)

    def set_question_replied(self, url):
        self.db.query('UPDATE questions SET replied = True WHERE url="{0}"'.format(url))
        self.db.commit()
        return True

    def set_question_asked(self, url):
        self.db.query('UPDATE questions SET asked = True WHERE url="{0}"'.format(url))
        self.db.commit()
        return True


load_dotenv()

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

utils = Utilities.get_instance()
utils.client = client
