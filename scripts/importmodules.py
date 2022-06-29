import re
import os
import sys
import importlib
from os.path import join, isdir


def find_all_sub_classes():
    """
    Import all classes in all files in the directory called 'modules' so that
    they are available for usage.
    """
    path = "/Users/chris/PycharmProjects/stampy/modules"
    for py in [f[:-3] for f in os.listdir(path) if f.endswith(".py") and f != "__init__.py"]:
        print(__name__)
        print(py)
        mod = __import__(".".join(["modules", py]), fromlist=[py])
        classes = [getattr(mod, x) for x in dir(mod) if isinstance(getattr(mod, x), type)]
        for cls in classes:
            print(cls)
            setattr(sys.modules[__name__], cls.__name__, cls)
