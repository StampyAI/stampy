import os
import threading
from typing import Callable

from structlog import get_logger

from config import database_path, enabled_modules, ALL_STAMPY_MODULES
from modules.module import Module
from servicemodules.discord import DiscordHandler
from servicemodules.flask import FlaskHandler
from servicemodules.serviceConstants import Services
from servicemodules.slack import SlackHandler
from utilities import Utilities

log_type = "stam.py"
log = get_logger()
utils = Utilities.get_instance()


def get_stampy_modules() -> dict[str, Module]:
    """Dynamically import and return all Stampy modules"""
    stampy_modules = {}
    skipped_modules = set(ALL_STAMPY_MODULES)
    for file_title in enabled_modules:
        assert (
            file_title in ALL_STAMPY_MODULES
        ), f"Module {file_title} enabled but doesn't exist!"

        log.info("import", filename=file_title)
        mod = __import__(".".join(["modules", file_title]), fromlist=[file_title])
        log.info("import", module_name=mod)

        for attribute in dir(mod):
            cls = getattr(mod, attribute)
            if isinstance(cls, type) and issubclass(cls, Module) and cls is not Module:
                log.info("import Module Found", module_name=attribute)
                if is_available := getattr(cls, "is_available", None):
                    if isinstance(is_available, Callable) and not is_available():
                        log.info("import Module not available", module_name=attribute)
                        continue
                    log.info("import Module available", module_name=attribute)
                try:
                    module = cls()
                    stampy_modules[cls.__name__] = module
                except Exception as exc:
                    msg = utils.format_error_message(exc)
                    utils.initialization_error_messages.append(msg)

        skipped_modules.remove(file_title)

    log.info("LOADED MODULES", modules=sorted(stampy_modules.keys()))
    log.info("SKIPPED MODULES", modules=sorted(skipped_modules))
    return stampy_modules


if __name__ == "__main__":
    if not os.path.exists(database_path):
        raise FileNotFoundError(
            f"Couldn't find the stampy database file at {database_path}"
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
    for service_name, service in utils.service_modules_dict.items():
        log.info(log_type, msg=f"Starting {service_name}")
        service_threads.append(service.start(e))
        log.info(log_type, msg=f"{service_name} Started!")

    for thread in service_threads:
        if thread.is_alive() and not thread.daemon:
            thread.join()
    log.info(log_type, msg="Stopping Stampy...")
