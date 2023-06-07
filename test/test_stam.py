import os
from unittest import TestCase
from stam import get_stampy_modules
from config import enabled_modules

class TestStam(TestCase):
    def test_get_stampy_modules(self):
        modules = get_stampy_modules()
        uncounted_modules = frozenset(["module"]) # not all files in the dir stay loaded
        module_file_count = len(enabled_modules - uncounted_modules)
        self.assertEqual(len(modules), module_file_count)
