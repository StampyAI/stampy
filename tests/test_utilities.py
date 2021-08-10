import pytest

from utilities import *
from config import TEST_RESPONSE_PREFIX, TEST_QUESTION_PREFIX


class Message:
    def __init__(self, content):
        self.clean_content = content


@pytest.fixture
def test_questions():
    id1, q1 = 0, TEST_QUESTION_PREFIX + "0 - what 100 questions are most important?"
    id2, q2 = 27, TEST_QUESTION_PREFIX + "27 stampy whats your name?"
    id3, q3 = 103, TEST_QUESTION_PREFIX + "103: 42?"
    return (id1, q1), (id2, q2), (id3, q3)


@pytest.fixture
def test_responses():
    id1, r1 = 0, TEST_RESPONSE_PREFIX + "0 - The first one"
    id2, r2 = 27, TEST_RESPONSE_PREFIX + "27 stampy"
    id3, r3 = 103, TEST_RESPONSE_PREFIX + "103: is the meaning of life"
    return (id1, r1), (id2, r2), (id3, r3)


@pytest.fixture
def user_questions():
    q1 = "stampy what time is it?"
    q2 = "stampy whats your name?"
    q3 = "stampy what is it all about?"
    return q1, q2, q3


@pytest.fixture
def user_responses():
    r1 = "its show time"
    r2 = "stampy danger miles"
    r3 = "stopping misaligned AGI from killing you"
    return r1, r2, r3


def test_is_test_message(test_questions, test_responses, user_questions, user_responses):
    assert all(is_test_message(text) for _, text in test_questions)
    assert all(is_test_message(text) for _, text in test_responses)
    assert all(not is_test_message(text) for text in user_questions)
    assert all(not is_test_message(text) for text in user_responses)


def test_get_question_id(test_questions, test_responses, user_questions):
    assert all((get_question_id(Message(q)) == qid) for qid, q in test_questions)
    assert all((get_question_id(Message(r)) == qid) for qid, r in test_responses)
    assert all("" == get_question_id(Message(q)) for q in user_questions)


def test_is_test_question(test_questions, user_questions):
    assert all(is_test_question(text) for _, text in test_questions)
    assert all(not is_test_message(text) for text in user_questions)


def test_is_test_response(test_responses, user_responses):
    assert all(is_test_response(text) for _, text in test_responses)
    assert all(not is_test_message(text) for text in user_responses)


def test_contains_prefix_with_number(test_questions, test_responses):
    assert all(contains_prefix_with_number(text, TEST_QUESTION_PREFIX) for _, text in test_questions)
    assert all(contains_prefix_with_number(text, TEST_RESPONSE_PREFIX) for _, text in test_responses)
