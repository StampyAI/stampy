import sys
import discord
from modules.module import Module
from config import rob_id, stampy_control_channel_names
from utilities import get_github_info, get_memory_usage, get_running_user_info


class StampyControls(Module):
    """Module to manage stampy controls like reboot and resetinviteroles"""

    def __init__(self):
        super().__init__()
        self.routines = {
            "bot test": self.bot_test,
            "reboot": self.reboot,
            "resetinviteroles": self.resetinviteroles,
            "stats": self.get_stampy_stats,
        }

    def is_at_module(self, message):
        text = self.is_at_me(message)
        if text:
            return text.lower() in self.routines
        return False

    def can_process_message(self, message, client=None):
        if self.is_at_module(message):
            return 10, ""
        return 0, ""

    async def process_message(self, message, client=None):
        if self.is_at_module(message):
            routine_name = self.is_at_me(message).lower()
            routine = self.routines[routine_name]
            result = await routine(message)
            return 10, result

    @staticmethod
    async def bot_test(message):
        await message.channel.send("I'm alive!")
        return ""

    @staticmethod
    async def reboot(message):
        if hasattr(message.channel, "name") and message.channel.name in stampy_control_channel_names:
            if message.author.id == int(rob_id):
                await message.channel.send("Rebooting...")
                sys.stdout.flush()
                exit()
            else:
                await message.channel.send("You're not my supervisor!")
        return ""

    async def resetinviteroles(self, message):
        print("[resetting can-invite roles]")
        await message.channel.send("[resetting can-invite roles, please wait]")
        guild = discord.utils.find(lambda g: g.name == self.utils.GUILD, self.utils.client.guilds)
        print(self.utils.GUILD, guild)
        role = discord.utils.get(guild.roles, name="can-invite")
        print("there are", len(guild.members), "members")
        reset_users_count = 0
        for member in guild.members:
            if self.utils.get_user_score(member) > 0:
                print(member.name, "can invite")
                await member.add_roles(role)
                reset_users_count += 1
            else:
                print(member.name, "has 0 stamps, can't invite")
        await message.channel.send("[Invite Roles Reset for %s users]" % reset_users_count)
        return ""

    async def get_stampy_stats(self, message):
        """
        TODO: Make this its own module and add number of factoids
        """
        git_message = get_github_info()
        run_message = get_running_user_info()
        memory_message = get_memory_usage()
        runtime_message = self.utils.get_time_running()
        modules_message = self.utils.list_modules()
        # scores_message = self.utils.modules_dict["StampsModule"].get_user_scores()
        await message.channel.send(
            "\n\n".join([git_message, run_message, memory_message, runtime_message, modules_message])
        )
        return ""

    def __str__(self):
        return "Stampy Controls Module"
