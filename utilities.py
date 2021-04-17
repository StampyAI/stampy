import os
import discord
from dotenv import load_dotenv
from database.database import Database
from api.semanticwiki import SemanticWiki
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
    wiki_config,
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
            self.youtube = None

            try:
                self.youtube = get_youtube_api(
                    youtube_api_service_name,
                    youtube_api_version,
                    developerKey=self.YOUTUBE_API_KEY,
                )
            except HttpError:
                if self.YOUTUBE_API_KEY:
                    print("YouTube API Key is set but not correct")
                else:
                    print("YouTube API Key is not set")

            print("Trying to open db - " + self.DB_PATH)
            self.db = Database(self.DB_PATH)
            self.wiki = SemanticWiki(
                wiki_config["uri"], wiki_config["user"], wiki_config["password"]
            )

    def get_youtube_comment_replies(self, comment_url):
        url_arr = comment_url.split("&lc=")
        reply_id = url_arr[-1].split(".")[0]
        request = self.youtube.comments().list(part="snippet", parentId=reply_id)
        response = request.execute()
        items = response.get("items")
        reply = {}
        for item in items:
            reply_id = item["id"]
            username = item["snippet"]["authorDisplayName"]
            text = item["snippet"]["textOriginal"]
            timestamp = item["snippet"]["publishedAt"][:-1]
            likes = item["snippet"]["likeCount"]
            reply = {
                "username": username,
                "text": text,
                "title": "",
                "timestamp": timestamp,
                "likes": likes,
            }

    def get_youtube_comment(self, comment_url):
        url_arr = comment_url.split("&lc=")
        video_url = url_arr[0]
        reply_id = url_arr[-1].split(".")[0]
        request = self.youtube.commentThreads().list(part="snippet", id=reply_id)
        response = request.execute()
        items = response.get("items")
        comment = {}
        if items:
            top_level_comment = items[0]["snippet"]["topLevelComment"]
            comment["timestamp"] = top_level_comment["snippet"]["publishedAt"][:-1]
            comment["comment_id"] = top_level_comment["id"]
            comment["username"] = top_level_comment["snippet"]["authorDisplayName"]
            comment["likes"] = top_level_comment["snippet"]["likeCount"]
            comment["text"] = top_level_comment["snippet"]["textOriginal"]
            comment["reply_count"] = items[0]["snippet"]["totalReplyCount"]
        else:  # This happens if the comment was deleted from YT
            comment["timestamp"] = datetime.isoformat(datetime.utcnow())
            comment["comment_id"] = reply_id
            comment["username"] = "Unknown"
            comment["likes"] = 0
            comment["text"] = ""
            comment["reply_count"] = 0
        return comment

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
                "YT waiting >%s\t- "
                % str(self.youtube_cooldown - (now - self.last_check_timestamp)),
                end="",
            )
            return None

        if self.youtube is None:
            print("WARNING: YouTube API Key is invalid or not set")
            self.youtube_cooldown = self.youtube_cooldown * 10
            return []

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

        print(
            "Got %s items, most recent published at %s" % (len(items), newest_timestamp)
        )

        # save the timestamp of the newest comment we found, so next API call knows what's fresh
        self.latest_comment_timestamp = newest_timestamp

        new_comments = []
        for item in new_items:
            top_level_comment = item["snippet"]["topLevelComment"]
            video_id = top_level_comment["snippet"]["videoId"]
            comment_id = top_level_comment["id"]
            username = top_level_comment["snippet"]["authorDisplayName"]
            text = top_level_comment["snippet"]["textOriginal"]
            timestamp = top_level_comment["snippet"]["publishedAt"][:-1]
            likes = top_level_comment["snippet"]["likeCount"]
            reply_count = item["snippet"]["totalReplyCount"]
            comment = {
                "url": "https://www.youtube.com/watch?v=%s&lc=%s"
                % (video_id, comment_id),
                "username": username,
                "text": text,
                "title": "",
                "timestamp": timestamp,
                "likes": likes,
                "reply_count": reply_count,
            }

            new_comments.append(comment)

        print("Got %d new comments since last check" % len(new_comments))

        if not new_comments:
            # we got nothing, double the cooldown period (but not more than 20 minutes)
            self.youtube_cooldown = min(
                self.youtube_cooldown * 2, timedelta(seconds=1200)
            )
            print(
                "No new comments, increasing cooldown timer to %s"
                % self.youtube_cooldown
            )

        return new_comments

    def get_latest_question(self, order_type="LATEST"):
        """Pull the oldest question from the queue
        Returns False if the queue is empty, the question string otherwise"""
        # TODO: I dont know that "latest" makes sense, but this is maybe used in a lot of places
        # So wanted to keep it consistent for now. Maybe get _a_ question?
        comment = None
        if order_type == "RANDOM":
            comment = self.wiki.get_random_question()
        elif order_type == "TOP":
            comment = self.wiki.get_top_question()
        else:
            comment = self.wiki.get_latest_question()

        if not comment:
            return None

        self.latest_question_posted = comment

        text = comment["text"]
        if len(text) > 1500:
            text = text[:1500] + " [truncated]"
        text_quoted = "> " + "\n> ".join(text.split("\n"))

        if "title" in comment:
            report = (
                "YouTube user {0} asked this question, on the video {1}!:\n"
                + "{2}\n"
                + "Is it an interesting question? Maybe we can answer it!\n"
                + "{3}"
            ).format(comment["username"], comment["title"], text_quoted, comment["url"])

        else:
            # TODO: What about questions that aren't from videos?
            report = (
                "YouTube user {0} asked this question, on the video {1}!:\n"
                + "{2}\n"
                + "Is it an interesting question? Maybe we can answer it!\n"
                + "{3}"
            ).format(
                comment["username"],
                self.get_title(comment["url"])[1],
                text_quoted,
                comment["url"],
            )

        print("==========================")
        print(report)
        print("==========================")

        # reset the question waiting timer
        self.last_question_asked_timestamp = datetime.now(timezone.utc)

        # mark it in the database as having been asked
        self.wiki.set_question_asked(comment["question_title"])

        return report

    def get_question_count(self):
        return self.wiki.get_question_count()

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
        query = (
            "SELECT IFNULL(sum(votecount),0) FROM uservotes where user = {0}".format(
                user
            )
        )
        return self.db.query(query)[0][0]

    def get_votes_for_user(self, user):
        query = "SELECT IFNULL(sum(votecount),0) FROM uservotes where votedFor = {0}".format(
            user
        )
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

    def add_youtube_question(self, comment):
        # Get the video title from the video URL, without the comment id
        # TODO: do we need to actually parse the URL param properly? Order is hard-coded from get yt comment
        video_titles = self.get_title(comment["url"].split("&lc=")[0])

        if not video_titles:
            # this should actually only happen in dev
            titles = ["Video Title Unknown", "Video Title Unknown"]

        question_title = "{0} on {1} by {2}".format(
            video_titles[0], comment["timestamp"], comment["username"]
        )

        return self.wiki.add_question(
            question_title,
            comment["username"],
            comment["timestamp"],
            comment["text"],
            comment_url=comment["url"],
            video_title=video_titles[1],
            likes=comment["likes"],
            reply_count=comment["reply_count"],
        )

    def get_title(self, url):
        result = self.db.query(
            'select ShortTitle, FullTitle from video_titles where URL="{0}"'.format(url)
        )
        if result:
            return result[0][0], result[0][1]
        return None


load_dotenv()

intents = discord.Intents.default()
intents.members = True
client = discord.Client(intents=intents)

utils = Utilities.get_instance()
utils.client = client

if not os.path.exists(database_path):
    raise Exception("Couldn't find the stampy database file at %s" % database_path)
