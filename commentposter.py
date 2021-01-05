# -*- coding: utf-8 -*-

# Sample Python code for youtube.comments.insert
# See instructions for running these code samples locally:
# https://developers.google.com/explorer-help/guides/code_samples#python

import os

import google_auth_oauthlib.flow
import googleapiclient.discovery
import googleapiclient.errors
import time
import json
import sys
from utilities import Utilities


class CommentPoster(object):
    utils = None

    def __init__(self):
        self.utils = self.utils = Utilities.getInstance()
        scopes = ["https://www.googleapis.com/auth/youtube.force-ssl"]
        # scopes = ["https://www.googleapis.com/auth/youtube"]
        api_service_name = "youtube"
        api_version = "v3"
        client_secrets_file = utils.YTAPIKEY

        # Get credentials and create an API client
        flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
            client_secrets_file, scopes)
        credentials = flow.run_console()
        self.youtube = googleapiclient.discovery.build(
            api_service_name, api_version, credentials=credentials)

    def postcomment(self, commentbody):
        request = self.youtube.comments().insert(
            part="snippet",
            body=commentbody)

        try:
            response = request.execute()
        except googleapiclient.errors.HttpError as e:
            print(e)
            return

        print(response)
        print(type(response))
        return response

    def run(self):
        topost = []
        while True:
            time.sleep(1)
            with open("topost.json") as postfile:
                try:
                    topost = json.load(postfile)
                except json.decoder.JSONDecodeError:
                    topost = []

            if topost:
                print("topost:", topost)
            else:
                print(".", end="")
                sys.stdout.flush()


            if topost:
                body = topost.pop()

                response = self.postcomment(body)


            with open("topost.json", 'w') as postfile:  # we modified the queue, put the rest back, if any
                json.dump(topost, postfile, indent="\t")


        # body = {
        #   "snippet": {
        #     "parentId": "Ugx2FUdOI6GuxSBkOQd4AaABAg",
        #     "textOriginal": "This is comment 23",
        #     "authorChannelId": {
        #       "value": "UCFDiTXRowzFvh81VOsnf5wg"
        #     }
        #   }
        # }

# [{'snippet': {'parentId': 'Ugx2FUdOI6GuxSBkOQd4AaABAg', 'textOriginal': 'This is comment 24', 'authorChannelId': {'value': 'UCFDiTXRowzFvh81VOsnf5wg'}}}]
# {
#           "snippet": {
#             "parentId": "Ugx2FUdOI6GuxSBkOQd4AaABAg",
#             "textOriginal": "This is comment 23",
#             "authorChannelId": {
#               "value": "UCFDiTXRowzFvh81VOsnf5wg"
#             }
#           }
#         }
        # self.postcomment(body)


if __name__ == "__main__":
    commentPoster = CommentPoster()
    commentPoster.run()