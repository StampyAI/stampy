from unittest import TestCase

from config import enabled_modules
from stam import get_stampy_modules
from utilities import Utilities


class TestStam(TestCase):
    def test_get_stampy_modules(self):
        modules = get_stampy_modules()
        unavailable_module_names = Utilities.get_instance().unavailable_module_names
        enabled_modules_count = len(enabled_modules)
        found_modules_count = len(modules) + len(unavailable_module_names)
        self.assertEqual(
            enabled_modules_count,
            found_modules_count,
            f"\nenabled_modules={sorted(enabled_modules, key=str.casefold)}\n"
            f"modules={sorted(modules, key=str.casefold)}\n"
            f"unavailable_modules={sorted(unavailable_module_names, key=str.casefold)}",
        )
