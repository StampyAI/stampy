import re
import random
import sqlite3
from config import rob_id
from modules.module import Module, Response


def randbool(p):
    if random.random() < p:
        return True
    else:
        return False


def is_bot_dev(user):
    if user.id == rob_id:
        return True
    roles = getattr(user, "roles", [])
    return "bot dev" in [role.name for role in roles]


class Factoids(Module):
    def __init__(self):
        super().__init__()
        self.class_name = self.__class__.__name__
        dbpath = "factoids.db"
        self.db = self.FactoidDb(dbpath)
        self.who = "Someone"
        self.re_replace = re.compile(r".*?({{.+?}})")
        self.re_verb = re.compile(r".*?<([^>]+)>")

        # dict of room ids to factoid: (text, value, verb) tuples
        self.prevFactoid = {}

    class FactoidDb:
        """Class to handle the factoid sqlite database"""

        def __init__(self, dbfile):
            # in principle this will make a new db if it doesn't exist
            # that's never actually been tried though
            self.dict = {}
            self.dbfile = dbfile

            try:
                open(dbfile)
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

        def add(self, key, value, by, verb="is"):
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

        def remove(self, key, value, by, verb):
            con = sqlite3.connect(self.dbfile)
            # con.text_factory = str
            c = con.cursor()
            c.execute(
                """DELETE FROM factoids WHERE fact LIKE ? AND verb = ? AND tidbit = ? """, (key, verb, value),
            )
            con.commit()
            c.close()
            con.close()

        def getall(self, key):
            con = sqlite3.connect(self.dbfile)
            # con.text_factory = str
            c = con.cursor()
            c.execute(
                """SELECT verb, tidbit, by FROM factoids WHERE fact = ? COLLATE NOCASE""", (key,),
            )

            vals = c.fetchall()

            c.close()
            con.close()
            return vals

        def getrandom(self, key):
            return random.choice(self.getall(key))

        def __len__(self):
            con = sqlite3.connect(self.dbfile)
            c = con.cursor()
            c.execute("""SELECT Count(*) FROM factoids""")
            val = c.fetchone()[0]

            c.close()
            con.close()
            return val

    def process_message(self, message):
        atme = False
        self.who = message.author.name
        self.utils.people.add(self.who)
        result = ""

        try:
            room = message.channel.name
            DM = False
        except AttributeError:  # no channel name, it's a DM
            DM = True
            atme = True  # DMs are always addressed to you
            self.log.info(self.class_name, msg="At me because DM")
            room = message.channel.recipient.id

        text = message.clean_content

        if self.is_at_me(message):
            atme = True
            text = self.is_at_me(message)

        factoids = self.db.getall(text)
        key = text

        re_factoid_request = re.compile(
            r"""(([Ww]hat)('s| is| are| do you know about| can you tell me about)) (?P<query>.+)\?"""
        )
        m = re.match(re_factoid_request, text)
        if m:
            query = m.group("query")
            query = re.sub(r"\bmy\b", f"{self.who}'s", query)
            query = re.sub(r"\bme\b", self.who, query)
            self.log.info(self.class_name, query=query)

            if not factoids:
                key = query

            factoids += self.db.getall(query)

        # forgetting factoids
        if (room in self.prevFactoid) and atme and (text == "forget that"):
            pf = self.prevFactoid[room]
            del self.prevFactoid[room]
            self.db.remove(*pf)
            if room == "stampy-dev":
                result = "debug: %s\n" % str(pf)
            result += """Ok %s, forgetting that "%s" %s "%s"\n""" % (self.who, pf[0], pf[3], pf[1],)
            why = """%s told me to forget that "%s" %s "%s"\n""" % (self.who, pf[0], pf[3], pf[1],)
            return Response(confidence=10, text=result, why=why)

        # if the text is a valid factoid, maybe reply
        elif factoids and (atme or randbool(0.3)):
            verb, rawvalue, by = random.choice(factoids)

            value = self.dereference(rawvalue)

            if verb == "reply":
                result = value
            else:
                result = "%s %s %s" % (re.sub(f"{self.who}'s", "your", key), verb, value)

            why = '%s said the factoid "%s" so I said "%s"' % (self.who, key, rawvalue,)
            self.prevFactoid[room] = (key, rawvalue, by, verb)  # key, value, verb
            if atme:
                return Response(confidence=9, text=result, why=why)
            else:
                return Response(confidence=8, text=result, why=why)

        # handle adding new factoids
        elif text.lower().startswith("remember") or text.startswith("sr "):
            if DM and not is_bot_dev(message.author):
                return Response(
                    confidence=2,
                    text="Sorry, I don't remember things in DMs",
                    why=f"{message.author} was trying to save a factoid in a DM",
                )
            else:
                isadd = True
                withbrackets = False
                verbmatch = self.re_verb.match(text)
                if verbmatch:
                    withbrackets = True
                    verb = verbmatch.group(1)
                elif " is " in text:
                    verb = "is"
                elif " are " in text:
                    verb = "are"
                else:  # we don't have a verb, this isn't a valid add command
                    verb = ""
                    isadd = False

                if isadd:
                    text = text.partition(" ")[2]  # Chop off the 'remember' or 'sr'
                    if withbrackets:
                        key, _, value = text.partition(" <%s> " % verb)
                    else:
                        key, _, value = text.partition(" %s " % verb)

                    key = re.sub(r"\bmy\b", f"{self.who}'s", key)

                    new_key = re.sub(r"\bI\b", f"{self.who}", key)
                    if new_key != key:
                        key = new_key
                        if verb == "am":
                            verb = "is"

                    result = """Ok %s, remembering that "%s" %s "%s" """ % (self.who, key, verb, value,)
                    why = "%s told me to remember that '%s' %s '%s'" % (self.who, key, verb, value,)
                    self.log.info(
                        self.class_name,
                        msg="adding factoid %s : %s" % (key, value),
                        author=message.author.id,
                        verb=verb,
                    )
                    self.db.add(key, value, message.author.id, verb)
                    self.prevFactoid[room] = (key, value, message.author.id, verb)
                    return Response(confidence=10, text=result, why=why)

        # some debug stuff, listing all responses for a factoid
        elif text.startswith("list ") or text.startswith("listall "):
            lword, _, fact = text.partition(" ")
            values = self.db.getall(fact)
            if values:
                random.shuffle(values)  # is this the right thing to do here?
                result = "%s values for factoid '%s':" % (len(values), fact)
                count = 200 if (lword == "listall" and is_bot_dev(message.author)) else 10
                for value in values[:count]:
                    result += "\n<%s> '%s' by %s" % value
                if len(values) > count:
                    result += "\n and %s more" % (len(values) - count)
                why = "%s asked me to list the values for the factoid '%s'" % (self.who, fact,)
                return Response(confidence=10, text=result, why=why)

        # This is either not at me, or not something we can handle
        return Response(confidence=0, text="")

    def __str__(self):
        return "Factoids"

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                question="remember chriscanal is the person who wrote this test",
                expected_response='Ok stampy, remembering that "chriscanal" is "the person who wrote this test"',
            ),
            self.create_integration_test(question="list chriscanal", expected_regex="values for factoid+",),
            self.create_integration_test(
                question="forget that",
                expected_response='Ok stampy, forgetting that "chriscanal" is "the person who wrote this test"',
            ),
        ]
