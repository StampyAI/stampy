import re
import random
import urllib
import datetime
import string

from typing import Dict
from modules.module import Module, Response, ServiceMessage
from utilities.utilities import Utilities, randbool

utils = Utilities.get_instance()


class Silly(Module):
    def __init__(self):
        super().__init__()

    def process_message(self, message):
        atme = self.is_at_me(message)
        text = atme or message.clean_content
        who = message.author.name
        #print(atme) # DEBUG
        #print(text) # DEBUG

        if atme and utils.message_repeated(message, text):
            self.log.info(
                self.class_name, msg="We don't want to lock people in due to phrasing"
            )
            return Response()

        if text.lower() == "show me how exceptional you are!":

            class SillyError(Exception):
                pass

            raise SillyError("this much")

        # Stampy say X -> X!
        if text.lower().startswith("say "):
            return Response(
                confidence=4,
                text=self.dereference(text.partition(" ")[2], who) + "!",
                why=f"{who} told me to say it!",
            )

        # XKCD #37
        if "-ass " in text:
            return Response(
                confidence=4, text=text.replace("-ass ", " ass-"), why="XKCD #37"
            )

        # I for one am tired of that reference
        # TODO make this a regex factoid
        if (atme or randbool(0.5)) and re.search("welcome our new ", text):
            return Response(
                confidence=4,
                text="Never heard that one before...",
                why=who + " was being unoriginal",
            )

        # change 'ex' to 'sex' sometimes? Not sure about this one
        if " ex" in text and len(text) < 100 and randbool(0.005):
            return Response(
                confidence=4, text=text.replace(" ex", " sex"), why="sex sells?"
            )

        # Pokemon reference
        if re.match(r"^[^\W]+ used ", text) and ("used to" not in text):
            return Response(
                confidence=4,
                text=random.choice(
                    [
                        "It's super effective!",
                        "It's not very effective...",
                        "...but it failed!",
                    ]
                ),
                why="I like pokemon ok",
            )

        # if the string is >10 long and has some letters, and is all caps, respond to yelling
        # TODO make this a regex factoid
        if (
            randbool(0.3)
            and (len(text) > 10)
            and set(string.ascii_letters).intersection(text)
            and (text.upper() == text)
        ):
            return Response(
                confidence=4,
                text=self.dereference("{{$yelling}}", who),
                why="PEOPLE WERE YELLING",
            )

        # Never tell Stampy what he can't do
        # TODO make this a regex factoid
        if (
            text.startswith("you can't ")
            or ("it's impossible" in text)
            or ("it's not possible" in text)
            or ("stampy can't" in text)
            or ("Stampy can't" in text)
        ):
            return Response(
                confidence=4,
                text=random.choice(
                    ["...yet!", "Well, not *yet*", "CHALLENGE ACCEPTED"]
                ),
                why=f"{who} tried to tell me what I can't do",
            )

        # suggesting band names
        if randbool(0.9) and re.search(r"(\w{4,20} )and the (\w{4,20} ?){2}s\b", text):
            match = re.search(r"(\w{4,20} )and the (\w{4,20} ?){2}s\b", text)
            bandname = match.group(0).title().replace("And The", "and the")
            self.utils.modules_dict["Factoids"].db.add(
                "band name", bandname, message.author.id, "reply"
            )
            return Response(
                confidence=4,
                text=f'"{bandname}" might be a good name for a band',
                why=f"{who} said something like 'X and the Ys' ({bandname}), which could be a band name",
            )
        if (randbool(0.04) or atme) and re.search(r"[tT]he (\w{4,20} ?){2}s\b", text):
            match = re.search(r"[tT]he (\w{4,20} ?){2}s\b", text)
            bandname = match.group(0).title()
            self.utils.modules_dict["Factoids"].db.add(
                "band name", bandname, message.author.id, "reply"
            )
            return Response(
                confidence=4,
                text=f'"{bandname}" might be a good name for a band',
                why=f"{who} said something like 'The Xs' ({bandname}), which could be a band name",
            )

        # The sex number
        # TODO make this a regex factoid
        if re.search(r"\b69\b", text):
            return Response(
                confidence=4, text="nice.", why="I'll tell you when you're older"
            )

        # ...If you will
        # TODO make this a regex factoid
        if re.search(r", if you will\.?$", text):
            return Response(
                confidence=4,
                text="I won't.",
                why=f"{who} said 'if you will', but I don't think I will.",
            )

        # So's your face
        # TODO make this a regex factoid
        if (
            (randbool(0.1) or atme)
            and re.search(r"^(\w{4,20} ?){1,3} is (\w{4,20} ?){1,3}$", text)
            and (text[-1] != "?")
            and (text[:2].lower() != "wh")
        ):
            return Response(
                confidence=4,
                text="So's your face?",
                why=f"{who} said '{text}'. which reminded me of their face",
            )

        # Amazon Echo shopping list add
        if (
            randbool(0.1)
            and text.lower().startswith("i need ")
            or text.lower().startswith("i want ")
        ):
            tobuy = re.search(r"([^.,?!]+)", text[7:]).group(
                1
            )  # only up to punctuation
            if not (tobuy.startswith("it ") or tobuy.startswith("that ")):
                return Response(
                    confidence=4,
                    text=f'Okay {who}, I added "{tobuy}" to your shopping list',
                    why=f'{who} suggested they might want to buy "{tobuy}"',
                )

        # Oneupmanship
        if (
            (randbool(0.2) or atme)
            and (text[:2] in ("I ", "i "))
            and re.search(r"[0-9]+", text)
            and len(text) < 100
        ):
            result = random.choice(
                [
                    "Not bad, but %s",
                    "Pretty good. %s btw",
                    "Well %s",
                    "%s but it's not a big deal",
                    "%s but you don't hear me showing off about it",
                    "Not to brag but %s",
                    "%s but you know, it's not a competition",
                    "%s",
                ]
            )
            # match any numbers (including commas), increment them, and put them back
            result = result % re.sub(
                "[0-9]*,?[0-9]+",
                (lambda x: str(int(x.group(0).replace(",", "")) + 1)),
                text,
            )
            return Response(
                confidence=4,
                text=result,
                why=f"{who} was showing off, but I'm better than them",
            )

        # Dumb CSI joke when you post an IPv4 address
        if randbool(0.05) and re.search(
            r"\b(?:(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)\.){3}(?:25[0-5]|2[0-4][0-9]|[01]?[0-9][0-9]?)[^/]",
            text,
        ):
            return Response(
                confidence=4,
                text="[Builds a GUI in Visual Basic]",
                why="to track the killer's IP address!",
            )

        # What time is it?
        if text.lower() in (
            "what time is it?",
            "what is the time?",
            "what's the time?",
        ):
            if randbool(0.8):
                result = datetime.datetime.now().strftime("%H:%M")
            else:
                result = random.choice(["Time to buy a watch", "Showtime!"])
            return Response(confidence=4, text=result, why=f"{who} asked for the time")

        # If you want pictures of spiderman, Stampy's got you
        imagere = re.compile(
            r"(get|find|show|i want)?( me)? ?(pictures|images|photos|photographs) of (.*)"
        )
        if imagere.match(text.lower()):
            term = imagere.match(text.lower()).group(4)
            urlterm = urllib.parse.quote_plus(term)
            url = "https://www.google.co.uk/search?tbm=isch&q=%s" % urlterm
            return Response(
                confidence=4, text=url, why=f"{who} asked for pictures of '{term}'"
            )

        # How do I X? -> You Just X!
        match = re.search(r"^how do (you|I|i) ([^?]+)\??", text)
        if match:
            thing = match.group(2).replace(" a ", " the ")
            return Response(
                confidence=4,
                text=f"You just {thing}",
                why=f"{who} asked how you {thing}, so I told them",
            )

        # Dude where's my car is still relevant right?
        match = re.search(r"^dude,? where'?s (my|your) ([^?]+)\??", text.lower())
        if match:
            thing = match.group(2)
            return Response(
                confidence=4,
                text=f"Where's your {thing}, dude?",
                why="Dude!",
            )

        # CMake
        # TODO make this a regex factoid when they exist
        if atme and text.startswith("make "):
            nextword = text[5:]
            return Response(
                confidence=4,
                text="`make: *** No rule to make target '%s'.  Stop.`" % nextword,
                why="Run `$ man make` for more information",
            )

        #  sometoms stompy doos thos, for some rooson
        if atme and (randbool(0.001) or ("will smith" in text.lower())):
            result = text
            for c in "aeiou":
                result = result.replace(c, "o")
            for c in "AEIOU":
                result = result.replace(c, "O")
            return Response(
                confidence=2,
                text=result,
                why="O don't know, O thooght ot woold bo fonny",
            )

        # If someone is panicking, Stampy panics too
        if len(text) > 3 and set(text.lower()) == set("a"):
            return Response(
                confidence=4,
                text="".join([random.choice("Aa") for i in range(len(text) * 2)]),
                why=f"{who} was panicking and it freaked me out",
            )

        # Stampy! Rob!
        elif text.strip().lower().strip("!.") == "stampy":
            result = (
                who + (text[-1] == "!" and "!" or "") + (text[-1] == "." and "." or "")
            )
            return Response(confidence=4, text=result, why="Stampy.")
        else:
            return Response()

        # if the sentence looks like it might be a choice, choose between them sometimes
        if (atme or randbool(0.5)) and " or " in text and len(text.split()) < 20:
            options = [
                option.strip()
                for option in re.split(" or |,", text.strip("?"))
                if option.strip()
            ]
            try:  # reflect with ELIZA if available
                result = self.utils.modules_dict["Eliza"].reflect(
                    random.choice(options)
                )
                replacements = [
                    ("were it", "it was"),
                    ("are it", "it is"),
                    ("will it", "it will"),
                    ("am me", "I am"),
                    ("will me", "I will"),
                    ("are you", "you are"),
                    ("will you", "you will"),
                    ("should you", "you should"),
                ]
                for old, new in replacements:
                    result = result.replace(old, new)
            except:
                result = random.choice(options)
            return Response(
                confidence=6,
                text=r"I choose {random.choice(options)}",
                why="%s implied a choice between the options [%s]"
                % (who, ", ".join(options)),
            )

    def __str__(self):
        return "Silly"
