import discord
from utilities import Utilities
from modules.module import Module, Response


class FaqModule(Module):
    template_channel_id = 876541727048077312

    def process_message(self, message, client=None):
        if type(message.channel) == discord.DMChannel:
            return Response()  # this module should not respond to dms

        if message.content == "Make me an FAQ channel, stampy":
            return Response(callback=self.start_FAQ_channel, args=[message], confidence=10)
        #elif message.content == "Give me some questions, stampy":
        #    return Response(callback=self.send_first_questions, args=[message], confidence=10)
        elif message.content == "test something for me, stampy":
            return Response(callback=self.test, args=[message], confidence=10)
        else:
            print("didnt get the specific test message")

    async def process_reaction_event(self, reaction, user, event_type="REACTION_ADD", client=None):
        """event_type can be 'REACTION_ADD' or 'REACTION_REMOVE'
        Use this to allow modules to handle adding and removing reactions on messages"""
        return Response()

    async def process_raw_reaction_event(self, event, client=None):
        """event is a discord.RawReactionActionEvent object
        Use this to allow modules to handle adding and removing reactions on messages"""
        return Response()

    def __str__(self):
        return "FAQ Module"

    async def start_FAQ_channel(self, message):
        server = message.guild
        template_channel = server.get_channel(self.template_channel_id)
        author_with_discriminator = message.author.name + message.author.discriminator
        new_channel = await template_channel.clone(name='FAQ for ' + author_with_discriminator)

        # give the user who just asked for a channel permissions to see that channel
        await new_channel.set_permissions(message.author, overwrite=discord.PermissionOverwrite(view_channel=True))



        if not await self.send_first_questions(new_channel):
            return Response(text="", confidence=10)

        return Response(text="DEBUG: done!", confidence=10)

    async def send_intro(self, channel):
        stampy_intro = self.utils.wiki.get_page_content("MediaWiki:Stampy-intro")
        await new_channel.send(stampy_intro.replace("$username", message.author.name))

        suggested_questions = self.utils.wiki.ask("[[Initial_questions]]|?SuggestedQuestion")

        try:
            for q in suggested_questions["query"]["results"]["Initial questions"]["printouts"]["SuggestedQuestion"]:
                sq_message = await channel.send(q["displaytitle"] or q["fulltext"])
                await sq_message.add_reaction("👆")
            return True
        except (KeyError, IndexError) as e:
            await channel.send(
                "Something has gone wrong in the fetching of Initial Questions, the @bot-dev team will come to your rescue shortly.\m"
                + "When they do, show them this: \n" + e)
            return False

    async def test(self, message):
        stampy_intro = self.utils.wiki.get_page("MediaWiki:Stampy-intro")
        print(stampy_intro["query"]["pages"][0]["revisions"][0]["slots"]["main"]["content"])
