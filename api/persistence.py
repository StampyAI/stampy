###########################################################################
#   Question and Answer Persistence API Interface for future-proofing
###########################################################################


from typing import Optional


class Persistence:
    def __init__(self, uri: str, user, api_key: str):
        self._uri = uri
        self._user = user
        self._api_key = api_key
        self._session = None
        self._token = None
        self._token_expiration = None

    # def login(self):
    #    raise NotImplementedError

    def add_question(
        self,
        question_title: str,
        asker: str,
        asked_time,
        question_text: str,
        comment_url: Optional[str] = None,
        video_title: Optional[str] = None,
        likes: int = 0,
        asked: bool = False,
        reply_count: int = 0,
    ):
        raise NotImplementedError

    def add_answer(self, answer_title, answer_writer, answer_users, answer_time, answer_text, question_title):
        raise NotImplementedError

    def edit_question(
        self,
        question_title: str,
        asker: str,
        asked_time,
        text: str,
        comment_url: str = "",
        video_title: str = "",
        likes: int = 0,
        asked: bool = False,
        reply_count: int = 0,
    ):
        raise NotImplementedError

    def get_latest_question(self):
        raise NotImplementedError

    def get_random_question(self):
        raise NotImplementedError

    def set_question_asked(self, title: str):
        raise NotImplementedError

    def set_question_replied(self, title: str):
        # TODO: Do we still need this? We can already query unanswered questions, and track if they've been asked
        # NotImplementedError
        pass

    def get_question_count(self):
        raise NotImplementedError
