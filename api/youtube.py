from __future__ import annotations

from datetime import datetime, timezone, timedelta
import json
from typing import Optional
from googleapiclient.discovery import build as get_youtube_api
from googleapiclient.errors import HttpError
from structlog import get_logger

from config import (
    youtube_api_version,
    youtube_api_service_name,
    rob_miles_youtube_channel_id,
    youtube_api_key,
)
from utilities import Utilities

log = get_logger()
utils = Utilities.get_instance()

class YoutubeAPI:
    """Youtube API"""
    __instance: Optional[YoutubeAPI] = None
    YOUTUBE_API_KEY = youtube_api_key
    
    @staticmethod
    def get_instance() -> YoutubeAPI:
        if YoutubeAPI.__instance is None:
            return YoutubeAPI()
        return YoutubeAPI.__instance
    
    def __init__(self) -> None:
        if YoutubeAPI.__instance is not None:
            raise Exception(
                "This class is a singleton! Access it using `Utilities.get_instance()`"
            )
        YoutubeAPI.__instance = self
        self.class_name = self.__class__.__name__
        
        # dict to keep last timestamps in
        self.last_timestamp: dict[str, datetime] = {}

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

    def rate_limit(self, timer_name: str, **kwargs) -> bool:
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
        # it hasn't been long enough, rate limit
        return True


    def get_youtube_comment_replies(self, comment_url: str) -> list[dict]:
        url_arr = comment_url.split("&lc=")
        reply_id = url_arr[-1].split(".")[0]
        request = self.youtube.comments().list(part="snippet", parentId=reply_id)
        try:
            response = request.execute()
        except HttpError as err:
            if err.resp.get("content-type", "").startswith("application/json"):
                message = (
                    json.loads(err.content).get("error").get("errors")[0].get("message")
                )
                if message:
                    log.error(self.class_name, error=message)
                    return []
            log.error(self.class_name, error="Unknown Google API Error")
            return []
        items: list[dict] = response.get("items", [])
        replies = [self.parse_reply(item) for item in items]
        return replies
    
    @staticmethod
    def parse_reply(item: dict) -> dict:
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
                message = (
                    json.loads(err.content).get("error").get("errors")[0].get("message")
                )
                if message:
                    log.error(self.class_name, error=message)
                    return
            log.error(self.class_name, error="Unknown Google API Error")
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

    def check_for_new_youtube_comments(self) -> Optional[list[dict]]:
        """Consider getting the latest comments from the channel
        Returns a list of dicts if there are new comments
        Returns [] if it checked and there are no new ones
        Returns None if it didn't check because it's too soon to check again"""

        now = datetime.now(timezone.utc)

        if (now - self.last_check_timestamp) > self.youtube_cooldown:
            log.info(self.class_name, msg="Hitting YT API")
            self.last_check_timestamp = now
        else:
            log.info(
                self.class_name,
                msg=f"YT waiting >{self.youtube_cooldown - (now - self.last_check_timestamp)}\t- "
            )
            return None

        if self.youtube is None:
            log.info(
                f"{self.class_name}: YouTube",
                msg="WARNING: YouTube API Key is invalid or not set",
            )
            self.youtube_cooldown = self.youtube_cooldown * 10
            return []

        request = self.youtube.commentThreads().list(
            part="snippet", allThreadsRelatedToChannelId=rob_miles_youtube_channel_id
        )
        try:
            response = request.execute()
        except HttpError as err:
            if err.resp.get("content-type", "").startswith("application/json"):
                message = (
                    json.loads(err.content).get("error").get("errors")[0].get("message")
                )
                if message:
                    log.error(self.class_name, error=message)
                    return
            log.error(self.class_name, error="Unknown Google API Error")
            return

        items = response.get("items", None)
        if not items:
            # something broke, slow way down
            log.info(
                self.class_name,
                msg="YT comment checking broke. I got this response:",
            )
            log.info(self.class_name, response=response)
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
            self.class_name,
            msg=f"Got {len(items)} items, most recent published at {newest_timestamp}"
        )

        # save the timestamp of the newest comment we found, so next API call knows what's fresh
        self.latest_comment_timestamp = newest_timestamp

        new_comments = [self.parse_comment(item) for item in new_items]
        
        log.info(
            self.class_name,
            msg=f"Got {len(new_comments)} new comments since last check",
        )

        if not new_comments:
            # we got nothing, double the cooldown period (but not more than 20 minutes)
            self.youtube_cooldown = min(
                self.youtube_cooldown * 2, timedelta(seconds=1200)
            )
            log.info(
                self.class_name,
                msg=f"No new comments, increasing cooldown timer to {self.youtube_cooldown}"
            )

        return new_comments
    
    
    
    @staticmethod
    def parse_comment(item: dict) -> dict:
        top_level_comment = item["snippet"]["topLevelComment"]
        video_id = top_level_comment["snippet"]["videoId"]
        comment_id = top_level_comment["id"]
        username = top_level_comment["snippet"]["authorDisplayName"]
        text = top_level_comment["snippet"]["textOriginal"]
        timestamp = top_level_comment["snippet"]["publishedAt"][:-1]
        likes = top_level_comment["snippet"]["likeCount"]
        reply_count = item["snippet"]["totalReplyCount"]
        comment = {
            "url": f"https://www.youtube.com/watch?v={video_id}&lc={comment_id}",
            "username": username,
            "text": text,
            "title": "",
            "timestamp": timestamp,
            "likes": likes,
            "reply_count": reply_count,
        }
        return comment

        

    def add_youtube_question(self, comment: dict):
        """Get the video title from the video URL, without the comment id
        """
        # TODO: do we need to actually parse the URL param properly? Order is hard-coded from get yt comment
        video_titles = utils.get_title(comment["url"].split("&lc=")[0])

        if not video_titles:
            # this should actually only happen in dev
            video_titles = ["Video Title Unknown", "Video Title Unknown"]

        display_title = f"{comment['username']}'s question on {video_titles[0]}"

        # TODO: add to Coda
