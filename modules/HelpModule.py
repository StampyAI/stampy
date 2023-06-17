from modules.module import Module, Response
from utilities.serviceutils import ServiceMessage


class HelpModule(Module):
    def __init__(self):
        super().__init__()
        self.help = self.make_module_help(
            descr="Helps you interact with me",
            capabilities={
                "list what modules I have + short descriptions": "<s, list modules>"
            },
        )

    def process_message(self, message: ServiceMessage) -> Response:
        if not (text := self.is_at_me(message)):
            return Response()
        if text == "list modules":
            return Response(
                confidence=10,
                text=self.list_modules(),
                why=f"{message.author.name} asked me to list my modules",
            )
        # if text.startswith("help"):

        return Response()

    def list_modules(self) -> str:
        msg_descrs = sorted(
            mod.help.descr_msg for mod in self.utils.modules_dict.values()
        )
        return "I have the following modules:\n" + "\n".join(msg_descrs)
