from modules.module import Module, Response


class test_longmessage(Module):
    def __init__(self):
        super().__init__()
        self.class_name = self.__class__.__name__
    def process_message(self, message):
        if text := self.is_at_me(message):
            if text.startswith("send a long message"):
                self.log.info("test_longmessage", msg="horrifically long message sent")
                return Response(confidence=100, text=str([x for x in range(0, 25000)]), why="you told me to dude!")
            else:
                return Response()
        else:
            return Response()

    def __str__(self):
        return "test_longmessage"
