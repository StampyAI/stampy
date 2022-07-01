import os
from unittest import TestCase
from stam import get_stampy_modules


class TestStam(TestCase):
    def test_get_stampy_modules(self):
        modules = get_stampy_modules()
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "modules")
        module_file_count = len([file for file in os.listdir(path) if ".py" in file]) - 2
        self.assertEqual(len(modules), module_file_count)
