import os
import sys
import threading
from utilities import Utilities
from modules.reply import Reply
from modules.questions import QuestionQueManager
from modules.wolfram import Wolfram
from modules.duckduckgo import DuckDuckGo
from modules.videosearch import VideoSearch
from modules.AlignmentNewsletterSearch import AlignmentNewsletterSearch
from modules.invitemanager import InviteManager
from modules.stampcollection import StampsModule
from modules.StampyControls import StampyControls
from modules.gpt3module import GPT3Module
from modules.Factoids import Factoids
from modules.wikiUpdate import WikiUpdate
from modules.wikiUtilities import WikiUtilities
from modules.testModule import TestModule
from servicemodules.discord import DiscordHandler
from servicemodules.slack import SlackHandler
from structlog import get_logger
from config import (
    database_path,
    prod_local_path,
    ENVIRONMENT_TYPE,
    acceptable_environment_types,
)

log_type = "stam.py"
log = get_logger()


if __name__ == "__main__":
    utils = Utilities.get_instance()

    if not os.path.exists(database_path):
        raise Exception("Couldn't find the stampy database file at " + f"{database_path}")

    if ENVIRONMENT_TYPE == "production":
        sys.path.insert(0, prod_local_path)
        import sentience
    elif ENVIRONMENT_TYPE == "development":
        from modules.sentience import sentience
    else:
        raise Exception(
            "Please set the ENVIRONMENT_TYPE environment variable "
            + f"to {acceptable_environment_types[0]} or "
            + f"{acceptable_environment_types[1]}"
        )

    utils.modules_dict = {
        "StampyControls": StampyControls(),
        "StampsModule": StampsModule(),
        "QQManager": QuestionQueManager(),
        "VideoSearch": VideoSearch(),
        "ANSearch": AlignmentNewsletterSearch(),
        "Wolfram": Wolfram(),
        "DuckDuckGo": DuckDuckGo(),
        "Reply": Reply(),
        "InviteManager": InviteManager(),
        "GPT3Module": GPT3Module(),
        "Factoids": Factoids(),
        "Sentience": sentience,
        "WikiUpdate": WikiUpdate(),
        "WikiUtilities": WikiUtilities(),
        "TestModule": TestModule(),
    }
    utils.service_modules_dict = {"Discord": DiscordHandler(), "Slack": SlackHandler()}

    service_threads = []
    e = threading.Event()
    utils.stop = e
    for module in utils.service_modules_dict:
        log.info(log_type, msg=f"Starting {module}")
        service_threads.append(utils.service_modules_dict[module].start(e))
        log.info(log_type, msg=f"{module} Started!")

    for thread in service_threads:
        if thread.is_alive():
            thread.join()
    log.info(log_type, msg="Stopping Stampy...")
