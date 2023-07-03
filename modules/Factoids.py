"""
Remembers or forgets factoids. Can remember multiple factoids about the same thing

- `remember X is Y`: When asked about X, will reply with Y
- `remember X <reply> Y`: will always respond to X with Y
- `forget that`: forgets last factoid given in this channel
- `list X` or `listall X`: list all responses to a factoid
"""
# TODO: let people forget any factoid not given by an admin

import re
import random
import sqlite3
from typing import Optional
from config import factoid_database_path
from modules.module import Module, Response
from utilities.serviceutils import ServiceMessage
from utilities.discordutils import DiscordUser
from utilities.utilities import get_user_handle, randbool, is_bot_dev, Utilities


class Factoids(Module):
    """You can tell Stampy

    `remember <x> is <y>`

    and he will remember
    """

    def __init__(self):
        super().__init__()
        self.db = FactoidDb(factoid_database_path)
        self.who = "Someone"
        self.re_replace = re.compile(r".*?({{.+?}})")
        self.re_verb = re.compile(r".*?<([^>]+)>")
        self.re_factoid_request = re.compile(
            r"""((what)('s| is| are| do you know about| can you tell me about)) (?P<query>.+)\?""",
            re.I,
        )

        # dict of room ids to factoid: (text, value, verb) tuples
        self.prev_factoid = {}

    def process_message(self, message: ServiceMessage) -> Response:
        self.who = message.author.name
        self.utils.people.add(self.who)
        result = ""

        # Check if this message is a DM and/or is directed at Stampy
        if getattr(message.channel, "name", None):
            is_dm = False
            at_me = False
            room = message.channel.name
        else:
            is_dm = True
            at_me = True
            # hashtags are not allowed in channel names,
            # so we will always see which room is a DM and which is server channel
            if isinstance(message.author, DiscordUser):
                room = get_user_handle(message.author)
            else:  # Factoids in DMs outside Discord are not supported at the moment
                return Response()
            self.log.info(self.class_name, msg="At me because DM")

        if text := self.is_at_me(message):
            at_me = True
        else:
            text = message.clean_content

        # Get factoids from the DB matching this text
        factoids = self.db.getall(text)
        key = text

        # process the query from the text
        if match := self.re_factoid_request.match(text):
            query = match.group("query")
            query = re.sub(r"\bmy\b", f"{self.who}'s", query)
            query = re.sub(r"\bme\b", self.who, query)
            self.log.info(self.class_name, query=query)

            if not factoids:
                key = query

            factoids += self.db.getall(query)

        # forgetting factoids
        if (room in self.prev_factoid) and at_me and (text == "forget that"):
            if response := self.parse_forget_factoid(
                message=message, room=room, result=result, is_dm=is_dm
            ):
                return response

        # if the text is a valid factoid, maybe reply
        if factoids and (at_me or randbool(0.3)):
            if response := self.parse_factoid_reply(
                factoids=factoids, message=message, room=room, key=key, at_me=at_me
            ):
                return response

        # handle adding new factoids
        if text.lower().startswith("remember") or text.startswith("sr "):
            if response := self.parse_add_new_factoid(
                message=message, room=room, text=text, is_dm=is_dm
            ):
                return response

        # some debug stuff, listing all responses for a factoid
        elif text.startswith("list ") or text.startswith("listall "):
            lword, _, fact = text.partition(" ")
            values = self.db.getall(fact)
            if values:
                random.shuffle(values)  # is this the right thing to do here?
                result = f'{len(values)} values for factoid "{fact}":'
                count = (
                    200 if (lword == "listall" and is_bot_dev(message.author)) else 10
                )
                for value in values[:count]:
                    result += "\n<%s> '%s' by %s" % value
                if len(values) > count:
                    result += "\n and %s more" % (len(values) - count)
                why = "%s asked me to list the values for the factoid '%s'" % (
                    self.who,
                    fact,
                )
                return Response(confidence=10, text=result, why=why)

        # This is either not at me, or not something we can handle
        return Response()

    def parse_forget_factoid(
        self, message: ServiceMessage, room: str, result: str, is_dm: bool
    ) -> Optional[Response]:
        if is_dm and not is_bot_dev(message.author):
            return Response(
                confidence=2,
                text="Sorry, I don't accept factoid forget request in DMs",
                why=f"{message.author} was trying to make me forget a factoid in a DM",
            )

        pf = self.prev_factoid[room]
        self.prev_factoid.pop(room)
        self.db.remove(*pf)
        result += f'Ok {self.who}, forgetting that "{pf[0]}" {pf[3]} "{pf[1]}"\n'
        why = f'{self.who} told me to forget that "{pf[0]}" {pf[3]} "{pf[1]}"\n'
        return Response(confidence=10, text=result, why=why)

    def parse_factoid_reply(
        self,
        factoids: list,
        message: ServiceMessage,
        room: str,
        key: str,
        at_me: bool,
    ) -> Optional[Response]:
        verb, raw_value, by = random.choice(factoids)

        value = self.dereference(raw_value, message.author.name)

        if verb == "reply":
            result = value
        else:
            result = re.sub(f"{self.who}'s", "your", key) + f" {verb} {value}"

        why = f'{self.who} said the factoid "{key}" so I said "{raw_value}"'
        self.prev_factoid[room] = (key, raw_value, by, verb)  # key, value, verb
        if at_me:
            return Response(confidence=9, text=result, why=why)
        return Response(confidence=8, text=result, why=why)

    def parse_add_new_factoid(
        self,
        message: ServiceMessage,
        room: str,
        text: str,
        is_dm: bool,
    ) -> Optional[Response]:
        if is_dm and not is_bot_dev(message.author):
            return Response(
                confidence=2,
                text="Sorry, I don't remember things in DMs",
                why=f"{message.author} was trying to save a factoid in a DM",
            )
        is_add = True
        with_brackets = False
        verb_match = self.re_verb.match(text)
        if verb_match:
            with_brackets = True
            verb = verb_match.group(1)
        elif " is " in text:
            verb = "is"
        elif " are " in text:
            verb = "are"
        else:  # we don't have a verb, this isn't a valid add command
            verb = ""
            is_add = False

        if is_add:
            text = text.partition(" ")[2]  # Chop off the 'remember' or 'sr'
            if with_brackets:
                key, _, value = text.partition(f" <{verb}> ")
            else:
                key, _, value = text.partition(f" {verb} ")

            key = re.sub(r"\bmy\b", f"{self.who}'s", key)

            new_key = re.sub(r"\bI\b", f"{self.who}", key)
            if new_key != key:
                key = new_key
                if verb == "am":
                    verb = "is"

            result = f'Ok {self.who}, remembering that "{key}" {verb} "{value}" '
            why = f'{self.who} told me to remember that "{key}" {verb} "{value}"'
            self.log.info(
                self.class_name,
                msg=f"adding factoid {key} : {value}",
                author=message.author.id,
                verb=verb,
            )
            self.db.add(key, value, message.author.id, verb)
            self.prev_factoid[room] = (key, value, message.author.id, verb)
            return Response(confidence=10, text=result, why=why)

    def __str__(self):
        return "Factoids"

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                test_message="remember chriscanal is the person who wrote this test",
                expected_response=f'Ok {Utilities.get_instance().discord_user.name}, remembering that "chriscanal" is "the person who wrote this test"',
            ),
            self.create_integration_test(
                test_message="list chriscanal",
                expected_regex="values for factoid+",
            ),
            self.create_integration_test(
                test_message="forget that",
                expected_response=f'Ok {Utilities.get_instance().discord_user.name}, forgetting that "chriscanal" is "the person who wrote this test"',
            ),
        ]


class FactoidDb:
    """Class to handle the factoid sqlite database"""

    def __init__(self, dbfile: str):
        # in principle this will make a new db if it doesn't exist
        # that's never actually been tried though
        self.dbfile = dbfile

        try:
            open(dbfile, encoding="utf-8")
            con = sqlite3.connect(self.dbfile)
            # c = con.cursor()
            # c.execute("""SELECT tidbit FROM factoids WHERE fact = ?""",
            #   ("test",))
            # c.close()
            con.close()
        except Exception:
            con = sqlite3.connect(self.dbfile)
            c = con.cursor()
            c.execute(
                """CREATE TABLE factoids
                (id INTEGER PRIMARY KEY NOT NULL, fact TEXT, verb TEXT, tidbit TEXT, by TEXT)
                """
            )
            con.commit()
            c.close()
            con.close()

    def add(self, key: str, value: str, by: str, verb: str = "is") -> None:
        con = sqlite3.connect(self.dbfile)
        # con.text_factory = str
        c = con.cursor()
        c.execute(
            """INSERT INTO factoids(fact, verb, tidbit, by) VALUES (?, ?, ?, ?)""",
            (key, verb, value, by),
        )
        con.commit()
        c.close()
        con.close()

    def remove(self, key: str, value: str, by: str, verb: str) -> None:
        con = sqlite3.connect(self.dbfile)
        # con.text_factory = str
        c = con.cursor()
        c.execute(
            """DELETE FROM factoids WHERE fact LIKE ? AND verb = ? AND tidbit = ? """,
            (key, verb, value),
        )
        con.commit()
        c.close()
        con.close()

    def getall(self, key: str) -> list[str]:
        con = sqlite3.connect(self.dbfile)
        # con.text_factory = str
        c = con.cursor()
        c.execute(
            """SELECT verb, tidbit, by FROM factoids WHERE fact = ? COLLATE NOCASE""",
            (key,),
        )

        vals = c.fetchall()

        c.close()
        con.close()
        return vals

    def getrandom(self, key: str) -> Optional[str]:
        vals = self.getall(key)
        if vals:
            return random.choice(vals)

    def __len__(self):
        con = sqlite3.connect(self.dbfile)
        c = con.cursor()
        c.execute("""SELECT Count(*) FROM factoids""")
        val = c.fetchone()[0]

        c.close()
        con.close()
        return val
