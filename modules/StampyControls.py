"""
Allows devs to manage some Stampy functions

Reboot
Reboot Stampy according to `BOT_REBOOT`
`reboot`

Stats
Stats about Stampy, like resource usage and modules loaded
`stats`

Reset invite roles
reset the roles for people with invitation permissions
`resetinviteroles`
"""

import os
import sys
from typing import Optional, cast

import discord

from config import (
    TEST_RESPONSE_PREFIX,
    bot_control_channel_ids,
    member_role_id,
    Stampy_Path,
    bot_reboot,
)
from modules.module import IntegrationTest, Module, Response
from servicemodules.serviceConstants import Services
from utilities import (
    Utilities,
    get_github_info,
    get_memory_usage,
    get_running_user_info,
    get_question_id,
    is_bot_dev,
)
from utilities.serviceutils import ServiceMessage


class StampyControls(Module):
    """Module to manage stampy controls like reboot and resetinviteroles"""

    BOT_TEST_MESSAGE = "I'm alive!"
    REBOOT_MESSAGE = "Rebooting..."
    REBOOT_DENIED_MESSAGE = "You're not my supervisor!"

    def __init__(self):
        super().__init__()
        self.routines = {
            "reboot": self.reboot,
            "stats": self.get_stampy_stats,
            "add member role to everyone": self.add_member_role,
        }

    def is_at_module(self, message: ServiceMessage) -> Optional[str]:
        if text := self.is_at_me(message):
            return text.lower() in self.routines

    async def send_control_message(self, message: ServiceMessage, text: str) -> None:
        if self.utils.test_mode:
            question_id = get_question_id(message)
            await message.channel.send(
                TEST_RESPONSE_PREFIX + str(question_id) + ": " + text
            )
        else:
            await message.channel.send(text)

    def process_message(self, message: ServiceMessage) -> Response:
        if self.is_at_module(message):
            routine_name = cast(str, self.is_at_me(message)).lower()
            routine = self.routines[routine_name]
            return Response(
                confidence=10,
                callback=routine,
                why=f"{message.author.display_name} said '{routine_name}', which is a special command, so I ran the {routine_name} routine",
                args=[message],
            )
        return Response()

    @staticmethod
    async def reboot(message: ServiceMessage) -> Response:
        if (
            hasattr(message.channel, "id")
            and message.channel.id in bot_control_channel_ids
        ):
            asked_by_dev = is_bot_dev(message.author)
            if asked_by_dev:
                if bot_reboot and not os.path.exists(Stampy_Path):
                    return Response(
                        confidence=10,
                        why=f"I couldn't find myself at this path: {Stampy_Path}",
                        text="I need to do some soul-searching.",
                    )
                await message.channel.send("Rebooting...")
                sys.stdout.flush()
                Utilities.get_instance().stop.set()
                if bot_reboot == "exec":
                    # Alternative: self-managed reboot, without needing external loop.
                    # BUG: When rebooting, Flask throws an error about port 2300
                    # being still in use. However the app seems to keep working.
                    os.execvp(
                        "bash", ["bash", "--login", "-c", f"python3 {Stampy_Path}"]
                    )
                else:
                    # expecting external infinite loop to make it a reboot.
                    # return value of "42" can be used to distinguish from
                    # intentional shutdown vs others.
                    Utilities.get_instance().exit_value = 42
                    sys.exit("Shutting down, expecting a reboot")
            return Response(
                confidence=10,
                why=f"{message.author.display_name} tried to kill me! They said 'reboot'",
                text="You're not my supervisor!",
            )
        return Response(
            confidence=10,
            why=f"{message.author.display_name} tried to kill me! They said 'reboot'",
            text="This is not the place for violent murder of an agent.",
        )

    async def add_member_role(self, message: ServiceMessage) -> Response:
        if message.service != Services.DISCORD:
            return Response(
                confidence=10, text="This feature is only available on Discord"
            )
        if not member_role_id:
            return Response(confidence=10, text="Variable member_role_id not defined")

        guild = message._message.guild
        member_role = discord.utils.get(guild.roles, id=int(member_role_id))
        if not member_role:
            return Response(
                confidence=10,
                why=f"{message.author.display_name} asked to add member role",
                text="this server doesn't have a member role yet",
            )
        asked_by_mod = discord.utils.get(message.author.roles, name="mod")
        if not asked_by_mod:
            return Response(
                confidence=10,
                why=f"{message.author.display_name} asked to add member role",
                text=f"naughty <@{message.author.id}>, you are not a mod :face_with_raised_eyebrow:",
            )

        members = list(filter(lambda m: member_role not in m.roles, guild.members))
        if not members:
            return Response(
                confidence=10,
                why=f"{message.author.display_name} asked to add member role",
                text="but everybody is a member already :shrug:",
            )
        len_members = len(members)
        await self.send_control_message(
            message,
            f"[adding member role to {len_members} users, this might take a moment...]",
        )

        done = []
        i = 0
        for member in members:
            await member.add_roles(member_role)
            done.append(member.name)
            i += 1
            if i % 20 == 0:
                await self.send_control_message(
                    message,
                    f'[... new members {i}/{len_members}: {", ".join(done)} ...]',
                )
                done = []
        if done:
            await self.send_control_message(
                message, f'[... new members {i}/{len_members}: {", ".join(done)}]'
            )

        return Response(
            confidence=10,
            why=f"{message.author.display_name} asked to add member role",
            text="[... done adding member role]",
        )

    def create_stampy_stats_message(self) -> str:
        git_message = get_github_info()
        run_message = get_running_user_info()
        memory_message = get_memory_usage()
        runtime_message = self.utils.get_time_running()
        modules_message = self.utils.list_modules()
        # scores_message = self.utils.modules_dict["StampsModule"].get_user_scores()
        return "\n\n".join(
            [git_message, run_message, memory_message, runtime_message, modules_message]
        )

    async def get_stampy_stats(self, message: ServiceMessage) -> Response:
        """
        TODO: Make this its own module and add number of factoids
        """
        stats_message = self.create_stampy_stats_message()
        return Response(
            confidence=10,
            why=f"because {message.author.display_name} asked for my stats",
            text=stats_message,
        )

    @property
    def test_cases(self) -> list[IntegrationTest]:
        return [
            self.create_integration_test(
                test_message="reboot", expected_response=self.REBOOT_DENIED_MESSAGE
            ),
            self.create_integration_test(
                test_message="stats",
                expected_response=self.create_stampy_stats_message(),
                test_wait_time=2,
                minimum_allowed_similarity=0.8,
            ),
        ]

    def __str__(self):
        return "Stampy Controls Module"
