from module import Module
import asyncio
import discord
import re

class InviteManager(Module):

    def __init__(self):
        Module.__init__(self)
        self.re_request = re.compile(r"""([pP]lease )?(([cC]an|[cC]ould) you )?(([Cc]reate|[mM]ake|[gG]ive|[gG]enerate) (me )?|([Cc]an|[mM]ay) [iI] (get|have) )((an|a new|my) )?[Ii]nvite( link)?,?( please| pls)?""")
        # self.re_request = re.compile(r"""((([Ww]hich|[Ww]hat) vid(eo)? (is|was) (it|that))|
# ?([Ii]n )?([Ww]hich|[Ww]hat)('?s| is| was| are| were)? ?(it|that|the|they|those)? ?vid(eo)?s? ?(where|in which|which)?|
# ?[Vv]id(eo)? ?[Ss]earch) (?P<query>.+)""")
        self.sorry_message = "Sorry, you don't have the `can-invite` role.\nEither you recently joined the server, or you've already been given an invite this week"    

    def canProcessMessage(self, message, client=None):
        if self.isatme(message):
            text = self.isatme(message)
 
            m = re.match(self.re_request, text)
            if m:
                guild = client.guilds[0]
                inviterole = discord.utils.get(guild.roles, name="can-invite")
                member = guild.get_member(message.author.id)
                print(guild, inviterole, member, message.author.id)
                if inviterole in member.roles:
                    return (10, "")
                else:
                    return (10, self.sorry_message)
 
        # This is either not at me, or not something we can handle
        return (0, "")

    async def processMessage(self, message, client=None):
        """Generate and send an invite, if user is allowed"""
        text = self.isatme(message)

        m = re.match(self.re_request, text)  # is this message requesting an invite link?
        if m:
            guild = client.guilds[0]
            inviterole = discord.utils.get(guild.roles, name="can-invite")
            member = guild.get_member(message.author.id)
            if inviterole in member.roles:
                welcome = discord.utils.find(lambda c: c.name == "welcome", guild.channels)
                invite = await welcome.create_invite(max_uses=1,
                                                    temporary=False,
                                                    unique=True,
                                                    reason="Requested by %s" % message.author.name)

                print("Generated invite for", member.name, invite)
                await member.remove_roles(inviterole)  # remove the invite role so they only get one

                return (10, "Here you go!: %s\nThis is the only invite I'll give you this week, and it will only work once, so use it wisely!" % invite.url)
            else:  # user doesn't have the can-invite role
                return (10, self.sorry_message)
        # elif "invitetest" in text:
        #   member = message.author
        #   role = discord.utils.get(message.author.guild.roles, name="can-invite")
        #   if "add" in text:
        #       await member.add_roles(role)
        #       return (10, "Added invite role")
        #   elif "remove" in text:
        #       await member.remove_roles(role)
        #       return (10, "removed invite role")


    def __str__(self):
        return "Invite Manager Module"