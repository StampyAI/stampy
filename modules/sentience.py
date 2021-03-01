from modules.module import Module


class Sentience(Module):
    def process_message(self, message, client=None):
        return 0, "I don't understand"


sentience = Sentience()
