import os
import re
from typing import Optional

_re_module_name = re.compile(r"(?:\nclass\s)(\w+)(?:\(Module\))")

ModuleName = DocString = str

# TODO: rename
MAIN_TEXT = """\
# Stampy commands

This file ~~lists~~ *will list (at some point [WIP])* all available commands for Stampy, divided according to which module handles them.

Whenever you add a new feature to Stampy or meaningfully modify some feature in a way that may alter how it acts, please update this file and test manually whether Stampy's behavior follows the specification."""


def get_module_docstring(fname: str) -> Optional[tuple[ModuleName, DocString]]:
    with open(f"modules/{fname}", "r", encoding="utf-8") as f:
        code = f.read()
    if '"""' not in code.split("\n")[0]:
        return
    docstring_start = code.find('"""')
    docstring_end = code.find('"""', docstring_start + 3)
    docstring = code[docstring_start + 3 : docstring_end].strip()
    if not (match := _re_module_name.search(code)):
        return
    module_name = match.group(1)
    return module_name, docstring


def main() -> None:
    module_fnames = [
        fname
        for fname in os.listdir("modules")
        if fname.endswith(".py") and fname != "__init__.py"
    ]

    help_file_text = MAIN_TEXT
    for fname in module_fnames:
        if result := get_module_docstring(fname):
            module_name, docstring = result
            help_file_text += f"\n\n## {module_name}\n\n{docstring}"

    with open("help.md", "w", encoding="utf-8") as f:
        f.write(help_file_text)


if __name__ == "__main__":
    main()
