from modules.module import Module, Response


class Sentience(Module):
    def process_message(self, message, client=None):
        if self.is_at_me(message):
            return Response(confidence=0.0000001, text="I don't understand")
        else:
            return Response()

    def __str__(self):
        return "Sentience"


sentience = Sentience()
