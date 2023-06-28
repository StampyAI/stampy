"""
Helps you interact with me

List modules
List what modules I have + short descriptions
`s, list modules`

Help
You can ask me for help with (1) a particular module or (2) a particular command defined on a module
`s, help <module-name>` - returns description of a module and lists all of its commands
`s, help <command-name>` - returns description of a command
"""
from itertools import islice
import re
from textwrap import dedent

from modules.module import IntegrationTest, Module, Response
from utilities.serviceutils import ServiceMessage


class HelpModule(Module):
    STAMPY_HELP_MSG = dedent(
        """\
        If you'd like to get a general overview of my modules, say `s, list modules`
        For a description of a module and what commands are available for it, say `s, help <module-name>`
        For a detailed description of one of those commands say `s, help <command-name>` (where `command-name` is any of alternative names for that command)"""
    )

    def __init__(self):
        super().__init__()
        self.re_help = re.compile(r"help \w+", re.I)

    def process_message(self, message: ServiceMessage) -> Response:
        if not (text := self.is_at_me(message)):
            return Response()
        if text.casefold() == "list modules":
            return Response(
                confidence=10,
                text=self.list_modules(),
                why=f"{message.author.display_name} asked me to list my modules",
            )
        if text.casefold() == "help":
            return Response(
                confidence=10,
                text=self.STAMPY_HELP_MSG,
                why=f"{message.author.display_name} asked me for generic help",
            )
        if self.re_help.match(text):
            return Response(confidence=10, callback=self.cb_help, args=[text, message])

        return Response()

    def list_modules(self) -> str:
        msg_descrs = sorted(
            (mod.help.listed_descr for mod in self.utils.modules_dict.values()),
            key=str.casefold,
        )
        return "I have the following modules:\n" + "\n".join(msg_descrs)

    async def cb_help(self, msg_text: str, message: ServiceMessage) -> Response:
        help_content = msg_text[len("help ") :]
        # iterate over modules, sorted in reverse in order to put longer module names first to prevent overly eager matching
        for mod_name, mod in sorted(self.utils.modules_dict.items(), reverse=False):
            if cmd_help := mod.help.get_command_help(msg_text=help_content):
                return Response(
                    confidence=10,
                    text=cmd_help,
                    why=f'{message.author.display_name} asked me for help with "{help_content}"',
                )
            # module help
            if mod_name.casefold() in help_content.casefold():
                mod_help = mod.help.get_module_help(markdown=False)
                why = f"{message.author.display_name} asked me for help with module `{mod_name}`"
                if mod_help is None:
                    msg_text = f"No help for module `{mod_name}`"
                    why += " but help is not written for it"
                else:
                    msg_text = mod_help
                return Response(confidence=10, text=msg_text, why=why)

        # nothing found
        return Response(
            confidence=10,
            text=f'I couldn\'t find any help info related to "{help_content}". Could you rephrase that?',
            why=f'{message.author.display_name} asked me for help with "{help_content}" but I found nothing.',
        )

    @property
    def test_cases(self) -> list[IntegrationTest]:
        module_help_tests = [
            self.create_integration_test(
                test_message=f"help {mod_name}",
                expected_regex=rf"\*\*Module `{mod_name}`\*\*",
            )
            for mod_name, mod in self.utils.modules_dict.items()
            if not mod.help.empty
        ]
        helpless_module_tests = list(
            islice(
                (
                    self.create_integration_test(
                        test_message=f"help {mod_name}",
                        expected_regex=f"No help for module `{mod_name}`",
                    )
                    for mod_name, mod in self.utils.modules_dict.items()
                    if mod.help.empty
                ),
                3,
            )
        )
        return (
            [
                self.create_integration_test(
                    test_message="list modules",
                    expected_regex=r"I have the following modules:(\n- `\w+`[^\n]*)+",
                ),
                self.create_integration_test(
                    test_message="help", expected_response=self.STAMPY_HELP_MSG
                ),
            ]
            + module_help_tests
            + helpless_module_tests
        )
