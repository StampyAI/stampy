from modules.module import Module, Response


class Sentience(Module):
    CONFUSED_RESPONSE = "I don't understand"

    def process_message(self, message, client=None):
        return Response(confidence=3, text=self.CONFUSED_RESPONSE)

    def __str__(self):
        return "Sentience"

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                question="If I asked you what 2+2 was and you answered incorrectly what would you have said?",
                expected_response=self.CONFUSED_RESPONSE,
            )
        ]


sentience = Sentience()
