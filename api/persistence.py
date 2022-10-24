###########################################################################
#   Question and Answer Persistence API Interface for future-proofing
###########################################################################


class Persistence:
    def __init__(self, uri, user, api_key):
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
        question_title,
        asker,
        asked_time,
        question_text,
        comment_url=None,
        video_title=None,
        likes=0,
        asked=False,
        reply_count=0,
    ):
        raise NotImplementedError

    def add_answer(self, answer_title, answer_writer, answer_users, answer_time, answer_text, question_title):
        raise NotImplementedError

    def edit_question(
        self,
        question_title,
        asker,
        asked_time,
        text,
        comment_url="",
        video_title="",
        likes=0,
        asked=False,
        reply_count=0,
    ):
        raise NotImplementedError

    def get_latest_question(self):
        raise NotImplementedError

    def get_random_question(self):
        raise NotImplementedError

    def set_question_asked(self, title):
        raise NotImplementedError

    def set_question_replied(self, title):
        # TODO: Do we still need this? We can already query unanswered questions, and track if they've been asked
        # NotImplementedError
        pass

    def get_question_count(self):
        raise NotImplementedError
