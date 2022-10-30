from unittest import TestCase
from servicemodules.serviceConstants import Services
from utilities.serviceutils import ServiceMessage, ServiceUser
from utilities import Utilities
from servicemodules.discord import DiscordHandler
from modules.Eliza import Eliza


class TestEliza(TestCase):
    def setUp(self):
        self.eliza = Eliza()
        self.create_mock_message = lambda author, text: ServiceMessage(
            "2", text, ServiceUser(author, author, "123"), "channel_name", Services.DISCORD
        )
        Utilities.get_instance().service_modules_dict[Services.DISCORD] = DiscordHandler()

    def test_init(self):
        self.assertEqual(self.eliza.class_name, "Eliza")

    def test_reflect(self):
        """
        function should convert a string to parrot it back
        'I am your friend' -> 'You are my friend' etc.
        """
        reflection = self.eliza.reflect("I am your friend")
        self.assertEqual(reflection, "you are my friend")

    def test_analyze(self):
        """
        function should return a response based on the input
        """
        response = self.eliza.analyze("I am your friend")
        self.assertIsInstance(response, str)

    def test_process_message(self):
        """
        function should return a response based on the input
        """
        message = self.create_mock_message("author_name", "stampy is x becomes")
        response = self.eliza.process_message(message)
        self.assertIsInstance(response.text, str)
