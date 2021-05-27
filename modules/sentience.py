from modules.module import Module, Response


class Sentience(Module):
    # def process_message(self, message, client=None):
    #     return 0.0000001, "I don't understand"

    # def can_process_message(self, message, client=None):
    #     return 0.0000001, "I don't understand"

    def process_message(self, message, client=None):
        if message.clean_content == "test1":
            return Response(text="You said test1", confidence=4)
        elif message.clean_content == "callback":
            return Response(callback=self.my_callback, args=["stringarg1"], confidence=8)
        elif message.clean_content == "async":
            return Response(
                callback=self.my_async_callback, args=["stringarg2"], kwargs={"kw": 7}, confidence=8
            )

    def my_callback(self, input_string):
        print("my callback")
        return Response(text="callback with arg %s" % input_string, confidence=5)

    async def my_async_callback(self, input_string, kw=None):
        print("my async callback", kw)
        return Response(text="async callback with arg %s" % input_string, confidence=5)

    def __str__(self):
        return "Sentience"


sentience = Sentience()
