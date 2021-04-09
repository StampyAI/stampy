from api.semanticwiki import SemanticWiki
from utilities import utils
import discord
import csv
import sqlite3
import re
from config import discord_token


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


# if you dont have the short tables in the db, you might want to add them or things will break
# load_short_titles("./database/shorttitles.csv")

load_short_titles("C:\\Users\\james\\OneDrive\\Projects\\Stampy\\stampy\\database\\shorttitles.csv")
# TODO: Enable this to add questions from the sqlite DB
# questions schema:  (url , username STRING, title STRING, text STRING,
#                     replied BOOL DEFAULT false, "asked" BOOL DEFAULT 'false');

#url, username, title, text, timestamp = None, likes = None)
questions = utils.db.query("SELECT * FROM QUESTIONS;")
for question in questions:
    print("Adding question: " + question[0])
    utils.add_question(question[0], question[1], None, question[3])

client = utils.client


@client.event
async def on_ready():
    guild = discord.utils.find(lambda g: g.name == utils.GUILD, client.guilds)
    # TODO: Make sure this goes to General in production
    print(utils.GUILD)
    general = discord.utils.find(lambda c: c.name == "general", guild.channels)
    async for message in general.history(limit=200):
        if message.author.name == client.user.name.lower():
            text = message.clean_content
            if text.startswith("Ok, posting this:"):
                reply = extract_reply(text)
                question_url = reply[0]
                reply_text = reply[1]
                users = reply[2]
                reply_time = message.created_at
                title = "{0}'s Answer to {1} on {2}".format(users[0], utils.get_title(question_url)[0], reply_time)
                print("Adding answer - " + title)
                # TODO: enable this to add answers from Discord
                #utils.wiki.add_answer(question_url, users, reply_text, title, reply_time)


def extract_reply(text):
    #Pull the text of the reply out of the message
    lines = text.split("\n")
    reply_message = ""
    url = ""
    users = ""
    for line in lines:
        # pull out the quote syntax "> " and a user if there is one
        #print(line)
        #TODO: Is this right? The reply module one didn't work, should likely fix?
        match = re.match(r".*> (.*)", line)
        if match:
            if line != lines[-3]:
                reply_message += match.group(1)
            else:
                users = line[46:-1].split(",")
    url = lines[-1][32:].replace(">", "").replace("<", "")
    return url, reply_message, users

# TODO: enable this to add answers from Discord
#client.run(discord_token)
