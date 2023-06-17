import re
from modules.module import Module, Response
from utilities.serviceutils import ServiceMessage


class HelpModule(Module):
    DEFAULT_HELP_RESPONSE = "#TODO: DEFAULT HELP RESPONSE"

    def __init__(self):
        super().__init__()
        self.help = self.make_module_help(
            descr="Helps you interact with me",
            capabilities={
                ("list modules",): (
                    "list what modules I have + short descriptions",
                    "`<s, list modules>`",
                )
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
        if text == "help":
            return Response(
                confidence=10,
                text=self.DEFAULT_HELP_RESPONSE,
                why=f"{message.author.name} asked me for generic help",
            )
        if re.match(r"help \w+", text):
            return Response(confidence=10, callback=self.cb_help, args=[text, message])
        if re.match(r"docs \w+", text):
            return Response(confidence=10, callback=self.cb_docs, args=[text, message])

        return Response()

    def list_modules(self) -> str:
        msg_descrs = sorted(
            (mod.help.descr_msg for mod in self.utils.modules_dict.values()),
            key=str.casefold,
        )
        return "I have the following modules:\n" + "\n".join(msg_descrs)

    async def cb_help(self, text: str, message: ServiceMessage) -> Response:
        help_content = text[len("help ") :]
        for mod in self.utils.modules_dict.values():
            if mod_help := mod.help.get_help(text):
                return Response(
                    confidence=10,
                    text=mod_help,
                    why=f'{message.author.name} asked me for help with "{help_content}"',
                )
        return Response(
            confidence=10,
            text=f'I couldn\'t find any help info related to "{help_content}". Could you rephrase that?',
            why=f'{message.author.name} asked me for help with "{help_content}" but I found nothing.',
        )

    async def cb_docs(self, text: str, message: ServiceMessage) -> Response:
        module_names = self.utils.parse_module_names(text)
        if not module_names:
            return Response(
                confidence=10,
                text="I don't have such a module",
                why=f"{message.author.name} asked me for ",
            )
