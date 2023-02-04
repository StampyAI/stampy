from datetime import datetime as dt, timedelta as td
import os
import re
import random

from dotenv import load_dotenv
import pandas as pd
import requests

from utilities.serviceutils import ServiceMessage

load_dotenv()

from modules.module import Module, Response

CODA_API_TOKEN = os.environ["CODA_API_TOKEN"]


class QuestionManager(Module):
    """Fetches not started questions from [Write answers](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/Write-answers_suuwH#Write-answers_tu4_x/r220)

    ## Functionality it should have:

    1. Can be asked for a new question to answer
    2. Will post new questions autonomously if nothing has been said in #general for long enough (and people have said something since the last time it asked a question). This functionality should be the same as the code in on_socket_raw_receive in discord.py
    3. Posts a link to the Gdoc along with the title
    4. Stretch: Asking for specific types of question, like “answer in progress”
    5. Related to 4: Can post [In-progress answers](https://coda.io/d/AI-Safety-Info_dfau7sl2hmG/Improve-answers_suxEW#_lu2ln) and include the current text of the answer
    6. Stretch: Can give stats about how many questions there are etc. QuestionQueueManager could do this, but it's not a key feature
    """

    DOC_ID = "fau7sl2hmG"
    TABLE_NAME = "Write answers"

    def process_message(self, message: ServiceMessage) -> Response:
        """Process message"""
        text = self.is_at_me(message)
        if text and self.is_next_q_request(text):
            questions_df = self.get_not_started_questions()
            question_msg = self.get_oldest_question_message(questions_df)
            return Response(
                confidence=8,
                text=question_msg,
                why="I was asked for next not started question",
            )
        return Response()

    @staticmethod
    def is_next_q_request(text: str) -> bool:
        """Is request for next question"""
        return text.endswith("next q") or text.endswith("next question")

    def get_not_started_questions(self) -> pd.DataFrame:
        """Get questions from with `status="Not started"`"""

        headers = {"Authorization": f"Bearer {CODA_API_TOKEN}"}
        params = {"valueFormat": "rich", "useColumnNames": True}
        uri = (
            f"https://coda.io/apis/v1/docs/{self.DOC_ID}/tables/{self.TABLE_NAME}/rows"
        )
        res = requests.get(uri, headers=headers, params=params, timeout=16).json()
        rows = [self.parse_row(row) for row in res["items"]]
        return pd.DataFrame(rows)

    def parse_row(self, row: dict) -> dict:
        """Parse row from "Write answers" table"""

        parsed = {"id": row["id"]}
        answer_raw = row["values"]["Edit Answer"]
        answer_match = re.match(r"\[(.+)\]\((.+)\)$", answer_raw)
        assert answer_match
        assert len(answer_match.groups()) == 2
        parsed["answer_title"], parsed["answer_url"] = answer_match.groups()
        parsed["status"] = row["values"]["Status"]["name"]
        parsed["last_asked_on_discord"] = self.adjust_date(
            row["values"]["Last Asked On Discord"]
        )
        return parsed

    @staticmethod
    def get_oldest_question_message(df: pd.DataFrame) -> str:
        """Generate Discord message for least recently asked question.
        It will contain question title and GDoc url.
        """
        oldest_discord_date = df["last_asked_on_discord"].min()
        oldest_discord_date_question_ids = df[
            df["last_asked_on_discord"] == oldest_discord_date
        ]["id"].tolist()
        random_question_id = random.choice(oldest_discord_date_question_ids)
        question = df.query("id == @random_question_id").iloc[0]
        return f"{question['answer_title']}\n\n{question['answer_url']}"

    @staticmethod
    def adjust_date(date_str: str) -> dt:
        """If date is in isoformat, parse it.
        Otherwise, assign earliest date possible.
        """

        if date_str == "":
            return dt(1, 1, 1, 0)
        return dt.fromisoformat(date_str.split("T")[0])

    def __str__(self):
        return "Question Manager module"
