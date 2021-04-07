import sys
import discord
from modules.module import Module
from config import rob_id, stampy_control_channels


class StampyControls(Module):
    """Module to manage stampy controls like reboot and resetinviteroles"""

    def __init__(self):
        super().__init__()
        self.routines = {
            "bot test": self.bot_test,
            "reboot": self.reboot,
            "reply test": self.reply_test,
            "resetinviteroles": self.resetinviteroles,
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
            routine = await self.routines[routine_name]
            result = routine(message)
            return 10, result

    @staticmethod
    async def bot_test(message):
        await message.channel.send("I'm alive!")
        return ""

    @staticmethod
    async def reboot(message):
        if hasattr(message.channel, "name") and message.channel.name in stampy_control_channels:
            if message.author.id == int(rob_id):
                await message.channel.send("Rebooting...")
                sys.stdout.flush()
                exit()
            else:
                await message.channel.send("You're not my supervisor!")
        return ""

    @staticmethod
    async def reply_test(message):
        if message.reference:
            reference = await message.channel.fetch_message(message.reference.message_id)
            reference_text = reference.content
            reply_url = reference_text.split("\n")[-1].strip()

            response = 'This is a reply to message %s:\n"%s"' % (
                message.reference.message_id,
                reference_text,
            )
            response += 'which should be taken as an answer to the question at: "%s"' % reply_url
        else:
            response = "This is not a reply"
        await message.channel.send(response)
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

    def __str__(self):
        return "Stampy Controls Module"
