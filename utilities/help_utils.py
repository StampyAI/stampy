from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
from textwrap import dedent
from typing import Optional, overload


@dataclass(frozen=True)
class ModuleHelp:
    """Help for a particular Stampy module, parsed from the docstring placed at the top of the module file.

    ### Docstring specification

    If the module has no file-level docstring, then no problem. However, if it does, it must follow this specification.

    The docstring is divided into segments, defined as blocks of text separated by double newlines.
    The **main segment** contains an obligatory short module description (`descr`) and an optional, longer module description (`longdescr`).
    The main segment is followed by one or more **command segments**, each describing one specific command or a set of related commands:
    what they do and how to use them. A detailed specification of command segments can be found in the docstring of the `CommandHelp` class.
    """

    module_name: str
    descr: Optional[str]
    longdescr: Optional[str]
    commands: list[CommandHelp]

    @classmethod
    def from_docstring(cls, module_name: str, docstring: Optional[str]) -> ModuleHelp:
        """Parse help from docstring"""
        if docstring is None:
            return cls(module_name, None, None, [])
        main_segment, *cmd_segments = re.split(r"\n{2,}", docstring.strip())
        if "\n" in main_segment:
            descr, longdescr = main_segment.split("\n", 1)
        else:
            descr = main_segment
            longdescr = None
        commands = [CommandHelp.from_docstring_segment(segm) for segm in cmd_segments]
        return cls(module_name, descr, longdescr, commands)

    @property
    def empty(self) -> bool:
        return self.descr is None

    @property
    def listed_descr(self) -> str:
        """Bulletpoint: module name followed by short description (if it exists)"""
        if self.descr:
            return f"- `{self.module_name}`: {self.descr}"
        return f"- `{self.module_name}`"

    def get_module_name_header(self, *, markdown: bool) -> str:
        """Get formatted header with module name"""
        if markdown:
            return f"## {self.module_name}"
        return f"**Module `{self.module_name}`**"

    def get_command_help(self, msg_text: str) -> Optional[str]:
        """Search for help for command mentioned in `msg_text`. If found, return it. Otherwise, return `None`."""
        if self.empty:
            return
        # iterate over commands
        for cmd in self.commands:
            # if some name of the command matches msg_text
            if command_help_msg := cmd.get_help(msg_text, markdown=False):
                return (
                    f"{self.get_module_name_header(markdown=False)}\n{command_help_msg}"
                )

    def get_module_help(self, *, markdown: bool) -> Optional[str]:
        """Get help for the module formatted either for markdown file or for Discord message.
        If help is empty, return `None`.
        """
        if self.empty:
            return
        segments = [self.get_module_name_header(markdown=markdown), self.descr]
        if self.longdescr is not None:
            segments.append(self.longdescr)
        segments = ["\n".join(segments).replace("\n", "\n\n" if markdown else "\n")]
        if self.commands:
            segments.extend(
                cmd.get_help(msg_text=None, markdown=markdown) for cmd in self.commands
            )
        return "\n\n".join(segments)


@dataclass(frozen=True)
class CommandHelp:
    """Help for a Stampy command doing a particular thing.
    Parsed from a segment of the docstring placed at the top of the module file.

    ### Segment structure

    - First line - `name` of the command, optionally alternative names (`alt_names`) following it, interspersed with commas
    - Second line - short description (`descr`) of the command
    - Next lines
        - `Code-styled` lines are parsed as `examples` of commands (it's advised to follow them with descriptions after hyphens)
        - Lines that are not `code-styled` are parsed and concatenated into longer description (`longdescr`) of the command
    - Remarks
        - There must be no blank lines between the above
        - You technically can mix `examples` lines with `longdescr` lines but please don't. If you write both, either put all `examples` first or `longdescr` first.

    ### Example

    ```md
    Do something, Do sth
    Stampy does something
    A longer description of
    how Stampy does something
    `s, do sth` - Stampy does sth
    `s, do something because of <x>` - Stampy does something because of "x"
    ```
    """

    name: str
    alt_names: list[str]
    descr: str
    longdescr: Optional[str]
    examples: list[str]

    @classmethod
    def from_docstring_segment(cls, segment: str) -> CommandHelp:
        """Parse `CommandHelp` from a segment of the docstring describing one command"""
        lines = segment.splitlines()
        # TODO: improve
        assert (
            len(lines) >= 3
        ), f"Must have at least a name (1), a description (2), and an example (3);\n{lines=}"
        name_line, descr = lines[:2]
        name, alt_names = cls.parse_name_line(name_line)
        longdescr = "\n".join(l for l in lines[2:] if not l.startswith("`")) or None
        examples = [l for l in lines[2:] if l.startswith("`")]
        return cls(
            name=name,
            alt_names=alt_names,
            descr=descr,
            longdescr=longdescr,
            examples=examples,
        )

    @staticmethod
    def parse_name_line(line: str) -> tuple[str, list[str]]:
        """Parse the first line of a segment, containing main name of the command and optional alternative names"""
        names = re.split(r",\s*", line)
        assert names
        name, *alt_names = names
        return name, alt_names

    @property
    def all_names(self) -> list[str]:
        """Main name and alternative names in one list"""
        return [self.name, *self.alt_names]

    def get_fmt_name_lines(
        self, *, markdown: bool, matched_name: Optional[str] = None
    ) -> str:
        """Get formatted name line, differently for markdown and not markdown.
        If `matched_name` is passed, bold it.

        ### `markdown = False`

        ```md
        ### <main-name>

        (<alt-name-1>, <alt-name-2>, ...)
        ```

        ### `markdown = True`

        `<main-name> (<alt-name-1>, <alt-name-2>, ...)`
        """
        out = self.name
        if markdown:
            out = f"### {out}"
            if self.alt_names:
                out += "\n\n(" + ", ".join(self.alt_names) + ")"
        elif self.alt_names:
            out += " (" + ", ".join(self.alt_names) + ")"
        if matched_name:
            assert matched_name in out, f"{matched_name = }; {out = }"
            out = out.replace(matched_name, f"**{matched_name}**")
        return out

    # fmt:off
    @overload
    def get_help(self, msg_text: str, markdown: bool) -> Optional[str]:...
    @overload
    def get_help(self, msg_text: None, markdown: bool) -> str:...
    # fmt:on
    def get_help(self, msg_text: Optional[str], markdown: bool) -> Optional[str]:
        """Get help for this command, if one of its names appears in `msg_text`. Otherwise, return `None`."""
        if msg_text:
            if not (matched_name := self._name_match(msg_text)):
                return
            name_lines = self.get_fmt_name_lines(
                markdown=markdown, matched_name=matched_name
            )
        else:
            name_lines = self.get_fmt_name_lines(markdown=markdown)
        lines = [name_lines, self.descr]
        if self.longdescr:
            lines.append(self.longdescr)
        lines.extend(self.examples)
        joiner = "\n\n" if markdown else "\n"
        return joiner.join(lines)

    def _name_match(self, msg_text: str) -> Optional[str]:
        """check if any of this command's names appears in `msg_text`"""
        for name in self.all_names:
            if re.search(rf"(?<!\w){name}(?!\w)", msg_text, re.I):
                return name


#################
# Build Help MD #
#################


def build_help_md(modules_dir: Path) -> str:
    modules_with_docstrings = load_modules_with_docstrings(modules_dir)
    helps = []
    for module_name, docstring in sorted(
        modules_with_docstrings.items(), key=lambda x: x[0].casefold()
    ):
        help = ModuleHelp.from_docstring(module_name, docstring)
        if not help.empty:
            helps.append(help.get_module_help(markdown=True))
    return HELP_MD_HEADER + "\n\n".join(helps)


def load_modules_with_docstrings(modules_dir: Path) -> dict[str, str]:
    modules_with_docstrings = {}
    for fname in os.listdir(modules_dir):
        if fname.startswith("_") or fname == "module.py":
            continue
        with open(modules_dir / fname, "r", encoding="utf-8") as f:
            code = f.read()
        if (module_name := extract_module_name(code)) and (
            docstring := extract_docstring(code)
        ):
            modules_with_docstrings[module_name] = docstring
    return modules_with_docstrings


HELP_MD_HEADER = dedent(
    """\
    # Stampy Module & Command Help
    
    This file was auto-generated from file-level docstrings in `modules` directory. If you think it's out of sync with docstrings, re-generate it by calling `python build_help.py`. If docstrings are out of date with code, feel free to edit them or nag somebody with a `@Stampy dev` on the server.
    
    """
)


def extract_docstring(code: str) -> Optional[str]:
    if not (code.startswith('"""') and '"""' in code[3:]):
        return
    docstring_end_pos = code.find('"""', 3)
    assert docstring_end_pos != -1
    docstring = code[3:docstring_end_pos].strip()
    assert docstring
    return docstring


_re_module_name = re.compile(r"(?<=class\s)\w+(?=\(Module\):)", re.I)


def extract_module_name(code: str) -> Optional[str]:
    if match := _re_module_name.search(code):
        return match.group()
