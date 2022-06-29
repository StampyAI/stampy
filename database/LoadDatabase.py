import os
import json
import utilities
from structlog import get_logger

log = get_logger()
script_name = os.path.basename(__file__)


def drop_tables():
    db.query("drop table questions")
    db.query("drop table users")
    db.query("drop table uservotes")
    db.commit()


def create_tables():
    db.query(
        "CREATE TABLE questions (url STRING NOT NULL PRIMARY KEY, username "
        "STRING, title STRING, text STRING, replied BOOL DEFAULT false);"
    )
    db.query(
        "CREATE TABLE uservotes (user INT NOT NULL, votedFor INT NOT "
        "NULL, votecount INT DEFAULT 1, PRIMARY KEY(user,votedFor))"
    )


def load_questions(file):
    with open(file) as qqfile:
        qq = json.load(qqfile)

    db.query("DELETE FROM questions")

    for question in qq:

        url = question["url"]
        username = question["username"]
        title = question["title"]
        text = question["text"]
        log.info(script_name, msg="Inserting question: {0}".format(url))
        db.query(
            "INSERT INTO questions VALUES (?,?,?,?,?,?,?);", (url, username, title, text, False, False, None),
        )

    db.commit()


def load_users(file):
    with open(file) as usersFile:
        users = json.load(usersFile)

    db.query("DELETE FROM users")

    for i in users:
        user = users[i]
        vote_count = user["votecount"]
        log.info(script_name, msg="Loading user vote for " + i)
        db.query("INSERT INTO users VALUES (?,?)", (i, vote_count))

    db.commit()


def load_votes(file):
    with open(file) as usersFile:
        users = json.load(usersFile)

    db.query("DELETE FROM uservotes")

    for i in users:
        user = users[i]
        votes = user["votes"]
        for vote in votes:
            log.info(
                script_name,
                msg="adding vote for user: {0} votedFor: {1} count: {2}".format(i, vote, votes[vote]),
            )

            db.query("INSERT INTO uservotes VALUES (?,?,?)", (i, vote, votes[vote]))

    db.commit()


util = utilities.Utilities.get_instance()
db = util.db

log.info(script_name, msg=util.db.connected)
