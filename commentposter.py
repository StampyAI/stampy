import time
import json
import sys
import googleapiclient.errors
from utilities import Utilities
import google_auth_oauthlib.flow
import googleapiclient.discovery


class CommentPoster(object):
    utils = None

    def __init__(self):
        self.utils = self.utils = Utilities.get_instance()
        scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
        api_service_name = "youtube"
        api_version = "v3"
        client_secrets_file = self.utils.YOUTUBE_API_KEY

        # Get credentials and create an API client
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            client_secrets_file, scopes
        )
        credentials = flow.run_console()
        self.youtube = googleapiclient.discovery.build(
            api_service_name, api_version, credentials=credentials
        )

    def post_comment(self, comment_body):
        request = self.youtube.comments().insert(part="snippet", body=comment_body)

        try:
            response = request.execute()
        except googleapiclient.errors.HttpError as e:
            print(e)
            return

        print(response)
        print(type(response))
        return response

    def run(self):
        while True:
            time.sleep(1)
            with open("database/topost.json") as post_file:
                try:
                    top_post = json.load(post_file)
                except json.decoder.JSONDecodeError:
                    top_post = []

            if top_post:
                print("top_post:", top_post)
            else:
                print(".", end="")
                sys.stdout.flush()

            if top_post:
                body = top_post.pop()

                self.post_comment(body)

            with open(
                "database/topost.json", "w"
            ) as post_file:  # we modified the queue, put the rest back, if any
                json.dump(top_post, post_file, indent="\t")


if __name__ == "__main__":
    commentPoster = CommentPoster()
    commentPoster.run()
