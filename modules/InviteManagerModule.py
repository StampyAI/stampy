import re
import discord
from stam import Module


class InviteManagerModule(Module):
    def __init__(self):
        super().__init__()
        self.re_request = re.compile(
            r"([pP]lease )?(([cC]an|[cC]ould) you )?(([Cc]reate|[mM]ake|[gG]ive|[gG]enerate) (me )"
            "?|([Cc]an|[mM]ay) [iI] (get|have) )((an|a new|my) )?[Ii]nvite( link)?,?( please| pls)?"
        )
        self.sorry_message = (
            "Sorry, you don't have the `can-invite` role.\nEither you recently"
            " joined the server, or you've already been given an invite this week"
        )

    def can_process_message(self, message, client=None):
        if self.is_at_me(message):
            text = self.is_at_me(message)

            m = re.match(self.re_request, text)
            if m:
                guild = client.guilds[0]
                invite_role = discord.utils.get(guild.roles, name="can-invite")
                member = guild.get_member(message.author.id)
                if invite_role in member.roles:
                    return 10, ""
                else:
                    return 10, self.sorry_message

        # This is either not at me, or not something we can handle
        return 0, ""

    async def process_message(self, message, client=None):
        """Generate and send an invite, if user is allowed"""
        text = self.is_at_me(message)

        # is this message requesting an invite link?
        m = re.match(self.re_request, text)
        if m:
            guild = client.guilds[0]
            invite_role = discord.utils.get(guild.roles, name="can-invite")
            member = guild.get_member(message.author.id)
            if invite_role in member.roles:
                welcome = discord.utils.find(lambda c: c.name == "welcome", guild.channels)
                invite = await welcome.create_invite(
                    max_uses=1, temporary=False, unique=True, reason="Requested by %s" % message.author.name,
                )

                print("Generated invite for", member.name, invite)
                # remove the invite role so they only get one
                await member.remove_roles(invite_role)

                return (
                    10,
                    "Here you go!: %s\nThis is the only invite I'll give you this week,"
                    " and it will only work once, so use it wisely!" % invite.url,
                )
            else:
                # user doesn't have the can-invite role
                return 10, self.sorry_message

    def __str__(self):
        return "Invite Manager Module"
