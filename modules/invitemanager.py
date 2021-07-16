import re
import discord
from modules.module import Module, Response


class InviteManager(Module):
    def __init__(self):
        Module.__init__(self)
        self.re_request = re.compile(
            r"([pP]lease )?(([cC]an|[cC]ould) you )?(([Cc]reate|[mM]ake|[gG]ive|[gG]enerate) (me )?|"
            "([Cc]an|[mM]ay) [iI] (get|have) )((an|a new|my) )?[Ii]nvite( link)?,?( please| pls)?"
        )
        self.sorry_message = (
            "Sorry, you don't have the `can-invite` role.\nEither you recently "
            "joined the server, or you've already been given an invite this week"
        )

<<<<<<< HEAD
        self.guild = self.utils.client.guilds[0]
        self.invite_role = discord.utils.get(self.guild.roles, name="can-invite")

=======
>>>>>>> 8b1ba87e7802ca04fdc2e7da4f8769877b62f7b9
    def process_message(self, message, client=None):
        if self.is_at_me(message):
            text = self.is_at_me(message)

            m = re.match(self.re_request, text)
            if m:
<<<<<<< HEAD
                member = self.guild.get_member(message.author.id)
                if self.invite_role in member.roles:
                    return Response(confidence=10, callback=self.post_invite, args=[message])
                else:
                    return Response(
                        confidence=10,
                        text=self.sorry_message,
                        why="%s asked for an invite, but they're not allowed one (right now)" % member.name,
                    )

        # This is either not at me, or not something we can handle
        return Response()

    async def post_invite(self, message):
        """Generate and send an invite"""
        welcome = discord.utils.find(lambda c: c.name == "welcome", self.guild.channels)
        member = self.guild.get_member(message.author.id)
        invite = await welcome.create_invite(
            max_uses=1,
            temporary=False,
            unique=True,
            reason="Requested by %s" % message.author.name,
        )
        print("Generated invite for", member.name, invite)

        # remove the invite role so they only get one
        await member.remove_roles(self.invite_role)

        return Response(
            confidence=10,
            text="Here you go!: %s\n"
            "This is the only invite I'll give you this week, "
            "and it will only work once, so use it wisely!" % invite.url,
            why="%s asked for an invite so I gave them one" % member.name,
        )
=======
                guild = client.guilds[0]
                invite_role = discord.utils.get(guild.roles, name="can-invite")
                member = guild.get_member(message.author.id)
                print(guild, invite_role, member, message.author.id)
                if invite_role in member.roles:
                    return Response(confidence=10,
                                    callback=self.post_invite,
                                    args=[message],
                                    kwargs={'client': client}
                                   )
                else:
                    return Response(confidence=10,
                                    text=self.sorry_message,
                                    why="%s asked for an invite, but they're not allowed one (right now)" % member.name
                                   )

        # This is either not at me, or not something we can handle
        return Response()

    async def post_invite(self, message, client=None):
        """Generate and send an invite"""
        guild = client.guilds[0]
        welcome = discord.utils.find(lambda c: c.name == "welcome", guild.channels)
        member = guild.get_member(message.author.id)
        invite = await welcome.create_invite(
            max_uses=1, temporary=False, unique=True, reason="Requested by %s" % message.author.name,
        )
        print("Generated invite for", member.name, invite)

        # remove the invite role so they only get one
        await member.remove_roles(invite_role)

        return Response(confidence=10,
                        text="Here you go!: %s\n"
                             "This is the only invite I'll give you this week, "
                             "and it will only work once, so use it wisely!" % invite.url,
                        why="%s asked for an invite so I gave them one" % member.name
                       )

        return Response()
>>>>>>> 8b1ba87e7802ca04fdc2e7da4f8769877b62f7b9

    def __str__(self):
        return "Invite Manager Module"
