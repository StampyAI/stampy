import re
import discord
from servicemodules.discordConstants import rob_id
from servicemodules.serviceConstants import Services
from modules.module import Module, Response


class InviteManager(Module):
    def __init__(self):
        Module.__init__(self)
        self.class_name = "InviteManager"
        self.re_request = re.compile(
            r"([pP]lease )?(([cC]an|[cC]ould) you )?(([Cc]reate|[mM]ake|[gG]ive|[gG]enerate) (me )?|"
            "([Cc]an|[mM]ay) [iI] (get|have) )((an|a new|my|\d+) )?[Ii]nvites?( link)?s?,?( please| pls)?"
        )
        self.sorry_message = (
            "Sorry, you don't have the `can-invite` role.\nEither you recently "
            "joined the server, or you've already been given an invite this week"
        )

    def process_message(self, message):
        if message.service != Services.DISCORD:
            return Response()
        guild, invite_role = self.get_guild_and_invite_role()
        if self.is_at_me(message):
            text = self.is_at_me(message)

            m = re.match(self.re_request, text)
            if m:
                member = guild.get_member(int(message.author.id))
                self.log.debug(self.class_name, member=member, author=message.author.id)
                if invite_role in member.roles:
                    return Response(confidence=10, callback=self.post_invite, args=[message])
                else:
                    return Response(
                        confidence=10,
                        text=self.sorry_message,
                        why=f"{member.name} asked for an invite, but they're not allowed one (right now)",
                    )

        # This is either not at me, or not something we can handle
        return Response()

    async def post_invite(self, message):
        """Generate and send one or more invites"""
        guild, invite_role = self.get_guild_and_invite_role()
        welcome = discord.utils.find(lambda c: c.name == "welcome", guild.channels)
        member = guild.get_member(message.author.id)

        text = self.is_at_me(message)
        m = re.search("\d+", text)  # if this is a request for multiple invites
        if m:
            if message.author.id != rob_id:
                return Response(
                    confidence=10,
                    text="Sorry, you can only get 1 invite at a time",
                    why=f"{message.author.name} asked for more than one invite, which isn't allowed",
                )

            count = int(m.group(0))
            if count > 50:
                return Response(
                    confidence=10,
                    text="Sorry, that's too many to ask for at once",
                    why=f"{message.author.name} asked for {count} invites, which is too many",
                )

            return_string = "Here are your invites:"
            for _ in range(count):
                invite = await welcome.create_invite(
                    max_uses=1, temporary=False, unique=True, reason="Requested by %s" % message.author.name,
                )
                return_string += "\n<%s>" % invite.url
            return Response(
                confidence=10,
                text=return_string,
                why=f"{message.author.name} asked for {count} invites, so I generated them",
            )

        # if we're here, only one invite was requested
        invite = await welcome.create_invite(
            max_uses=1, temporary=False, unique=True, reason="Requested by %s" % message.author.name,
        )
        self.log.info(self.class_name, msg="Generated invite", member=member.name, invite=invite)

        # remove the invite role so they only get one
        await member.remove_roles(invite_role)

        return Response(
            confidence=10,
            text="Here you go!: %s\n"
            "This is the only invite I'll give you this week, "
            "and it will only work once, so use it wisely!" % invite.url,
            why="%s asked for an invite so I gave them one" % member.name,
        )

    def __str__(self):
        return "Invite Manager Module"

    @property
    def test_cases(self):
        return [
            self.create_integration_test(
                test_message="can you make me an invite link?", expected_response=self.sorry_message
            )
        ]
