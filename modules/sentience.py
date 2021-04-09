from modules.module import Module


class Sentience(Module):
    def process_message(self, message, client=None):
        return 0.0000001, "I don't understand"

    def can_process_message(self, message, client=None):
        return 0.0000001, "I don't understand"


sentience = Sentience()
