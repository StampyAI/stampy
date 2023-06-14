from unittest import TestCase

from config import enabled_modules
from stam import get_stampy_modules
from utilities import Utilities

class TestStam(TestCase):
    def test_get_stampy_modules(self):
        modules = get_stampy_modules()
        unavailable_module_names = Utilities.get_instance().unavailable_module_names
        uncounted_modules = frozenset(["module"]) # not all files in the dir stay loaded
        module_file_count = len(enabled_modules - uncounted_modules) + len(unavailable_module_names)
        self.assertEqual(len(modules), module_file_count)
