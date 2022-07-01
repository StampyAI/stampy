from config import CONFUSED_RESPONSE
from modules.module import Module, Response


class Sentience(Module):
    def process_message(self, message):
        if self.is_at_me(message):
            self.log.info("Sentience", msg="Confused Response Sent")
            return Response(confidence=0.0000001, text=CONFUSED_RESPONSE)
        else:
            return Response()

    def __str__(self):
        return "Sentience"

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                question="If I asked you what 2+2 was and you answered incorrectly what would you have said?",
                expected_response=CONFUSED_RESPONSE,
            )
        ]
