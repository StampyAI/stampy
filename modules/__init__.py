import importlib
import os

import modules.ANSearch


def import_all_modules():
    """
    Import all modules in the modules folder.
    Assumes that the folder structure of modules is flat, this could be done recursively in future if needed.
    """
    path = os.path.join(os.path.abspath(__file__), "..")

    for fname in os.listdir(path):
        if os.path.isfile(os.path.join(path, fname)) and fname.endswith(".py") and not fname.startswith("__"):
            importlib.import_module("modules." + fname[0:-3])


# It might make sense to make this happen on a conditional, not all the time. Rn
# Rn, importing any single module will import all of them automatically, and consequently set up a db connect, etc.
import_all_modules()

# USAGE:
# with this, any file can call "import modules" and all of the modules in this folder will be imported
# once all modules are imported, you can use "Module.__subclasses__()" to get a list of all modules.


