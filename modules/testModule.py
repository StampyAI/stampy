"""
Test whether I work as expected
Ideally, every Stampy module should have a suite of integration tests written for it. A Stampy integration test consists of Stampy sending a particular test message to the channel and testing whether he (i.e., Stampy himself) will respond to it as expected. You can run all tests at once or only for a subset of modules.
**Important:** tests can be run only in the private dev channel channel `#stampy-dev-priv`.

Test all modules, Test yourself
Test all Stampy modules that have tests written for them.
`s, test yourself`
`s, test modules` - If it's not specified **which particular modules** are to be tested, all modules will be tested.

Test some modules, Test modules
Test a selected subset of Stampy modules.
`s, test modules <module-name-1> <module-name-2> ...` - Specify one or more modules. Tests will be run only for those.

Test one module, Test module
Test exactly one Stampy module.
`s, test module <module-name>`

Send a long message
Stampy will send an absurdly long message to the channel so that you can see if it's properly shortened and wrapped.
This is not included in any tests; only meant as a possibility to check that one functionality.
`s, send a long message`
"""

from asyncio import sleep
import re
from textwrap import dedent
from typing import cast

from jellyfish import jaro_winkler_similarity

from config import (
    TEST_MESSAGE_PREFIX,
    TEST_RESPONSE_PREFIX,
    test_response_message,
    bot_private_channel_id,
)
from modules.module import IntegrationTest, Module, Response
from servicemodules.serviceConstants import Services
from utilities import get_question_id, is_test_response
from utilities.serviceutils import ServiceMessage
from utilities.utilities import is_bot_dev


class TestModule(Module):
    """
    This module is the only module that gets stampy to ask himself multiple questions.
    In test mode, stampy only responds to himself, whereas in other modes stampy responds only to not himself.

    ### How to test Stampy

    - You can only test Stampy in the channel for bot_private_channel_id
    - You can test Stampy in one of three ways
        1. test all modules; `s, test yourself` or `s, test modules`
        2. test a subset of modules `s, test modules <module-name-1> <module-name-2> <module-name-3>
        3. test one module: `s, test module <module-name>`
    """

    TEST_PREFIXES = {TEST_MESSAGE_PREFIX, TEST_RESPONSE_PREFIX}
    TEST_MODULE_PROMPTS = {"test yourself", "test modules", "test module"}
    TEST_PHRASES = {TEST_RESPONSE_PREFIX} | TEST_MODULE_PROMPTS
    TEST_MODE_RESPONSE_MESSAGE = "I am running my integration test right now and I cannot handle your request until I am finished"
    SUPPORTED_SERVICES = [Services.DISCORD, Services.SLACK]

    def __init__(self):
        super().__init__()
        self.sent_test: list[IntegrationTest] = []

    def process_message(self, message: ServiceMessage) -> Response:
        if message.clean_content == "s, send a long message":
            if not is_bot_dev(message.author):
                return Response(
                    confidence=10,
                    text=f"You're not a bot dev, {message.author.display_name}",
                    why=f"{message.author.display_name} doesn't have permissions to ask me to spam the channel with absurdly long messages",
                )
            self.log.info(self.class_name, msg="horrifically long message sent")
            return Response(
                confidence=10, text=str(list(range(25000))), why="you told me to dude!"
            )

        if not self.is_at_module(message):
            return Response()
        # If this is a message coming from an integration test,
        # add it to the dictionary and update output to the channel

        if is_test_response(message.clean_content):
            response_id = cast(int, get_question_id(message))
            self.log.info(
                self.class_name,
                clean_content=message.clean_content,
                response_id=response_id,
                is_at_me=self.is_at_me(message),
            )
            self.sent_test[response_id]["received_response"] = self.clean_test_prefixes(
                message, TEST_RESPONSE_PREFIX
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

        if message.channel.id != bot_private_channel_id:
            return Response(
                confidence=10,
                text="Testing is only allowed in the private channel",
                why=f"{message.author.display_name} wanted to test me outside of the private channel which is prohibited!",
            )

        if not is_bot_dev(message.author):
            return Response(
                confidence=10,
                text=f"You are not a bot dev, {message.author.display_name}",
                why=f"{message.author.display_name} wanted to test me but they are not a bot dev",
            )

        # Otherwise, this is a request for Stampy to run integration tests
        lowercase_module_names = [
            module_name.lower() for module_name in self.utils.modules_dict
        ]
        if match := re.search(r"test module (\w+)", message.clean_content, re.I):
            parsed_module_name = match.group(1)
            if parsed_module_name.lower() not in lowercase_module_names:
                return Response(
                    confidence=10,
                    text=f'I don\'t have a module named "{parsed_module_name}"',
                    why=(
                        f"{message.author.display_name} asked me to test module "
                        f'"{parsed_module_name}" but I don\'t have such a module'
                    ),
                )
            module_name = next(
                module_name
                for module_name in self.utils.modules_dict
                if module_name.lower() == parsed_module_name.lower()
            )
            modules_dict = {module_name: self.utils.modules_dict[module_name]}
        elif message.clean_content.strip().endswith("test module"):
            return Response(
                confidence=10,
                text="Yeah but which module?",
                why=f"{message.author.display_name} asked me to test a module but they didn't specify which one",
            )
        else:
            modules_dict = self.parse_module_dict(message)
            if not modules_dict:
                return Response(
                    confidence=10,
                    text="I don't have these modules. Are you sure you wrote their names correctly?",
                    why=f"{message.author.display_name} asked me to test some modules but I couldn't recognize their names.",
                )

        return Response(
            confidence=10,
            callback=self.run_integration_tests,
            args=[message],
            kwargs={"modules_dict": modules_dict},
        )

    def is_at_module(self, message: ServiceMessage) -> bool:
        """The message is directed at this module
        if its service is supported and it contains one of the test phrases
        """
        if (
            hasattr(message, "service")
            and message.service not in self.SUPPORTED_SERVICES
        ):
            return False
        text = self.is_at_me(message)
        if not text:
            text = message.clean_content
        return any(text.startswith(phrase) for phrase in self.TEST_PHRASES)

    def parse_module_dict(self, message: ServiceMessage) -> dict[str, Module]:
        """Extract module names from the message (containing "test modules" phrase)
        and return a dictionary containing  modules to be tested. If no modules
        are mentioned in the message, return a dictionary with all the modules.
        """
        text = message.clean_content
        if re.search(r"test modules ([\w\s]+)", text, re.I):
            module_names = self.utils.parse_module_names(text)
            modules_dict = {
                module_name: self.utils.modules_dict[module_name]
                for module_name in module_names
            }
            return modules_dict
        return self.utils.modules_dict

    async def run_integration_tests(
        self, message: ServiceMessage, modules_dict: dict[str, Module]
    ) -> Response:
        """Run integration tests in all modules from `modules_dict`
        with defined `test_cases`
        """
        # safeguards before running this function guarantee that modules_dict is not empty
        if len(modules_dict) == len(self.utils.modules_dict):
            channel_msg = "Running tests for all the modules"
        elif len(modules_dict) == 1:
            channel_msg = f"Running tests for the module `{list(modules_dict)[0]}`"
        else:
            channel_msg = (
                f"Runnning tests for the following {len(modules_dict)} modules: "
                + ", ".join(f"`{module_name}`" for module_name in modules_dict)
            )
        # Send a message about how many tests are being run and for which module
        await message.channel.send(channel_msg)

        # Set test mode to True and set message prefix
        self.utils.test_mode = True
        self.utils.message_prefix = TEST_RESPONSE_PREFIX

        # Run test_cases
        await self.send_test_messages(message, modules_dict)
        await sleep(10)  # Wait for test messages to go to discord and back to server

        # if no tests were found for given modules, reset stuff and explain why
        if not self.sent_test:
            self.utils.test_mode = False
            self.utils.message_prefix = ""
            module_names = sorted(modules_dict)
            if len(module_names) == 1:
                module_msg_str = f"module `{module_names[0]}`"
            else:
                module_msg_str = "modules " + ", ".join(
                    f"`{module_name}`" for module_name in module_names
                )

            return Response(
                confidence=10,
                text=f"I found no tests for {module_msg_str}",
                why=f"This was meant to be a test but I found no test cases for {module_msg_str}",
            )

        await message.channel.send(
            "\n\n`=== Finished tests, evaluating the results ===`\n\n"
        )

        # Evaluate tests and generate test message with the score (% of tests that passed)
        score = self.evaluate_test()
        test_message = f"The percentage of tests passed is {score:.2%}"

        # Get status messages and send them to the channel
        for test_id, test_case in enumerate(self.sent_test):
            received_response = test_case["received_response"][:200].replace("\n", " ")
            test_status_message = dedent(
                f"""\
                `TEST #{test_id}: {test_case["result"]}`
                The sent message was: "{test_case["test_message"][:200]}"
                The expected message was "{test_case["expected_response"][:200]}"
                The received message was "{received_response}"\n\n\n"""
            )
            await message.channel.send(test_status_message)

        await sleep(3)

        # Delete tests from memory
        self.sent_test.clear()

        # Reset test mode and message_prefix
        self.utils.test_mode = False
        self.utils.message_prefix = ""

        return Response(confidence=10, text=test_message, why="this was a test")

    async def send_test_messages(
        self, message: ServiceMessage, modules_dict: dict[str, Module]
    ) -> None:
        """Gather tests from modules in `modules_dict` that have `test_cases` defined,
        save them to memory and send the messages defined on those tests to the channel.
        """
        # test index - must be defined outside the loop because modules vary in number of tests
        test_id = 0
        for module_id, (module_name, module) in enumerate(modules_dict.items()):
            if test_cases := cast(
                list[IntegrationTest], getattr(module, "test_cases", None)
            ):
                # make the message about testing that module; log it and send to the channel
                self.log.info(self.class_name, msg=f"testing module {module_name}")
                await message.channel.send(
                    f"`=== [{module_id}] {module_name}: running {len(test_cases)} tests ===`"
                )

                # run tests
                for test_case in test_cases:
                    test_message = (
                        f"{TEST_MESSAGE_PREFIX}{test_id}: {test_case['test_message']}"
                    )
                    test_case["test_message"] = test_message
                    self.sent_test.append(test_case)
                    test_id += 1
                    await message.channel.send(test_message)
                    await sleep(test_case["test_wait_time"])
            else:
                self.log.info(
                    self.class_name, msg=f"no tests written for module {module_name}"
                )
                await message.channel.send(
                    f"`=== [{module_id}] {module_name}: no tests have been written ===`"
                )

    def evaluate_test(self) -> float:
        """Evaluate tests that were sent and saved to memory using `send_test_questions`."""
        if not self.sent_test:
            self.log.error(
                self.class_name,
                msg="Tried evaluating integration tests but no integration tests were run",
            )
            return 0
        passed_tests_count = 0
        for test_case in self.sent_test:
            # Removing random whitespace errors
            received_response = test_case["received_response"].strip()

            # Evaluate regex test
            if test_case["expected_regex"]:
                test_case["expected_response"] = "RegEx: " + test_case["expected_regex"]
                if re.search(test_case["expected_regex"], received_response):
                    passed_tests_count += 1
                    test_case["result"] = "PASSED"
                else:
                    test_case["result"] = "FAILED"

            # Evaluate "normal" test
            elif test_case["minimum_allowed_similarity"] == 1.0:
                if test_case["expected_response"] == received_response:
                    passed_tests_count += 1
                    test_case["result"] = "PASSED"
                else:
                    test_case["result"] = "FAILED"

            # Evaluate test which allows less-than-perfect-similarity
            else:
                text_similarity = jaro_winkler_similarity(
                    test_case["expected_response"], received_response
                )
                if text_similarity >= test_case["minimum_allowed_similarity"]:
                    passed_tests_count += 1
                    test_case["result"] = "PASSED"
                else:
                    test_case["result"] = "FAILED"

        score = passed_tests_count / len(self.sent_test)
        return score

    def __str__(self):
        return "TestModule"

    @property
    def test_cases(self) -> list[IntegrationTest]:
        return [
            self.create_integration_test(
                test_message=prompt, expected_response=self.TEST_MODE_RESPONSE_MESSAGE
            )
            for prompt in self.TEST_MODULE_PROMPTS
        ]
