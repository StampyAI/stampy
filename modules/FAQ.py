import discord
from modules.module import Module, Response
from config import stampy_id


class FaqModule(Module):
    template_channel_id = 876541727048077312
    faq_user_channel_prefix = 'faq-for-'
    select_message_emoji_name = "👆"
    approve_result_base_name = "green_stamp"
    approve_result_emoji_name = f"<:{approve_result_base_name}:870032324279033896>"
    reject_result_emoji_name = "🚩"
    reaction_emoji_list = [select_message_emoji_name, approve_result_base_name, reject_result_emoji_name]

    def process_message(self, message, client=None):
        if type(message.channel) == discord.DMChannel:
            return Response()  # this module should not respond to dms

        if message.content == "Make me an FAQ channel, stampy":
            return Response(callback=self.start_FAQ_channel, args=[message], confidence=10)
        # elif message.content == "Give me some questions, stampy":
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
        if event.event_type == "REACTION_REMOVE" or event.member.name == "stampy" \
                or event.emoji.name not in self.reaction_emoji_list:
            return  # ignore our own reacts, as well as reacts that have no associated command

        server = event.member.guild
        channel_id = event.channel_id
        event_channel = server.get_channel(channel_id)
        if not event_channel or not event_channel.name.startswith(self.faq_user_channel_prefix):
            return  # ignore all reacts not in FAQ channels, maybe this is unnecessary

        reaction_message = await event_channel.fetch_message(event.message_id)

        if not any(event.emoji.name == get_base_name(x.emoji) and x.me for x in reaction_message.reactions):
            return  # only care about reacts if we have explicitly marked that message as reactable

        # TODO: use the send that can have more than 4000 characters
        if event.emoji.name == self.select_message_emoji_name:
            question_text = reaction_message.content.removeprefix("Follow-up question: ") \
                                                    .removeprefix("Related question: ")
            try:
                answer_title = self.utils.wiki.get_page_properties(question_text, "CanonicalAnswer")[0]['fulltext']
                answer_response = self.utils.wiki.get_page_properties(answer_title, "Answer")[0]
                answer_text = answer_title + "\n" + answer_response

                ans_message = await event_channel.send(
                    answer_text)  # send_wrapper(event_channel, answer_text) #TODO: figure out how to link the message that gets reacted to with the first message with the page name
                await ans_message.add_reaction(self.approve_result_emoji_name)
                await ans_message.add_reaction(self.reject_result_emoji_name)

                self.increment_page_stats("Stats:" + answer_title, "ServedCount")
            except (IndexError, KeyError):
                await event_channel.send("No Canonical Response found for that question")

        elif event.emoji.name == self.approve_result_base_name:
            answer_page = reaction_message.content.split("\n")[0]

            self.increment_page_stats("Stats:" + answer_page, "ThumbsUp")

            await self.send_related_and_follow_up_questions(answer_page, event_channel)

    def __str__(self):
        return "FAQ Module"

    async def start_FAQ_channel(self, message):
        server = message.guild
        template_channel = server.get_channel(self.template_channel_id)
        author_with_discriminator = message.author.name + message.author.discriminator
        new_channel = await template_channel.clone(name=self.faq_user_channel_prefix + author_with_discriminator)

        # give the user who just asked for a channel permissions to see that channel
        await new_channel.set_permissions(message.author, overwrite=discord.PermissionOverwrite(view_channel=True))

        if not await self.send_intro(new_channel, message.author.name):
            return Response(text="", confidence=10)

        return Response(text="DEBUG: done!", confidence=10)

    async def send_intro(self, channel, author):
        stampy_intro = self.utils.wiki.get_page_content("MediaWiki:Stampy-intro")
        if stampy_intro:
            await channel.send(stampy_intro.replace("$username", author))

        suggested_questions = self.utils.wiki.get_page_properties("Initial questions", "SuggestedQuestion")

        if suggested_questions:
            try:
                for q in suggested_questions:
                    sq_message = await channel.send(q["displaytitle"] or q["fulltext"])
                    await sq_message.add_reaction(self.select_message_emoji_name)
                return True
            except (KeyError, IndexError) as e:
                await channel.send(
                    "Something has gone wrong in the fetching of Initial Questions, the @bot-dev team will come to your rescue shortly.\n"
                    + "When they do, show them this: \n" + e)
                return False

    def increment_page_stats(self, stats_page_name, stat_name, failIfStatNotFound=False):
        """Increments the stat with the name `stat_name` on the page with name `stats_page_name`."""
        stats_served_count = self.utils.wiki.get_page_properties(stats_page_name, stat_name)
        if stats_served_count:
            stat_count_incremented = stats_served_count[0]+1
        else:
            if failIfStatNotFound:
                raise ValueError(f"Stat {stat_name} was not present on page {stats_page_name}." +
                                 "If you wished to create the property, unset the failIfStatNotFound parameter")
            else:
                stat_count_incremented = 1
        body = {
            "action": "pfautoedit",
            "form": "Stats",
            "target": stats_page_name,
            "format": "json",
            "query": f"Stats[{stat_name.lower()}]={stat_count_incremented}",
        }
        print("DEBUG:" + str(self.utils.wiki.post(body)))

    async def send_related_and_follow_up_questions(self, answer_page, event_channel):
        question_query = self.utils.wiki.get_page_properties(answer_page, "RelatedQuestion", "FollowUpQuestion")

        for rel_q_name in question_query["RelatedQuestion"]:
            rel_q_text = rel_q_name["displaytitle"] or rel_q_name["fulltext"]
            sq_message = await event_channel.send("Related question: " + rel_q_text)
            await sq_message.add_reaction(self.select_message_emoji_name)
        for fol_q_name in question_query["FollowUpQuestion"]:
            fol_q_text = fol_q_name["displaytitle"] or fol_q_name["fulltext"]
            sq_message = await event_channel.send("Related question: " + fol_q_text)
            await sq_message.add_reaction(self.select_message_emoji_name)


def get_base_name(emoji):
    """this is a necesary evil, we could use exclusively custom emotes to avoid having to use this"""
    if isinstance(emoji, str):
        return emoji
    else:
        return emoji.name
