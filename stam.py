import os
import sys
import threading
from servicemodules.discord import DiscordHandler
from servicemodules.slack import SlackHandler
from servicemodules.flask import FlaskHandler
from utilities import Utilities
from structlog import get_logger
from modules.module import Module
from config import (
    database_path,
    prod_local_path,
    ENVIRONMENT_TYPE,
    acceptable_environment_types,
)
from servicemodules.serviceConstants import Services

log_type = "stam.py"
log = get_logger()


def get_stampy_modules():
    stampy_modules = {}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules")
    for file_title in [f[:-3] for f in os.listdir(path) if f.endswith(".py") and f != "__init__.py"]:
        log.info("import", filename=file_title)
        mod = __import__(".".join(["modules", file_title]), fromlist=[file_title])
        log.info("import", module_name=mod)
        for attribute in dir(mod):
            cls = getattr(mod, attribute)
            if isinstance(cls, type) and issubclass(cls, Module) and cls is not Module:
                log.info("import Module Found", module_name=attribute)
                stampy_modules[cls.__name__] = cls()
    log.info("LOADED MODULES", modules=sorted(stampy_modules.keys()))
    return stampy_modules


if __name__ == "__main__":
    utils = Utilities.get_instance()

    if not os.path.exists(database_path):
        raise Exception("Couldn't find the stampy database file at " + f"{database_path}")

    if ENVIRONMENT_TYPE == "production":
        sys.path.insert(0, prod_local_path)
        import sentience
    elif ENVIRONMENT_TYPE == "development":
        pass
        # from modules.sentience import sentience
    else:
        raise Exception(
            "Please set the ENVIRONMENT_TYPE environment variable "
            + f"to {acceptable_environment_types[0]} or "
            + f"{acceptable_environment_types[1]}"
        )

    utils.modules_dict = get_stampy_modules()

    utils.service_modules_dict = {
        Services.DISCORD: DiscordHandler(),
        Services.SLACK: SlackHandler(),
        Services.FLASK: FlaskHandler(),
    }

    service_threads = []
    e = threading.Event()
    utils.stop = e
    for service in utils.service_modules_dict:
        log.info(log_type, msg=f"Starting {service}")
        service_threads.append(utils.service_modules_dict[service].start(e))
        log.info(log_type, msg=f"{service} Started!")

    for thread in service_threads:
        if thread.is_alive() and not thread.daemon:
            thread.join()
    log.info(log_type, msg="Stopping Stampy...")
