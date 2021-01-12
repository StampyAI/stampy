import discord
from database import Database

import json

from datetime import datetime, timezone, timedelta

import googleapiclient.discovery

class Utilities:
    
    __instance = None
    db = None
    discord = None
    client = None

    TOKEN = None
    GUILD = None
    YTAPIKEY = None
    DBPATH = None 

    lastmessagewasYTquestion = None
    latestcommentts = None 
    lastcheckts = None
    ytcooldown = None
    lasttickts = None
    lastqaskts = None
    latestquestionposted = None

    users = None
    ids = None
    index = None
    scores = None



    @staticmethod 
    def getInstance(dbPath=None,discord=None):
        if Utilities.__instance == None:
            Utilities()
            print("Trying to open db - " + dbPath)
            Utilities.db = Database(dbPath)
            #Utilities.discord = discord
        return Utilities.__instance

    def __init__(self):
        if Utilities.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            Utilities.__instance = self

    def tds(self,s):
        """Make a timedelta object of s seconds"""
        return timedelta(seconds=s)

    def check_for_new_youtube_comments(self):
        """Consider getting the latest comments from the channel
        Returns a list of dicts if there are new comments
        Returns [] if it checked and there are no new ones 
        Returns None if it didn't check because it's too soon to check again"""

        # print("Checking for new YT comments")

        now = datetime.now(timezone.utc)

        # print("It has been this long since I last called the YT API: " + str(now - self.lastcheckts))
        # print("Current cooldown is: " + str(self.ytcooldown))
        if (now - self.lastcheckts) > self.ytcooldown:
            print("Hitting YT API")
            self.lastcheckts = now
        else:
            print("YT waiting >%s\t- " % str(self.ytcooldown - (now - self.lastcheckts)), end='')
            return None

        api_service_name = "youtube"
        api_version = "v3"
        DEVELOPER_KEY = self.YTAPIKEY

        youtube = googleapiclient.discovery.build(api_service_name, api_version, developerKey=DEVELOPER_KEY)

        request = youtube.commentThreads().list(
            part="snippet",
            allThreadsRelatedToChannelId="UCLB7AzTwc6VFZrBsO2ucBMg"
        )
        response = request.execute()

        items = response.get('items', None)
        if not items:
            print("YT comment checking broke. I got this response:")
            print(response)
            self.ytcooldown = self.ytcooldown * 10  # something broke, slow way down
            return None

        newestts = self.latestcommentts

        newitems = []
        for item in items:
            # Find when the comment was published
            pubTsStr = item['snippet']['topLevelComment']['snippet']['publishedAt']
            # For some reason fromisoformat() doesn't like the trailing 'Z' on timestmaps
            # And we add the "+00:00" so it knows to use UTC
            pubTs = datetime.fromisoformat(pubTsStr[:-1] + "+00:00")

            # If this comment is newer than the newest one from last time we called API, keep it
            if pubTs > self.latestcommentts:
                newitems.append(item)

            # Keep track of which is the newest in this API call
            if pubTs > newestts:
                newestts = pubTs

        print("Got %s items, most recent published at %s" % (len(items), newestts))

        # save the timestamp of the newest comment we found, so next API call knows what's fresh
        self.latestcommentts = newestts

        newcomments = []
        for item in newitems:
            videoId = item['snippet']['topLevelComment']['snippet']['videoId']
            commentId = item['snippet']['topLevelComment']['id']
            username = item['snippet']['topLevelComment']['snippet']['authorDisplayName']
            text = item['snippet']['topLevelComment']['snippet']['textOriginal']
            # print("dsiplay text:" + item['snippet']['topLevelComment']['snippet']['textDisplay'])
            # print("original text:" + item['snippet']['topLevelComment']['snippet']['textOriginal'])

            comment = {'url': "https://www.youtube.com/watch?v=%s&lc=%s" % (videoId, commentId),
                        'username': username,
                        'text': text,
                        'title': ""
                    }

            newcomments.append(comment)

        print("Got %d new comments since last check" % len(newcomments))

        if not newcomments:
            # we got nothing, double the cooldown period (but not more than 20 minutes)
            self.ytcooldown = min(self.ytcooldown * 2, self.tds(1200))
            print("No new comments, increasing cooldown timer to %s" % self.ytcooldown)

        return newcomments

    def get_latest_question(self):
        """Pull the oldest question from the queue
        Returns False if the queue is empty, the question string otherwise"""

        comment = self.getNextQuestion("text,username,title,url")


        commentdict = {'text': comment[0],
                        'username': comment[1],
                        'title': comment[2],
                        'url': comment[3]}
        self.latestquestionposted = commentdict

        text = comment[0]
        if len(text) > 1500:
            text = text[:1500] + " [truncated]"
        textquoted = "> " + "\n> ".join(text.split("\n"))

        title = comment[2]
        if title:
            report = """YouTube user {0} asked this question, on the video {1}!:
                        {2}
                        Is it an interesting question? Maybe we can answer it!
                        {3}""".format(comment[1],comment[2],textquoted,comment[3])

        else:
            report = """YouTube user {0} just asked a question!:
                    {2}
                    Is it an interesting question? Maybe we can answer it!
                    {3}""".format(comment[1],comment[2],textquoted,comment[3])

        print("==========================")
        print(report)
        print("==========================")

        self.lastqaskts = datetime.now(timezone.utc)  # reset the question waiting timer

        return report

    def getQuestionCount(self):
        query = "SELECT COUNT(*) FROM questions"
        return self.db.query(query)[0][0]

    def clearVotes(self):
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

        if user in self.index:  # maybe we got given a valid ID?
            return self.index[user]

        uid = getattr(user, 'id', None)  # maybe we got given a User or Member object that has an ID?
        print(uid)
        print(self.index)
        if uid:
            return self.index_dammit(str(uid))

        return None

    def get_user_score(self, user):
        index = self.index_dammit(user)
        if index:
            return self.scores[index]
        else:
            return 0.0

    def addVote(self,user,votedFor,voteQty):
        query = """INSERT OR REPLACE INTO uservotes VALUES ({0},{1},IFNULL((SELECT votecount FROM uservotes WHERE user = {0}  
                AND votedFor = {1}),0)+{2})""".format(user,votedFor,voteQty)
        self.db.query(query)
        self.db.commit()

    def getVotesByUser(self,user):
        query = "SELECT IFNULL(sum(votecount),0) FROM uservotes where user = {0}".format(user)
        return self.db.query(query)[0][0]

    def getVotesForUser(self,user):
        query = "SELECT IFNULL(sum(votecount),0) FROM uservotes where votedFor = {0}".format(user)
        return self.db.query(query)[0][0]

    def getTotalVotes(self):
        query = "SELECT sum(votecount) from uservotes where user is not 0"
        return self.db.query(query)[0][0]

    def getAllUserVotes(self):
        return self.db.get("uservotes","user,votedFor,votecount")
    
    def getUsers(self):
        query = "SELECT user from (SELECT user FROM uservotes UNION SELECT votedFor as user FROM uservotes)"
        result = self.db.query(query)
        users = [item for sublist in result for item in sublist]
        return users
        
    def addQuestion(self,url,username,title,text):
        self.db.query('INSERT INTO questions VALUES (?,?,?,?,?)',(url,username,title,text,False))
        self.db.commit()
    
    #Kind of a hack, using the table param for the where clause
    #TODO: Fix this crap
    def getNextQuestion(self,columns="*"):
        return self.db.getLast("questions WHERE replied=False",columns)

    #TODO: see above
    def getRandomQuestion(self,columns="*"):
        return self.db.getLast("questions WHERE replied=False ORDER BY RANDOM()",columns)
    
    def setQuestionReplied(self,url):
        self.db.query('UPDATE questions SET replied = True WHERE url="{0}"'.format(url))
        self.db.commit()
        return True

    