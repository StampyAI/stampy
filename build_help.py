from pathlib import Path

from utilities.help_utils import build_help_md


def main() -> None:
    help_md = build_help_md(Path("modules"))
    with open("help.md", "w", encoding="utf-8") as f:
        f.write(help_md)


if __name__ == "__main__":
    main()
