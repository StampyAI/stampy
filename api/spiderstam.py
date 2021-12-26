# Stampy on the Web #

from stampy import app
#from stampy import utils
from ..utilities import Utilities

utils = Utilities.get_instance()

#for module_name, class_name in utils.enabled_modules:
#    utils.modules_dict[smodule_name] = getattr(import_module(f"modules.{module_name}"), class_name)()

api_base = "api"
api_version = "v1"


@app.route(f"/{api_base}/{api_version}/question")
def question():
    #return "Hey"
    #return "Hello"
    return utils.get_question()
