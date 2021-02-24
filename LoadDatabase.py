import database
import json
import sys
import utilities


def dropTables():
    try:
        db.query("drop table questions")
    except:
        pass
    try:
        db.query("drop table users")
    except:
        pass
    try:
        db.query("drop table uservotes")
    except:
        pass
    db.commit()


def createTables():
    db.query(
        """CREATE TABLE questions (url STRING NOT NULL PRIMARY KEY, username STRING, title STRING, text STRING, replied BOOL DEFAULT false);"""
    )
    # db.query("""CREATE TABLE users (user INT NOT NULL PRIMARY KEY, votecount INT DEFAULT 0);""")
    db.query(
        """CREATE TABLE uservotes (user INT NOT NULL, votedFor INT NOT NULL, votecount INT DEFAULT 1, PRIMARY KEY(user,votedFor))"""
    )


def loadQuestions(file):
    with open(file) as qqfile:
        qq = json.load(qqfile)

    db.query("DELETE FROM questions")

    for question in qq:

        url = question["url"]
        username = question["username"]
        title = question["title"]
        text = question["text"]
        print("Inserting question: {0}".format(url))
        db.query(
            "INSERT INTO questions VALUES (?,?,?,?,?,?,?);",
            (url, username, title, text, False, False, None),
        )
        # try:
        #    break
        # except:
        #    print("Error inserting question - ", sys.exc_info()[0])

    db.commit()


def loadUsers(file):
    with open(file) as usersFile:
        users = json.load(usersFile)

    db.query("DELETE FROM users")

    for i in users:
        user = users[i]
        votecount = user["votecount"]
        print("Loading user vote for " + i)
        db.query("INSERT INTO users VALUES (?,?)", (i, votecount))

    db.commit()


def loadVotes(file):
    with open(file) as usersFile:
        users = json.load(usersFile)

    db.query("DELETE FROM uservotes")

    for i in users:
        user = users[i]
        votes = user["votes"]
        for vote in votes:
            print(
                "adding vote for user: {0} votedFor: {1} count: {2}".format(
                    i, vote, votes[vote]
                )
            )

            db.query("INSERT INTO uservotes VALUES (?,?,?)", (i, vote, votes[vote]))

    db.commit()


util = utilities.Utilities.getInstance("stampy.db")
db = util.db

# util.getDatabase("stampy.db")
print(util.db.connected)


# dropTables()
# createTables()
# loadQuestions("qq.json")
# loadUsers("stamps.json") #load users is no longer required, unless we need the user table to track other stuff. We can just use uservotes
# loadVotes("stamps.json")

# q = util.getNextQuestion("url")

# print(q[0])

# v = util.getVotes(181142785259208704)

# print(v)

# util.setQuestionReplied(q[0])
# util.addVote(123,2) #add votes some random users who dont already exist

# print(util.getNextQuestion("*"))
# print(util.getRandomQuestion("text"))
