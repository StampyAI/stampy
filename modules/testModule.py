import re
from time import sleep
from modules.module import Module
from jellyfish import jaro_winkler_similarity
from config import bot_dev_channel_id, ENVIRONMENT_TYPE, TEST_QUESTION_PREFIX, TEST_RESPONSE_PREFIX


class TestModule(Module):
    # This module is the only module that gets stampy to ask its self multiple questions
    # In test mode, stampy only responds to itself, whereas in other modes stampy responds only to not itself
    TEST_PREFIXES = {TEST_QUESTION_PREFIX, TEST_RESPONSE_PREFIX}
    TEST_PHRASES = {"test yourself", "test modules", TEST_QUESTION_PREFIX, TEST_RESPONSE_PREFIX}

    MATCH_TYPES = {
        jaro_winkler_similarity,
    }

    def __str__(self):
        return "TestModule"

    def __init__(self):
        super().__init__()
        self.sent_test = []

    def is_at_module(self, message):
        text = self.is_at_me(message)
        if text:
            return TEST_RESPONSE_PREFIX in text
        return False

    def is_test_response(self, text):
        text = self.is_at_me(text)
        if text:
            return any([phrase in text for phrase in self.TEST_PHRASES])
        return False

    def can_process_message(self, message, client=None):
        if self.is_at_module(message):
            return 10, ""
        return 0, ""

    def get_question_id(self, message):
        text = message.clean_content
        first_number_found = re.search(r"\d+", text).group()
        return int(first_number_found)

    def send_test_questions(self, client=None):
        self.utils.test_mode = True
        question_id = 0
        for module in self.utils.modules_dict:
            if not hasattr(module, "tests"):
                question_id += 1
                self.sent_test.append(
                    {
                        "sent_message": "Developers didn't write test for %s" % str(module),
                        "expected_response": "FAILED - NO TEST WRITTEN FOR %s MODULE" % str(module),
                        "received_response": "NEVER RECEIVED A RESPONSE",
                    }
                )
            else:
                for test in module.tests:
                    question_id += 1
                    test_message = str(TEST_QUESTION_PREFIX % question_id) + test["question"]
                    self.sent_test.append(
                        {
                            "sent_message": test_message,
                            "expected_response": test["expected_response"],
                            "received_response": "NEVER RECEIVED A RESPONSE",
                        }
                    )
                    await client.get_channel(bot_dev_channel_id[ENVIRONMENT_TYPE]).send(test_message)
                    sleep(1)
        self.utils.test_mode = False

    def evaluate_test(self):
        correct_count = 0
        for question in self.sent_test:
            if question["expected_response"] == question["received_response"]:
                correct_count += 1
        score = correct_count / len(self.sent_test)
        self.sent_test = []
        return score

    async def process_message(self, message, client=None):
        if self.is_at_module(message):
            if self.is_test_response(message):
                response_id = self.get_question_id(message)
                self.sent_test[response_id]["received_response"] = message.clean_content
            else:
                self.send_test_questions(client=client)
                sleep(5)
                score = self.evaluate_test()
                # TODO make nicer test passed statement
                return 10, "The percent of test passed is %.2f%%" % (score * 100)
