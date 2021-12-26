# Stampy on the Web #

from stampy import spiderstam

#utils = utilities.Utilities.get_instance()
#for module_name, class_name in utils.enabled_modules:
#    utils.modules_dict[smodule_name] = getattr(import_module(f"modules.{module_name}"), class_name)()

api_base = "api"
api_version = "v1"


@spiderstam.route(f"/{api_base}/{api_version}/question")
def question():
    return
    #return "Hello"
    #return utils.get_question()
