from unittest import TestCase

from config import enabled_modules as enabled_module_filenames
from stam import get_stampy_modules
from utilities import Utilities


class TestStam(TestCase):
    def test_get_stampy_modules(self):
        stampy_module_classnames = frozenset(get_stampy_modules())

        unavailable_module_filenames = Utilities.get_instance().unavailable_module_filenames  # fmt:skip
        enabled_modules_count = len(enabled_module_filenames)

        found_modules_count = len(stampy_module_classnames) + len(unavailable_module_filenames)  # fmt:skip

        enabled_msg = sorted(enabled_module_filenames, key=str.casefold)
        modules_msg = sorted(stampy_module_classnames, key=str.casefold)
        unavailable_msg = sorted(unavailable_module_filenames, key=str.casefold)
        self.assertEqual(
            enabled_modules_count,
            found_modules_count,
            f"\nenabled_module_filenames={enabled_msg}\n"
            f"stampy_module_classnames={modules_msg}\n"
            f"unavailable_module_filenames={unavailable_msg}",
        )
