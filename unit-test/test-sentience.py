from modules.sentience import Sentience


def test_process_message():
    module = Sentience()
    assert (0.0000001, "I don't understand") == module.process_message("")
