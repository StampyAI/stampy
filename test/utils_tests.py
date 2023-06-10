from unittest import TestCase
from utilities.utilities import Utilities


class UtilsTests(TestCase):
    def test_split_message_for_discord(self):
        test_out = Utilities.split_message_for_discord(
            "123456789012345\n1234567890123456789\n10\n10\n10\n01234567890123456789",
            max_length=20,
        )
        self.assertEqual(len(test_out), 4)
        for chunk in test_out:
            self.assertLessEqual(len(chunk), 20)
