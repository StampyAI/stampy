from database import Database
import json

class Utilities:
    
    __instance = None
    db = None

    @staticmethod 
    def getInstance(dbPath=None):
        if Utilities.__instance == None:
            Utilities()
            Utilities.db = Database(dbPath)
        return Utilities.__instance

    def __init__(self):
        if Utilities.__instance != None:
            raise Exception("This class is a singleton!")
        else:
            Utilities.__instance = self
    

    def addVote(self,user,votedFor):
        query = "INSERT OR REPLACE INTO uservotes VALUES ({0},{1},IFNULL((SELECT votecount FROM uservotes WHERE user = {0} AND votedFor = {1}),0)+1)".format(user,votedFor)
        self.db.query(query)
        self.db.commit()

    def getVotes(self,user):
        query = "SELECT sum(votecount) FROM uservotes where user = {0}".format(user)
        return self.db.query(query)[0][0]

    def addQuestion(self,url,username,title,text):
        self.db.query('INSERT INTO questions VALUES (?,?,?,?,?);',(url,username,title,text,False))
        self.db.commit()
    
    #Shouldn't be adding where clauses to the 'table' param.. 
    #TODO: Fix this crap
    def getNextQuestion(self,columns="*"):
        return self.db.getLast("questions WHERE replied=False",columns)
    #TODO: see above
    def getRandomQuestion(self,columns="*"):
        return self.db.getLast("questions WHERE replied=False ORDER BY RANDOM()",columns)
    
    def setQuestionReplied(self,url):
        self.db.query('UPDATE questions SET replied = True WHERE url="{0}";'.format(url))
        self.db.commit()
        return True

    