import os
import re
from typing import Optional


HELP_FILE_START_TEXT = """\
# Stampy commands

This file ~~lists~~ *will list (at some point [WIP])* all available commands for Stampy, divided according to which module handles them.

Whenever you add a new feature to Stampy or meaningfully modify some feature in a way that may alter how it acts, please update this file and test manually whether Stampy's behavior follows the specification."""

_re_module_name = re.compile(r"(?:\nclass\s)(\w+)(?:\(Module\))")

ModuleName = DocString = str


def get_module_docstring(module_fname: str) -> Optional[tuple[ModuleName, DocString]]:
    """Get the name of the `Module` defined in the file and its docstring."""
    with open(f"modules/{module_fname}", "r", encoding="utf-8") as f:
        code = f.read()

    # If the first line doesn't start with docstring, skip
    if '"""' not in code.split("\n")[0]:
        return
    # If there is no class that inherits from `Module`, skip
    if not (match := _re_module_name.search(code)):
        return

    # Extract docstring
    docstring_start = code.find('"""')
    docstring_end = code.find('"""', docstring_start + 3)
    docstring = code[docstring_start + 3 : docstring_end].strip()

    # Extract module name
    module_name = match.group(1)
    return module_name, docstring


def main() -> None:
    # get module filenames
    module_fnames = [
        fname
        for fname in os.listdir("modules")
        if fname.endswith(".py") and fname != "__init__.py"
    ]

    # build help file text
    help_file_text = HELP_FILE_START_TEXT
    for fname in module_fnames:
        if result := get_module_docstring(fname):
            module_name, docstring = result
            help_file_text += f"\n\n## {module_name}\n\n{docstring}"

    # save it
    with open("help.md", "w", encoding="utf-8") as f:
        f.write(help_file_text)


if __name__ == "__main__":
    main()
