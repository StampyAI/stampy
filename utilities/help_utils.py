from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Optional

CommandAliases = tuple[str, ...]
CommandDescr = CommandExample = str
CapabilitiesDict = dict[CommandAliases, tuple[CommandDescr, CommandExample]]


@dataclass(frozen=True)
class CommandHelp:
    name: str
    alt_names: list[str]
    descr: str
    longdescr: Optional[str]
    cases: list[str]
    img_paths: list[str]  # TODO

    @staticmethod
    def parse_name_line(line: str) -> tuple[str, list[str]]:
        if alt_name_match := re.search(r"(?<=\().+(?=\))", line):
            name = line[: alt_name_match.span()[0] - 2].strip()
            alt_names = [an.strip() for an in alt_name_match.group().split(",")]
        else:
            name = line.strip()
            alt_names = []
        return name, alt_names

    @classmethod
    def from_docstring_segment(cls, segment: str) -> CommandHelp:
        lines = segment.splitlines()
        # TODO: improve
        assert (
            len(lines) >= 3
        ), "Must have at least a name (1), a description (2), and an example (3)"
        name_line, descr = lines[:2]
        name, alt_names = cls.parse_name_line(name_line)
        longdescr = lines[2] if not lines[2].startswith("`") else None
        cases = [l for l in lines[2:] if l.startswith("`")]
        return cls(
            name=name,
            alt_names=alt_names,
            descr=descr,
            longdescr=longdescr,
            cases=cases,
            img_paths=[],
        )

    @property
    def all_names(self) -> list[str]:
        return [self.name, *self.alt_names]

    @property
    def names_fmt(self) -> str:
        """Formatted names: `<main-name> (<alt-name1>, <alt-name2>, ...)`"""
        names_fmt = self.name
        if self.alt_names:
            names_fmt += " (" + "|".join(self.alt_names) + ")"
        return names_fmt

    def name_match(self, msg_text: str) -> Optional[str]:
        """check if any of this command's names appears in `msg_text`"""
        for name in self.all_names:
            if re.search(rf"(?<!\w){name}(?!\w)", msg_text, re.I):
                return name

    @property
    def help_msg(self) -> str:
        msg = f"{self.names_fmt}\n{self.descr}\n"
        if self.longdescr:
            msg += f"{self.longdescr}\n"
        msg += "\n".join(self.cases)
        return msg


@dataclass(frozen=True)
class ModuleHelp:
    module_name: str
    descr: Optional[str]
    longdescr: Optional[str]
    commands: list[CommandHelp]

    @classmethod
    def from_docstring(cls, module_name: str, docstring: Optional[str]) -> ModuleHelp:
        if docstring is None:
            return cls(module_name=module_name, descr=None, longdescr=None, commands=[])
        descr_segment, *command_segments = re.split(r"\n{2,}", docstring.strip())
        if "\n" in descr_segment:
            descr, longdescr = descr_segment.split("\n", 1)
        else:
            descr = descr_segment
            longdescr = None
        cmds = [
            CommandHelp.from_docstring_segment(segment) for segment in command_segments
        ]
        return cls(
            module_name=module_name, descr=descr, longdescr=longdescr, commands=cmds
        )

    @property
    def descr_msg(self) -> str:
        if self.descr is None:
            return f"- `{self.module_name}`"
        return f"- `{self.module_name}`: {self.descr}"

    @property
    def module_name_header(self) -> str:
        return f"Module `{self.module_name}`"

    def get_help_for_module(self) -> str:
        msg = f"{self.module_name_header}\n"
        if self.descr is not None:
            msg += f"{self.descr}\n"
            if self.longdescr is not None:
                msg += f"{self.longdescr}\n"
        else:
            msg += "No module description available\n"
        if self.commands:
            msg += "\n" + "\n\n".join(cmd.help_msg for cmd in self.commands)
        return msg

    def get_help_for_command(self, msg_text: str) -> Optional[str]:
        # iterate over commands
        for cmd in self.commands:
            # if some name of the command matches msg_text
            if cmd_name := cmd.name_match(msg_text):
                command_help_msg = cmd.help_msg.replace(cmd_name, f"**{cmd_name}**", 1)
                return f"{self.module_name_header}\n{command_help_msg}"
