import os
import time
import json
import pickle
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
        response = request.execute()

        # print(response)
        print(type(response))
        return response

    def verify_comment(self, comment_id):
        request = self.youtube.comments().list(part="id", id=comment_id)

        try:
            response = request.execute() # if no error, comment was found
            return True
        except googleapiclient.errors.HttpError as e:
            if e.status_code == 404: # comment not found
                return False
            else:
                raise

    # table comment_queue
    # body varchar(3000) NOT NULL
    # id int
    # pub_time float
    # ver_time float
    # failed bool

    def run(self):
        query = self.utils.db.query
        old_enough = lambda t: time.time() - t >= 600 # 10 minutes

        while True:
            time.sleep(1)

            # verify posts
            toverify = query("SELECT id, pub_time FROM comment_queue WHERE id!=NULL AND ver_time=NULL")
            for (comment_id, comment_time) in toverify:
                if old_enough(comment_time) and self.verify_comment(comment_id):
                    query("UPDATE comment_queue SET ver_time=? WHERE id=?",
                        (time.time(), comment_id))
                    print(f"{comment_id = } verified")
                else:
                    query("UPDATE comment_queue SET failed=TRUE WHERE id=?",
                            (comment_id,))
                    print(f"{comment_id = } failed to verify")
            # post new
            topost = query("SELECT body FROM comment_queue WHERE id==NULL AND failed!=True")
            for body in topost:
                try:
                    response = self.post_comment(body)
                    query("UPDATE comment_queue SET pub_time=?, id=? WHERE body=?",
                            (time.time(), response["id"], body))
                    print(f"Comment posted: {body!r}")
                except googleapiclient.errors.HttpError as e:
                    query("UPDATE comment_queue SET failed=TRUE WHERE body=?",
                            (body,))
                    print(f"Comment not posted with error {e}; {body}")


if __name__ == "__main__":
    commentPoster = CommentPoster()
    commentPoster.run()
