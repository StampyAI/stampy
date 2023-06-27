import os
from sys import warnoptions

from config import database_path, enabled_modules, ALL_STAMPY_MODULES, ENVIRONMENT_TYPE

if not warnoptions: # if user hasn't passed explicit warning settings
    import warnings
    from typing import Literal
    WARN_LEVEL: Literal['default', 'error', 'ignore', 'always', 'module', 'once']
    if ENVIRONMENT_TYPE == "development":
        WARN_LEVEL = 'error'
    elif ENVIRONMENT_TYPE == "production":
        WARN_LEVEL = 'always'
    else:
        raise Exception(f"Unknown environment type {ENVIRONMENT_TYPE}")

    warnings.simplefilter(WARN_LEVEL) # Change the filter in this process
    os.environ["PYTHONWARNINGS"] = WARN_LEVEL # Also affect subprocesses

import threading
import sys
from typing import cast

from structlog import get_logger

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

    loaded_module_filenames = set()

    # filenames of modules that were skipped because not enabled
    skipped_module_filenames = set(ALL_STAMPY_MODULES - enabled_modules)

    for filename in enabled_modules:
        if filename not in ALL_STAMPY_MODULES:
            raise AssertionError(f"Module {filename} enabled but doesn't exist!")

        log.info("import", filename=filename)
        mod = __import__(f"modules.{filename}", fromlist=[filename])
        log.info("import", module_name=mod)

        # iterate over attribute names in the file
        for attr_name in dir(mod):
            cls = getattr(mod, attr_name)
            # try instantiating it if it is a `Module`...
            if isinstance(cls, type) and issubclass(cls, Module) and cls is not Module:
                log.info("import Module Found", module_name=attr_name)
                # unless it has a classmethod is_available, which in this particular situation returns False
                if (
                    (is_available := getattr(cls, "is_available", None))
                    and callable(is_available)
                    and not is_available()
                ):
                    log.info(
                        "import Module not available",
                        module_name=attr_name,
                        filename=filename,
                    )
                    # for testing in test_stam.py
                    utils.unavailable_module_filenames.append(filename)
                else:
                    if hasattr(cls, "is_available"):
                        log.info(
                            "import Module available",
                            module_name=attr_name,
                            filename=filename,
                        )
                    try:
                        module = cast(Module, cls())
                        stampy_modules[module.class_name] = module
                        loaded_module_filenames.add(filename)
                    except Exception as exc:
                        msg = utils.format_error_traceback_msg(exc)
                        utils.initialization_error_messages.append(msg)
                        log.error("Import error", exc=exc, traceback=msg)

    log.info(
        "Loaded modules", filenames=sorted(loaded_module_filenames, key=str.casefold)
    )
    log.info(
        "Skipped modules", filenames=sorted(skipped_module_filenames, key=str.casefold)
    )
    log.info(
        "Unavailable modules",
        filenames=sorted(utils.unavailable_module_filenames, key=str.casefold),
    )
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

    # Calling sys.exit() from other threads does not get
    # the exit value to the shell
    sys.exit(utils.exit_value)
