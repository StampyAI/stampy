import re
from asyncio import sleep
from modules.module import Module
from utilities import get_question_id
from jellyfish import jaro_winkler_similarity
from config import TEST_QUESTION_PREFIX, TEST_RESPONSE_PREFIX


class TestModule(Module):
    # This module is the only module that gets stampy to ask its self multiple questions
    # In test mode, stampy only responds to itself, whereas in other modes stampy responds only to not itself
    TEST_PREFIXES = {TEST_QUESTION_PREFIX, TEST_RESPONSE_PREFIX}
    TEST_PHRASES = {
        "test yourself",
        "test modules",
        TEST_QUESTION_PREFIX,
        TEST_RESPONSE_PREFIX,
    }
    TESTING_MODE_RESPONSE_MESSAGE = (
        "I am running my integration test right now and I cannot answer you question until I am finished"
    )

    def __str__(self):
        return "TestModule"

    def __init__(self):
        super().__init__()
        self.sent_test = []

    def is_at_module(self, message):
        return any([phrase in message.clean_content for phrase in self.TEST_PHRASES])

    def is_test_response(self, text):
        text = self.is_at_me(text)
        if text:
            return any([phrase in text for phrase in self.TEST_PHRASES])
        return False

    def can_process_message(self, message, client=None):
        if self.is_at_module(message):
            return 10, ""
        return 0, ""

    @staticmethod
    def get_question_id(message):
        text = message.clean_content
        first_number_found = re.search(r"\d+", text).group()
        return int(first_number_found)

    async def send_test_questions(self, message):
        self.utils.test_mode = True
        self.utils.message_prefix = TEST_RESPONSE_PREFIX
        question_id = 0
        for module_name, module in self.utils.modules_dict.items():
            try:
                print("testing module %s" % str(module_name))
                for test in module.test_cases:
                    test_message = str(TEST_QUESTION_PREFIX + str(question_id) + ": ") + test["question"]
                    test.update({"question": test_message})
                    self.sent_test.append(test)
                    question_id += 1
                    await message.channel.send(test_message)
                    await sleep(test["test_wait_time"])
            except AttributeError:
                self.sent_test.append(
                    self.create_integration_test(
                        question="Developers didn't write test for %s" % str(module),
                        expected_response="FAILED - NO TEST WRITTEN FOR %s MODULE" % str(module),
                    )
                )
                question_id += 1

    def evaluate_test(self):
        correct_count = 0
        for question in self.sent_test:
            if question["minimum_allowed_similarity"] == 1.0:
                if question["expected_response"] == question["received_response"]:
                    correct_count += 1
            else:
                text_similarity = jaro_winkler_similarity(
                    question["expected_response"], question["received_response"]
                )
                if text_similarity >= question["minimum_allowed_similarity"]:
                    correct_count += 1
        score = correct_count / len(self.sent_test)
        self.sent_test = []
        return score

    async def process_message(self, message, client=None):
        if self.is_at_module(message):
            if self.is_test_response(message):
                response_id = get_question_id(message)
                print(message.clean_content, response_id, self.is_at_me(message))
                self.sent_test[response_id].update(
                    {"received_response": self.clean_test_prefixes(message, TEST_RESPONSE_PREFIX)}
                )
                return 10, ""
            else:
                await self.send_test_questions(message)
                score = self.evaluate_test()
                test_message = "The percent of test passed is %.2f%%" % (score * 100)
                await sleep(3)  # Wait for test messages to go to discord and back to server
                self.utils.test_mode = False
                for question in self.sent_test:
                    test_status_message = (
                        "The sent message was '%s', the expected message was '%s', the received message was '%s'"
                        % (
                            question["question"][:200],
                            question["expected_response"][:200],
                            question["received_response"][:200],
                        )
                    )
                    await message.channel.send(test_status_message)
                self.sent_test = []
                self.utils.message_prefix = ""
                return 10, test_message
