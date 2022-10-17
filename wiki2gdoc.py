import logging
import os
import re
from typing import Optional

from dotenv import load_dotenv
from ezodf import newdoc, Paragraph, Heading
from ezodf.document import PackagedDocument
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive

from api.semanticwiki import SemanticWiki
from config import wiki_config

def load_questions() -> list[str]:
    if not os.path.isfile("questions.txt"):
        raise FileNotFoundError(
            "`questions.txt` file doesn't exist. "
            "Create the file and write question titles into it as separate lines."
        )
    with open("questions.txt", "r", encoding="utf-8") as f:
        questions = f.read().split("\n")
    return questions

def make_filename(question: str) -> str:
    return re.sub(r"[^\w\-_\. ]", "_", question) + ".odt"

def get_canonical_answer(question_title: str, answers: list[dict]) -> Optional[str]:
    return next((a["answer"] for a in answers
                 if a.get("canonical") == "Yes"
                 and a.get("answerto") == question_title
                 ), None)

def get_noncanonical_answers(question_title: str, answers: list[dict]) -> list[str]:
    return [a["answer"] for a in answers
            if a.get("canonical") != "Yes"
            and a.get("answerto") == question_title]


def make_odt_from_question(question: str, answers: list[dict]) -> PackagedDocument:
    odt = newdoc(doctype="odt", filename=make_filename(question))
    odt.body += Heading(question)
        
    canonical_answer = get_canonical_answer(question, answers)
    noncanonical_answers = get_noncanonical_answers(question, answers)
    n_answers = len(noncanonical_answers) + (canonical_answer is not None)
    print(f"total {n_answers} answers\n{canonical_answer = }\n{noncanonical_answers = }")
    
    if canonical_answer is not None:
        logging.info(f"Found canonical answer for question \"{question}\"")
        odt.body += Paragraph(canonical_answer)
        return odt
    
    if not noncanonical_answers:
        logging.info(f"No answers for question \"{question}\"")
        return odt
    logging.info(f"Found {len(noncanonical_answers)} answers for question \"{question}\"")
    for nca in noncanonical_answers:
        odt.body += Paragraph(nca)
    return odt

def main() -> None:
    folder_id = os.getenv("GDRIVE_FOLDER_ID")
    questions = load_questions()
    # questions = ["What is artificial general intelligence safety / AI alignment?"]
    semantic_wiki = SemanticWiki(wiki_config["uri"], wiki_config["user"], wiki_config["password"])
    answers = semantic_wiki.get_all_answers(questions)
    gauth = GoogleAuth()
    drive = GoogleDrive(gauth)
    for question in questions:
        odt = make_odt_from_question(question, answers)
        odt.save()
    upload_files = [make_filename(q) for q in questions]
    for file in upload_files:
        print(f"{file=}")
        gfile = drive.CreateFile({"parents": [{"id": folder_id}]})
        gfile.SetContentFile(file)
        gfile.Upload()
    
if __name__ == "__main__":
    load_dotenv()
    logging.basicConfig(level=logging.INFO)
    main()
