import os
from pathlib import Path
import re
from typing import Optional

from utilities.help_utils import ModuleHelp

MODULES_PATH = Path("modules/")

ModuleName = Docstring = str

FILE_HEADER = """# Stampy Module & Command Help\n\n"""


def extract_docstring(code: str) -> Optional[Docstring]:
    if not (code.startswith('"""') and '"""' in code[3:]):
        return
    docstring_end_pos = code.find('"""', 3)
    assert docstring_end_pos != -1
    docstring = code[3:docstring_end_pos].strip()
    assert docstring
    return docstring


_re_module_name = re.compile(r"(?<=class\s)\w+(?=\(Module\):)", re.I)


def extract_module_name(code: str) -> Optional[ModuleName]:
    if match := _re_module_name.search(code):
        return match.group()


def load_modules_with_docstrings() -> dict[ModuleName, Docstring]:
    modules_with_docstrings = {}
    for fname in os.listdir(MODULES_PATH):
        if fname.startswith("_") or fname == "module.py":
            continue
        with open(MODULES_PATH / fname, "r", encoding="utf-8") as f:
            code = f.read()
        if (module_name := extract_module_name(code)) and (
            docstring := extract_docstring(code)
        ):
            modules_with_docstrings[module_name] = docstring
    return modules_with_docstrings


def main() -> None:
    modules_with_docstrings = load_modules_with_docstrings()
    helps = []
    for module_name, docstring in modules_with_docstrings.items():
        help = ModuleHelp.from_docstring(module_name, docstring)
        if not help.empty:
            helps.append(help.get_module_help(markdown=True))
    help_txt = FILE_HEADER + "\n\n".join(helps)
    with open("help.md", "w", encoding="utf-8") as f:
        f.write(help_txt)


if __name__ == "__main__":
    main()
