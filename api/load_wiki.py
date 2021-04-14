from api.semanticwiki import SemanticWiki
from utilities import utils
import discord
import csv
import sqlite3
import re
from config import discord_token, ENVIRONMENT_TYPE


###########################################################################
#  This is a temporary helper file to load the questions from SQL lite into the wiki
#  It also can scrape the Discord to get replies to questions, and add those as well.
#  It's super messy, partially because we have to actually run the bot / discord directly here to scrape the messages
#  Long-term, this will go away and won't be part of the project / master branch
###########################################################################


def load_short_titles(csv_path):
    # Get CSV from: https://docs.google.com/spreadsheets/d/1SvMD1ws9RmNPzWBRt75fRTW2rOSgOYLetL6R-5qplj8
    con = utils.db.conn
    cur = con.cursor()
    try:
        cur.execute("DROP TABLE video_titles")
    except:
        pass

    cur.execute("CREATE TABLE video_titles (URL STRING PRIMARY KEY, FullTitle STRING, ShortTitle STRING);")

    with open(csv_path, "r") as fin:
        # csv.DictReader uses first line in file for column headings by default
        dr = csv.DictReader(fin)
        to_db = [(i["URL"], i["FullTitle"], i["ShortTitle"]) for i in dr]

    cur.executemany("INSERT INTO video_titles (URL, FullTitle, ShortTitle) VALUES (?, ?, ?);", to_db)
    con.commit()
    return


has_titles = utils.db.query("SELECT name FROM sqlite_master WHERE type='table' AND name='video_titles';")
if not has_titles:
    load_short_titles("./database/shorttitles.csv")


questions = []
# TODO: uncomment to enable
# questions = utils.db.query("SELECT * FROM QUESTIONS;")

for question in questions:
    comment = utils.get_youtube_comment(question[0])
    comment["url"] = question[0]
    comment["username"] = question[1]
    comment["text"] = question[3]

    video_titles = utils.get_title(comment["url"].split("&lc=")[0])

    if not video_titles:
        # this should actually only happen in dev
        video_titles = ["Video Title Unknown", "Video Title Unknown"]

    question_title = "{0} on {1} by {2}".format(video_titles[0], comment["timestamp"], comment["username"])

    utils.wiki.add_question(question_title, comment["username"], comment["timestamp"], comment["text"],
                            comment_url=comment["url"], video_title=video_titles[1], likes=comment["likes"],
                            asked=question[5])


client = utils.client
channel_name = "general"
max_history = None  # None == all history

if ENVIRONMENT_TYPE == "development":
    channel_name = "test"
    max_history = None


@client.event
async def on_ready():
    guild = discord.utils.find(lambda g: g.name == utils.GUILD, client.guilds)
    # TODO: Make sure this goes to General in production
    print(utils.GUILD)
    general = discord.utils.find(lambda c: c.name == channel_name, guild.channels)
    async for message in general.history(limit=99999999):
        if message.author.name == client.user.name.lower():
            text = message.clean_content
            if text.startswith("Ok, posting this:"):
                reply = extract_reply(text)
                comment_url = reply[0]

                question = utils.db.query("SELECT username FROM QUESTIONS WHERE url='{0}';".format(comment_url))

                comment = utils.get_youtube_comment(comment_url)
                comment["url"] = comment_url
                if questions:
                    comment["username"] = question[0][0]

                video_titles = utils.get_title(comment["url"].split("&lc=")[0])

                if not video_titles:
                    # this should actually only happen in dev
                    video_titles = ["Video Title Unknown", "Video Title Unknown"]

                question_title = "{0} on {1} by {2}".format(video_titles[0], comment["timestamp"],
                                                            comment["username"])
                answer_text = reply[1]
                answer_users = reply[2]
                answer_time = message.created_at

                answer_title = answer_users[0] + "'s Answer to " + question_title

                utils.wiki.add_answer(answer_title, answer_users, answer_time, answer_text, question_title)


def extract_reply(text):
    # Pull the text of the reply out of the message
    lines = text.split("\n")
    reply_message = ""
    url = ""
    users = ""
    for line in lines:
        # pull out the quote syntax "> " and a user if there is one
        # print(line)
        # TODO: Is this right? The reply module one didn't work, should likely fix?
        match = re.match(r".*> (.*)", line)
        if match:
            if line != lines[-3]:
                reply_message += match.group(1)
            else:
                users = line[46:-1].split(",")
    url = lines[-1][32:].replace(">", "").replace("<", "")
    return url, reply_message, users


# TODO: enable this to add answers from Discord
client.run(discord_token)
