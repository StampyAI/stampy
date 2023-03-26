from asyncio import sleep
import re
from typing import cast

from jellyfish import jaro_winkler_similarity

from config import TEST_QUESTION_PREFIX, TEST_RESPONSE_PREFIX, test_response_message
from modules.module import Module, Response
from servicemodules.serviceConstants import Services
from utilities import get_question_id, is_test_response
from utilities.serviceutils import ServiceMessage


class TestModule(Module):
    """
    This module is the only module that gets stampy to ask its self multiple questions
    In test mode, stampy only responds to itself, whereas in other modes stampy responds only to not itself
    """

    TEST_PREFIXES = {TEST_QUESTION_PREFIX, TEST_RESPONSE_PREFIX}
    TEST_MODULE_PROMPTS = {"test yourself", "test modules"}
    TEST_PHRASES = {TEST_RESPONSE_PREFIX} | TEST_MODULE_PROMPTS
    TEST_MODE_RESPONSE_MESSAGE = "I am running my integration test right now and I cannot handle your request until I am finished"
    SUPPORTED_SERVICES = [Services.DISCORD, Services.SLACK]

    def __init__(self):
        super().__init__()
        self.class_name = self.__str__()
        self.sent_test: list[dict] = []

    def process_message(self, message: ServiceMessage):
        if not self.is_at_module(message):
            return Response()
        # If this is a message coming from an integration test,
        # add it to the dictionary and update output to the channel
        if is_test_response(message.clean_content):
            response_id = get_question_id(message)
            self.log.info(
                self.class_name,
                clean_content=message.clean_content,
                response_id=response_id,
                is_at_me=self.is_at_me(message),
            )
            self.sent_test[cast(int, response_id)].update(
                {
                    "received_response": self.clean_test_prefixes(
                        message, TEST_RESPONSE_PREFIX
                    )
                }
            )
            return Response(
                confidence=8,
                text=test_response_message,
                why="this was a test",
            )

        # If Stampy is already running tests and this message is a request
        # to test himself, ignore it and reply accordingly
        if self.utils.test_mode:
            return Response(
                confidence=9,
                text=self.TEST_MODE_RESPONSE_MESSAGE,
                why="Test already running",
            )
        # Otherwise, this is a request for Stampy to run integration tests
        return Response(
            confidence=10, callback=self.run_integration_test, args=[message]
        )

    def is_at_module(self, message: ServiceMessage) -> bool:
        if hasattr(message, "service"):
            if message.service not in self.SUPPORTED_SERVICES:
                return False
        return any(phrase in message.clean_content for phrase in self.TEST_PHRASES)

    async def send_test_questions(self, message: ServiceMessage):
        self.utils.test_mode = True
        self.utils.message_prefix = TEST_RESPONSE_PREFIX
        question_id = 0
        for module_name, module in self.utils.modules_dict.items():
            try:
                self.log.info(
                    self.class_name, msg="testing module %s" % str(module_name)
                )
                for test in module.test_cases:
                    test_message = (
                        str(TEST_QUESTION_PREFIX + str(question_id) + ": ")
                        + test["question"]
                    )
                    test.update({"question": test_message})
                    self.sent_test.append(test)
                    question_id += 1
                    await message.channel.send(test_message)
                    await sleep(test["test_wait_time"])
            except AttributeError:
                self.sent_test.append(
                    self.create_integration_test(
                        question="Developers didn't write test for %s" % str(module),
                        expected_response="NEVER RECEIVED A RESPONSE",
                    )
                )
                question_id += 1

    def evaluate_test(self):
        correct_count = 0
        for question in self.sent_test:
            received_response = question[
                "received_response"
            ].strip()  # Getting random whitespace errors
            if question["expected_regex"]:
                question["expected_response"] = (
                    "REGULAR EXPRESSION: " + question["expected_regex"]
                )
                if re.search(question["expected_regex"], received_response):
                    correct_count += 1
                    question["results"] = "PASSED"
                else:
                    question["results"] = "FAILED"
            elif question["minimum_allowed_similarity"] == 1.0:
                if question["expected_response"] == received_response:
                    correct_count += 1
                    question["results"] = "PASSED"
                else:
                    question["results"] = "FAILED"
            else:
                text_similarity = jaro_winkler_similarity(
                    question["expected_response"], received_response
                )
                if text_similarity >= question["minimum_allowed_similarity"]:
                    correct_count += 1
                    question["results"] = "PASSED"
                else:
                    question["results"] = "FAILED"
        score = correct_count / len(self.sent_test)
        return score

    async def run_integration_test(self, message: ServiceMessage):
        await self.send_test_questions(message)
        await sleep(3)  # Wait for test messages to go to discord and back to server
        score = self.evaluate_test()
        test_message = "The percentage of tests passed is %.2f%%" % (score * 100)
        self.utils.test_mode = False
        for question_number, question in enumerate(self.sent_test):
            test_status_message = (
                f"QUESTION # {question_number}: {question['results']}\n"
                + f"The sent message was '{question['question'][:200]}'\n"
                + f"the expected message was '{question['expected_response'][:200]}'\n"
                + f"the received message was '{question['received_response'][:200]}'\n\n\n"
            )
            await message.channel.send(test_status_message)
        await sleep(3)
        self.sent_test = []  # Delete all test from memory
        self.utils.message_prefix = ""
        return Response(confidence=10, text=test_message, why="this was a test")

    def __str__(self):
        return "TestModule"

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                question=prompt, expected_response=self.TEST_MODE_RESPONSE_MESSAGE
            )
            for prompt in self.TEST_MODULE_PROMPTS
        ]
