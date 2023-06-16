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

    # dictionary mapping Module class names to initialized Module objects
    stampy_modules: dict[str, Module] = {}

    # names of files of modules that were skipped because not enabled
    skipped_modules = set(ALL_STAMPY_MODULES - enabled_modules)

    for filename in enabled_modules:
        if filename not in ALL_STAMPY_MODULES:
            raise AssertionError(f"Module {filename} enabled but doesn't exist!")

        log.info("import", filename=filename)
        mod = __import__(f"modules.{filename}", fromlist=[filename])
        log.info("import", module_name=mod)

        for attr_name in dir(mod):
            cls = getattr(mod, attr_name)
            if isinstance(cls, type) and issubclass(cls, Module) and cls is not Module:
                log.info("import Module Found", module_name=attr_name)
                if (
                    (is_available := getattr(cls, "is_available", None))
                    and isinstance(is_available, Callable)
                    and not is_available()
                ):
                    log.info(
                        "import Module not available",
                        module_name=attr_name,
                        filename=filename,
                    )
                    utils.unavailable_module_filenames.append(filename)
                    skipped_modules.add(filename)
                    continue
                log.info(
                    "import Module available",
                    module_name=attr_name,
                    filename=filename,
                )
                if attr_name == "QuestionSetter":
                    log.info("IMPORT", msg="Importing QuestionSetter")
                try:
                    module = cls()
                    log.info("IMPORT", msg="Successfully instantiated QuestionSetter")
                    stampy_modules[cls.__name__] = module
                    log.info("IMPORT", msg="Successfully added QuestionSetter")
                except Exception as exc:
                    log.info("IMPORT", msg="Failed at importing QuestionSetter")
                    msg = utils.format_error_message(exc)
                    log.error("ERROR", exc=exc)
                    log.error("ERROR MSG", msg=msg)
                    utils.initialization_error_messages.append(msg)
    # skipped_modules = set(enabled_modules) - set(stampy_modules)
    log.info("LOADED MODULES", modules=sorted(stampy_modules, key=str.casefold))
    log.info("SKIPPED MODULES", modules=sorted(skipped_modules, key=str.casefold))
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
