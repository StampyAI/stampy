import re
import random
from modules.module import Module, Response

from utilities.utilities import Utilities, randbool

utils = Utilities.get_instance()

class Random(Module):
    def process_message(self, message):
        atme = self.is_at_me(message)
        text = atme or message.clean_content
        who = message.author.name

        # dice rolling
        if re.search("^roll [0-9]+d[0-9]+$", text):
            result = None
            count, _, sides = text.partition(" ")[2].partition("d")
            count = max(1, int(count))
            sides = max(1, int(sides))
            rolls = []
            total = 0
            if sides > 100000:
                result = "WriteError: No space left on dice"
            elif count > 100:
                result = "OutOfDiceError"
            else:
                rolls = [1 + random.choice(range(sides)) for x in range(count)]
                total = sum(rolls)

            if rolls:
                if count == 1:
                    result = f"{who} rolled: {total}"
                else:
                    rolls = ", ".join([str(r) for r in rolls])
                    result = f"{who} rolled: {rolls}\nTotal: {total}"

            if result:
                return Response(
                    confidence=9, text=result, why=f"{who} asked me to roll {count} {sides}-sided dice"
                )

        # "Stampy, choose coke or pepsi or both"
        elif text.startswith("choose ") and " or " in text:
            # repetition guard
            if atme and utils.message_repeated(message, text):
                self.log.info(
                    self.class_name, msg="We don't want to lock people in due to phrasing"
                )
                return Response()
            cstring = text.partition(" ")[2].strip("?")
            # options = [option.strip() for option in cstring.split(" or ")]  # No oxford commas please
            options = [option.strip() for option in re.split(" or |,", cstring) if option.strip()]
            return Response(
                confidence=9,
                text=random.choice(options),
                why="%s asked me to choose between the options [%s]" % (who, ", ".join(options)),
            )

    def __str__(self):
        return "Random"
