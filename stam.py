import os
import threading

from structlog import get_logger

from config import database_path
from modules.module import Module
from servicemodules.discord import DiscordHandler
from servicemodules.flask import FlaskHandler
from servicemodules.serviceConstants import Services
from servicemodules.slack import SlackHandler
from utilities import Utilities

log_type = "stam.py"
log = get_logger()


def get_stampy_modules() -> dict[str, Module]:
    """Dynamically import and return all Stampy modules"""
    stampy_modules = {}
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "modules")
    module_filenames = [
        f[:-3] for f in os.listdir(path) if f.endswith(".py") and f != "__init__.py"
    ]
    for file_title in module_filenames:
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
