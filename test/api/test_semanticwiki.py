from unittest import TestCase
from unittest.mock import MagicMock
from api.semanticwiki import SemanticWiki


class TestSemanticWiki(TestCase):
    def test_add_question(self):
        display_title = "Test Question"
        asker = "Test User"
        asked_time = "2020-01-01T00:00:00Z"
        text = "Test Question Text"
        response = {"query": {"tokens": {"csrftoken": "token", "logintoken": "token"}}}
        SemanticWiki.post = MagicMock(return_value=response)
        ftext = SemanticWiki(uri="https://none.fake", user=asker, api_key="1234").format_ftext(
            display_title,
            asker,
            asked_time,
            text,
            comment_url="",
            video_title="",
            likes=0,
            asked=False,
            reply_count=0,
        )
        self.assertEqual(
            ftext,
            "{{Question"
            + "|question=TestQuestionText"
            + "|notquestion=No"
            + "|canonical=No"
            + "|forrob=No"
            + "|asked=No"
            + "|asker=TestUser"
            + "|date=2020-01-01T00:00"
            + "|video="
            + "|ytlikes=0"
            + "|commenturl="
            + "|replycount=0"
            + "|titleoverride=TestQuestion}}",
        )
