from api.semanticwiki import SemanticWiki, QuestionSource
from config import (
    youtube_api_version,
    youtube_api_service_name,
    rob_miles_youtube_channel_id,
    discord_token,
    discord_guild,
    youtube_api_key,
    database_path,
    TEST_RESPONSE_PREFIX,
    TEST_QUESTION_PREFIX,
    wiki_config,
    wikifeed_id,
)
from database.database import Database
from datetime import datetime, timezone, timedelta
from git import Repo
from googleapiclient.discovery import build as get_youtube_api
from googleapiclient.errors import HttpError
from structlog import get_logger
from time import time
from utilities.discordutils import DiscordMessage, DiscordUser
from utilities.serviceutils import ServiceMessage
import discord
import json
import os
import psutil
import random
import re

# Sadly some of us run windows...
if not os.name == "nt":
    import pwd

log = get_logger()


class Utilities:
    __instance = None
    db = None
    discord = None
    client = None
    discord_user = None
    stop = None

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
    service_modules_dict = {}

    @staticmethod
    def get_instance():
        if Utilities.__instance is None:
            Utilities()
        return Utilities.__instance

    def __init__(self):
        if Utilities.__instance is not None:
            raise Exception("This class is a singleton!")
        else:
            Utilities.__instance = self
            self.class_name = self.__class__.__name__
            self.TOKEN = discord_token
            self.GUILD = discord_guild
            self.YOUTUBE_API_KEY = youtube_api_key
            self.DB_PATH = database_path
            self.youtube = None
            self.start_time = time()
            self.test_mode = False
            self.people = set("stampy")

            # dict to keep last timestamps in
            self.last_timestamp = {}

            # when was the most recent comment we saw posted?
            self.latest_comment_timestamp = datetime.now(timezone.utc)

            # when did we last hit the API to check for comments?
            self.last_check_timestamp = datetime.now(timezone.utc)

            # how many seconds should we wait before we can hit YT API again
            # this the start value. It doubles every time we don't find anything new
            self.youtube_cooldown = timedelta(seconds=60)

            # timestamp of last time we asked a youtube question
            self.last_question_asked_timestamp = datetime.now(timezone.utc)

            # Was the last message posted in #general by anyone, us asking a question from YouTube?
            # We start off not knowing, but it's better to assume yes than no
            self.last_message_was_youtube_question = True

            try:
                self.youtube = get_youtube_api(
                    youtube_api_service_name,
                    youtube_api_version,
                    developerKey=self.YOUTUBE_API_KEY,
                )
            except HttpError:
                if self.YOUTUBE_API_KEY:
                    log.info(self.class_name, msg="YouTube API Key is set but not correct")
                else:
                    log.info(self.class_name, msg="YouTube API Key is not set")

            log.info(self.class_name, status="Trying to open db - " + self.DB_PATH)
            self.db = Database(self.DB_PATH)
            intents = discord.Intents.default()
            intents.members = True
            intents.message_content = True
            self.client = discord.Client(intents=intents)
            self.wiki = SemanticWiki(wiki_config["uri"], wiki_config["user"], wiki_config["password"])

    def rate_limit(self, timer_name, **kwargs):
        """Should I rate-limit? i.e. Has it been less than this length of time since the last time
        this function was called using the same `timer_name`?
        Used in a function like Module.tick() to make sure it doesn't run too often.
        For example, adding this at the top of a function that checks the youtube API:

        if utils.rate_limit("check youtube API", seconds=30):
            return

        will cause the function to return early if it's been less than 30 seconds since it was last called.
        The keyword arguments are passed on to the timedelta object,
        so you can use 'seconds=', 'minutes=', 'hours=' etc, or combinations of them
        Note that this is all reset when Stampy reboots
        """
        tick_cooldown = timedelta(**kwargs)
        now = datetime.now(timezone.utc)

        # if there's no timestamp stored for that name, store now and don't rate limit
        if timer_name not in self.last_timestamp:
            self.last_timestamp[timer_name] = now
            return False

        # if it's been long enough, update the timestamp and don't rate limit
        if (now - self.last_timestamp[timer_name]) > tick_cooldown:
            self.last_timestamp[timer_name] = now
            return False
        else:  # it hasn't been long enough, rate limit
            return True

    def stampy_is_author(self, message: DiscordMessage) -> bool:
        return self.is_stampy(message.author)

    def is_stampy(self, user: DiscordUser) -> bool:
        if user.id == wikifeed_id:  # consider wiki-feed ID as stampy to ignore -- is it better to set a wiki user?
            return True
        if self.discord_user:
            return user == self.discord_user
        if user.id == str(self.client.user.id):
            self.discord_user = user
            return True
        return False

    def is_stampy_mentioned(self, message: DiscordMessage) -> bool:
        for user in message.mentions:
            if self.is_stampy(user):
                return True
        return False

    def get_youtube_comment_replies(self, comment_url):
        url_arr = comment_url.split("&lc=")
        reply_id = url_arr[-1].split(".")[0]
        request = self.youtube.comments().list(part="snippet", parentId=reply_id)
        try:
            response = request.execute()
        except HttpError as err:
            if err.resp.get("content-type", "").startswith("application/json"):
                message = json.loads(err.content).get("error").get("errors")[0].get("message")
                if message:
                    log.error(f"{self.class_name}: YouTube", error=message)
                    return
            log.error(f"{self.class_name}: YouTube", error="Unknown Google API Error")
            return
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
                "reply": reply_id,
                "text": text,
                "title": "",
                "timestamp": timestamp,
                "likes": likes,
            }
        return reply

    def get_youtube_comment(self, comment_url):
        url_arr = comment_url.split("&lc=")
        video_url = url_arr[0]
        reply_id = url_arr[-1].split(".")[0]
        request = self.youtube.commentThreads().list(part="snippet", id=reply_id)
        try:
            response = request.execute()
        except HttpError as err:
            if err.resp.get("content-type", "").startswith("application/json"):
                message = json.loads(err.content).get("error").get("errors")[0].get("message")
                if message:
                    log.error(f"{self.class_name}: YouTube", error=message)
                    return
            log.error(f"{self.class_name}: YouTube", error="Unknown Google API Error")
            return
        items = response.get("items")
        comment = {"video_url": video_url}
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
            log.info(f"{self.class_name}: YouTube", msg="Hitting YT API")
            self.last_check_timestamp = now
        else:

            log.info(
                f"{self.class_name}: YouTube",
                msg="YT waiting >%s\t- " % str(self.youtube_cooldown - (now - self.last_check_timestamp)),
            )
            return None

        if self.youtube is None:
            log.info(f"{self.class_name}: YouTube", msg="WARNING: YouTube API Key is invalid or not set")
            self.youtube_cooldown = self.youtube_cooldown * 10
            return []

        request = self.youtube.commentThreads().list(
            part="snippet", allThreadsRelatedToChannelId=rob_miles_youtube_channel_id
        )
        try:
            response = request.execute()
        except HttpError as err:
            if err.resp.get("content-type", "").startswith("application/json"):
                message = json.loads(err.content).get("error").get("errors")[0].get("message")
                if message:
                    log.error(f"{self.class_name}: YouTube", error=message)
                    return
            log.error(f"{self.class_name}: YouTube", error="Unknown Google API Error")
            return

        items = response.get("items", None)
        if not items:
            # something broke, slow way down
            log.info(f"{self.class_name}: YouTube", msg="YT comment checking broke. I got this response:")
            log.info(f"{self.class_name}: YouTube", response=response)
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

        log.info(
            f"{self.class_name}: YouTube",
            msg="Got %s items, most recent published at %s" % (len(items), newest_timestamp),
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
                "url": "https://www.youtube.com/watch?v=%s&lc=%s" % (video_id, comment_id),
                "username": username,
                "text": text,
                "title": "",
                "timestamp": timestamp,
                "likes": likes,
                "reply_count": reply_count,
            }

            new_comments.append(comment)

        log.info(
            f"{self.class_name}: YouTube", msg="Got %d new comments since last check" % len(new_comments)
        )

        if not new_comments:
            # we got nothing, double the cooldown period (but not more than 20 minutes)
            self.youtube_cooldown = min(self.youtube_cooldown * 2, timedelta(seconds=1200))
            log.info(
                f"{self.class_name}: YouTube",
                msg="No new comments, increasing cooldown timer to %s" % self.youtube_cooldown,
            )

        return new_comments

    def get_question(
        self, order_type="TOP", wiki_question_bias=SemanticWiki.default_wiki_question_percent_bias
    ):
        """Pull the oldest question from the queue
        Returns False if the queue is empty, the question string otherwise"""
        # TODO: I dont know that "latest" makes sense, but this is maybe used in a lot of places
        # So wanted to keep it consistent for now. Maybe get _a_ question?
        if order_type == "RANDOM":
            comment = self.wiki.get_random_question(wiki_question_bias=wiki_question_bias)
        elif order_type == "TOP":
            comment = self.wiki.get_top_question(wiki_question_bias=wiki_question_bias)
        else:
            comment = self.wiki.get_latest_question(wiki_question_bias=wiki_question_bias)

        if not comment:
            return None

        self.latest_question_posted = comment

        text = comment["text"]
        if len(text) > 1500:
            text = text[:1500] + " [truncated]"
        text_quoted = "> " + "\n> ".join(text.split("\n"))

        # This might be better if moved to be handled by get_random_question directly.
        if comment["source"] == QuestionSource.YOUTUBE:
            if "title" in comment:
                report = (
                    "YouTube user {0} asked this question, on the video {1}!:\n"
                    + "{2}\n"
                    + "Is it an interesting question? Maybe we can answer it!\n"
                    + "{3}"
                ).format(comment["username"], comment["title"], text_quoted, comment["url"])

            else:
                # TODO: not sure if there are any cases where this branch is met, this is left here until confirmed
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
        elif comment["source"] == QuestionSource.WIKI:
            report = "Wiki User {0} asked this question.\n{1}\n".format(
                comment["username"], comment["question_title"]
            )
            if comment["text"]:
                report += text_quoted
            report += "\nIs it an interesting question? Maybe we can answer it!\n{0}".format(comment["url"])
        else:
            report = "I am being told to post a question which I cant parse properly, i am very sorry"
        log.info(f"{self.class_name}: YouTube", youtube_question_report=report)

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
        try:
            uid = int(uid)
        except (ValueError, TypeError):
            pass
        log.info(self.class_name, function_name="index_dammit", uuid=uid, index=self.index)
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
            "INSERT OR REPLACE INTO uservotes VALUES (:user,:voted_for,IFNULL((SELECT votecount "
            "FROM uservotes WHERE user = :user AND votedFor = :voted_for),0)+:vote_quantity)"
        )
        args = {"user": user, "voted_for": voted_for, "vote_quantity": vote_quantity}
        self.db.query(query, args)
        self.db.commit()

    def get_votes_by_user(self, user):
        query = "SELECT IFNULL(sum(votecount),0) FROM uservotes where user = ?"
        args = (user,)
        return self.db.query(query, args)[0][0]

    def get_votes_for_user(self, user):
        query = "SELECT IFNULL(sum(votecount),0) FROM uservotes where votedFor = ?"
        args = (user,)
        return self.db.query(query, args)[0][0]

    def get_total_votes(self):
        query = "SELECT sum(votecount) from uservotes where user is not 0"
        return self.db.query(query)[0][0]

    def get_all_user_votes(self):
        query = "SELECT user,votedFor,votecount from uservotes;"
        return self.db.query(query)

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
            video_titles = ["Video Title Unknown", "Video Title Unknown"]

        display_title = "{0}'s question on {1}".format(
            comment["username"],
            video_titles[0],
        )

        return self.wiki.add_question(
            display_title,
            comment["username"],
            comment["timestamp"],
            comment["text"],
            comment_url=comment["url"],
            video_title=video_titles[1],
            likes=comment["likes"],
            reply_count=comment["reply_count"],
        )

    def get_title(self, url):
        result = self.db.query('select ShortTitle, FullTitle from video_titles where URL="?"', (url,))
        if result:
            return result[0][0], result[0][1]
        return None

    def list_modules(self):
        message = f"I have {len(self.modules_dict)} modules. Here are their names:"
        for module_name in self.modules_dict.keys():
            message += "\n" + module_name
        return message

    def get_time_running(self):
        message = "I have been running for"
        seconds_running = timedelta(seconds=int(time() - self.start_time))
        time_running = datetime(1, 1, 1) + seconds_running
        if time_running.day - 1:
            message += " " + str(time_running.day) + " days,"
        if time_running.hour:
            message += " " + str(time_running.hour) + " hours,"
        message += " " + str(time_running.minute) + " minutes"
        message += " and " + str(time_running.second) + " seconds."
        return message


def get_github_info():
    message = (
        "\nThe latest commit was by %(actor)s."
        + "\nThe commit message was '%(git_message)s'."
        + "\nThis commit was written on %(date)s."
    )
    repo = Repo(".")
    master = repo.head.reference
    return message % {
        "actor": master.commit.author,
        "git_message": master.commit.message.strip(),
        "date": master.commit.committed_datetime.strftime("%A, %B %d, %Y at %I:%M:%S %p UTC%z"),
    }


def get_git_branch_info():
    repo = Repo(".")
    branch = repo.active_branch
    name = repo.config_reader().get_value("user", "name")
    return f"from git branch `{branch}` by `{name}`"


def get_running_user_info():
    if not os.name == "nt":
        user_info = pwd.getpwuid(os.getuid())
        user_name = user_info.pw_gecos.split(",")[0]
        message = (
            "The last user to start my server was %(username)s."
            + "\nThey used the %(shell)s shell."
            + "\nMy Process ID is %(pid)s on this machine."
        )
        return message % {"username": user_name, "shell": user_info.pw_shell, "pid": os.getpid()}
    else:
        # This should be replaced with a better test down the line.
        shell = "Command Prompt (DOS)" if os.getenv("PROMPT") == "$P$G" else "PowerShell"
        user_name = os.getlogin()
        message = (
            "The last user to start my server was %(username)s."
            + "\nThey used the %(shell)s shell."
            + "\nMy Process ID is %(pid)s on this machine."
        )
        return message % {"username": user_name, "shell": shell, "pid": os.getpid()}


def get_memory_usage():
    process = psutil.Process(os.getpid())
    bytes_used = int(process.memory_info().rss) / 1000000
    megabytes_string = f"{bytes_used:,.2f} MegaBytes"
    return "I'm using %s of memory." % megabytes_string


def get_question_id(message):
    text = message.clean_content
    first_number_found = re.search(r"\d+", text)
    if first_number_found:
        return int(first_number_found.group())
    return ""


def contains_prefix_with_number(text, prefix):
    prefix = prefix.strip()  # remove white space for regex formatting
    return bool(re.search(rf"^{prefix}\s[0-9]+", text))


def is_test_response(text):
    return contains_prefix_with_number(text, TEST_RESPONSE_PREFIX)


def is_test_question(text):
    return contains_prefix_with_number(text, TEST_QUESTION_PREFIX)


def is_test_message(text):
    return is_test_response(text) or is_test_question(text)


def randbool(p):
    if random.random() < p:
        return True
    else:
        return False


def is_stampy_mentioned(message: ServiceMessage) -> bool:
    utils = Utilities.get_instance()
    return utils.service_modules_dict[message.service].service_utils.is_stampy_mentioned(message)


def stampy_is_author(message: ServiceMessage) -> bool:
    utils = Utilities.get_instance()
    return utils.service_modules_dict[message.service].service_utils.stampy_is_author(message)


def get_guild_and_invite_role():
    utils = Utilities.get_instance()
    guild = utils.client.guilds[0]
    invite_role = discord.utils.get(guild.roles, name="can-invite")
    return guild, invite_role
