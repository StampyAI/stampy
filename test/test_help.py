from pathlib import Path
from unittest import TestCase

from utilities.help_utils import build_help_md


class TestHelp(TestCase):
    def test_build_help_md(self):
        help_md = build_help_md(Path("modules"))
        self.assertGreater(len(help_md), 100)
