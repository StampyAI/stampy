import re
from typing import Generator
from modules.module import Module, Response


class WikiUtilities(Module):
    """Module to manage commands about moving wiki pages"""

    shared_regex_part = (
        r"(?:,? matching (?P<page>'[^']+'|\"[^\"]+\"|`[^`]+`|.+))?"
        r"(?:,? offset (?P<offset>\d+))?"
        r"(?P<skip>,? skip (?:boring|video title unknown))?"
    )
    dry_run_regex = re.compile(
        rf"what(?:,? (?P<limit>\d+))? (?:question|page)s? needs? moving{shared_regex_part}\?*$", re.IGNORECASE
    )
    move_regex = re.compile(
        rf"move(?: th[ae])?(?:,? (?P<limit>\d+))? (?:question|page)s?{shared_regex_part}!*$", re.IGNORECASE
    )
    stop_regex = re.compile(r"stop", re.IGNORECASE)
    generatorInstance: Generator = None

    def process_message(self, message):
        text = self.is_at_me(message)
        if text:
            stop = self.stop_regex.match(text)
            if stop:
                if not self.generatorInstance:
                    return Response(confidence=1, text="Nothing to stop.", why="No iterator.")
                else:
                    self.generatorInstance.close()
                    self.generatorInstance = None
                    return Response(confidence=10, text="WikiUtilities: HALT_AND_CATCH_FIRE")

            match_dry_run = self.dry_run_regex.match(text)
            match_move = self.move_regex.match(text)

            if match_move and not self.is_wiki_editor(message.author):
                return Response(
                    confidence=10,
                    text=f"naughty <@{message.author.id}>, you are not a wiki-editor :face_with_raised_eyebrow:",
                )

            match = match_dry_run or match_move
            if match:
                self.generatorInstance = self.utils.wiki.move_pages_generator(
                    page=match.group("page"),
                    limit=match.group("limit"),
                    offset=match.group("offset"),
                    dry_run=bool(match_dry_run),
                    skip_boring=bool(match.group("skip")),
                )
                return Response(confidence=10, text=self.generatorInstance)

        # This is either not at me, or not something we can handle
        return Response()

    @staticmethod
    def is_wiki_editor(user):
        roles = getattr(user, "roles", [])
        return "wiki-editor" in [role.name for role in roles]

    def __str__(self):
        return "Wiki Move Pages"

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                question="what questions need moving, matching 'What is superintelligence?'?",
                expected_response="move_pages_generator: No results for `[[PageNeedsMovingTo::What is superintelligence?]]|limit=1|offset=0`.",
                # TODO: more tests, we probably need to mock wiki API to be able to run tests on stable data
            ),
        ]
