import os
import time
import json
import sys
import googleapiclient.errors
from utilities import Utilities
import google_auth_oauthlib.flow as google_auth
from googleapiclient.discovery import build as get_youtube_api
from itertools import cycle

spinner = cycle("\\|/-")


class CommentPoster(object):
    utils = None

    def __init__(self):
        self.utils = self.utils = Utilities.get_instance()
        scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
        api_service_name = "youtube"
        api_version = "v3"

        # Get credentials and create an API client
        flow = google_auth.InstalledAppFlow.from_client_secrets_file(os.getenv("CLIENT_SECRET_PATH"), scopes)
        credentials = flow.run_console()
        self.youtube = get_youtube_api(api_service_name, api_version, credentials=credentials)

    def post_comment(self, comment_body):
        # attempts to post comment
        # returns 2xx response or raises HTTP error
        request = self.youtube.comments().insert(part="snippet", body=comment_body)

        try:
            response = request.execute()
        except googleapiclient.errors.HttpError as e:
            print(e)
            raise

        print(response)
        print(type(response))
        return response

    # def verify_comment(self, comment_id):
    # checks for  the existence of a comment with comment's id

    # def run(self): (rewrite)
    # periodically,
    # toverify: if old_enough, verify_comment
    #   drop or set failed
    # topost: post_comment
    #   set pub time or set failed

    # table comment_queue
    # body (what is needed for post_comment), failed, id, pub time

    def run(self):
        while True:
            time.sleep(1)
            with open("database/topost.json") as post_file:
                try:
                    responses_to_post = json.load(post_file)
                except json.decoder.JSONDecodeError:
                    responses_to_post = []

            if responses_to_post:
                print("responses_to_post:", responses_to_post)
                print(".", end="")
            else:
                print("\b" + next(spinner), end="")
                sys.stdout.flush()

            if responses_to_post:
                body = responses_to_post.pop()

                self.post_comment(body)

            with open("database/topost.json", "w") as post_file:
                # we modified the queue, put the rest back, if any
                json.dump(responses_to_post, post_file, indent="\t")


if __name__ == "__main__":
    commentPoster = CommentPoster()
    commentPoster.run()
