from unittest import TestCase
from utilities import Utilities
from api.semanticwiki import SemanticWiki
from modules.questions import QQManager
from stand_alone_stampy import stampy_response

q = QQManager()


class Test(TestCase):
    def test_stampy_response(self):
        test_question = "how many questions are in the queue?"
        expected_response = q.question_count_response(Utilities.get_instance().get_question_count())
        response = stampy_response(test_question, "test_author", "test_channel")
        self.assertEqual(response.text, expected_response)
