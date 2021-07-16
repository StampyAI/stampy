from modules.module import Module, Response


class Sentience(Module):
    def process_message(self, message, client=None):
        return Response(confidence=0.0000001, text="I don't understand")

    def __str__(self):
        return "Sentience"


sentience = Sentience()
