"""
Helps you interact with me

list modules
list what modules I have + short descriptions
`s, list modules`

help
You can ask me for help with (1) a particular module or (2) a particular command defined on a module
`s, help <module-name>` - returns description of a module and 
 
"""

import re

from modules.module import Module, Response
from utilities.help_utils import ModuleHelp
from utilities.serviceutils import ServiceMessage


class HelpModule(Module):
    DEFAULT_HELP_RESPONSE = "#TODO: DEFAULT HELP RESPONSE"

    def __init__(self):
        super().__init__()
        self.help = ModuleHelp.from_docstring(self.class_name, __doc__)
        self.re_help = re.compile(r"help \w+", re.I)

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
        if self.re_help.match(text):
            return Response(confidence=10, callback=self.cb_help, args=[text, message])

        return Response()

    def list_modules(self) -> str:
        msg_descrs = sorted(
            (mod.help.descr_msg for mod in self.utils.modules_dict.values()),
            key=str.casefold,
        )
        return "I have the following modules:\n" + "\n".join(msg_descrs)

    async def cb_help(self, text: str, message: ServiceMessage) -> Response:
        help_content = text[len("help ") :]

        # iterate over modules
        for mod in self.utils.modules_dict.values():
            # command help
            # TODO: rename attr
            if mod_help := mod.help.get_help_for_command(msg_text=help_content):
                return Response(
                    confidence=10,
                    text=mod_help,
                    why=f'{message.author.name} asked me for help with "{help_content}"',
                )
            # module help
            if mod.class_name.casefold() in help_content.casefold():
                # TODO: help is empty
                msg_text = mod.help.get_help_for_module()
                return Response(
                    confidence=10,
                    text=msg_text,
                    why=f"{message.author.name} asked me for help with module `{mod.class_name}`",
                )

        # nothing found
        return Response(
            confidence=10,
            text=f'I couldn\'t find any help info related to "{help_content}". Could you rephrase that?',
            why=f'{message.author.name} asked me for help with "{help_content}" but I found nothing.',
        )
