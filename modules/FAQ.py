import asyncio
import datetime

import discord
from modules.module import Module, Response
from config import stampy_id


class FaqModule(Module):
    template_channel_id = 876541727048077312
    feedback_channel_id = 894314718251085845
    faq_user_channel_prefix = 'faq-for-'
    select_message_emoji_name = "👆"
    approve_result_base_name = "green_stamp"
    approve_result_emoji_name = f"<:{approve_result_base_name}:870032324279033896>"
    reject_result_emoji_name = "🚩"
    reaction_emoji_list = [select_message_emoji_name, approve_result_base_name, reject_result_emoji_name]
    none_of_the_above_text = "None of the above (add this question to the wiki for team Stampy to answer)"
    max_wait = 3600

    channels_waiting_to_return_to_questions = {}

    question_titles_for_large_answers = {}

    def process_message(self, message, client=None):
        if type(message.channel) == discord.DMChannel:
            return Response()  # this module should not respond to dms

        if message.content == "Make me an FAQ channel, stampy":
            return Response(callback=self.start_FAQ_channel, args=[message], confidence=10)
        # elif message.content == "Give me some questions, stampy":
        #    return Response(callback=self.send_first_questions, args=[message], confidence=10)
        elif message.content == "test something for me, stampy":
            return Response(callback=self.test, args=[message], confidence=10)
        elif message.content.endswith("?") and message.channel.name == \
                "faq-for-" + message.author.name.lower().replace(" ", "-") + str(message.author.discriminator):
            return Response(callback=self.look_up_question_from_user, args=[message], confidence=10)

    async def process_raw_reaction_event(self, event, client=None):
        """event is a discord.RawReactionActionEvent object
        Use this to allow modules to handle adding and removing reactions on messages"""
        if event.event_type == "REACTION_REMOVE" or event.member.id == stampy_id \
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

        if event.emoji.name == self.select_message_emoji_name:
            if reaction_message.content == self.none_of_the_above_text:
                await self.add_user_question_to_wiki(reaction_message)
            else:
                question_text = reaction_message.content.removeprefix("Follow-up question: ")\
                                                        .removeprefix("Related question: ")

                await self.serve_answer(event_channel, question_text)

        elif event.emoji.name == self.approve_result_base_name:
            if event.message_id in self.question_titles_for_large_answers:
                answer_page = self.question_titles_for_large_answers[event.message_id]
            else:
                answer_page = reaction_message.content.split("\n")[0]

            await self.send_related_and_follow_up_questions(answer_page, event_channel)

        elif event.emoji.name == self.reject_result_emoji_name:
            if event.message_id in self.question_titles_for_large_answers:
                answer_page = self.question_titles_for_large_answers[event.message_id]
            else:
                answer_page = reaction_message.content.split("\n")[0]

            await self.alert_helpers_and_put_channel_in_feedback_mode(answer_page, event_channel, server,
                    f"https://discord.com/channels/{event.member.guild.id}/{event.channel_id}/{event.message_id}")

    def __str__(self):
        return "FAQ Module"

    # WORKFLOW FUNCTIONS

    async def start_FAQ_channel(self, message):
        server = message.guild
        template_channel = server.get_channel(self.template_channel_id)
        author_with_discriminator = message.author.name + message.author.discriminator
        new_channel = await template_channel.clone(name=self.faq_user_channel_prefix + author_with_discriminator)

        # give the user who just asked for a channel permissions to see that channel
        await new_channel.set_permissions(message.author, overwrite=discord.PermissionOverwrite(view_channel=True))

        if not await self.send_intro(new_channel, message.author.name):
            return Response(text="Something went wrong in the creation of a personal FAQ Channel", confidence=10)

        return Response(text="DEBUG: done!", confidence=10)

    async def send_intro(self, channel, author):
        stampy_intro = self.utils.wiki.get_page_content("MediaWiki:Stampy-intro")
        if stampy_intro:
            await self.utils.send_wrapper(channel, stampy_intro.replace("$username", author))

        suggested_questions = self.utils.wiki.get_page_properties("Initial questions", "SuggestedQuestion")

        if suggested_questions:
            try:
                for q in suggested_questions:
                    await self.send_possible_question_and_react(channel, q["displaytitle"] or q["fulltext"])
                return True
            except (KeyError, IndexError) as e:
                await self.utils.send_wrapper(
                    channel,
                    "Something has gone wrong in the fetching of Initial Questions, the @bot-dev team will come "
                    + "to your rescue shortly.\nWhen they do, show them this: \n" + e
                )
                return False

    async def serve_answer(self, channel, question_text):
        answer_title = self.utils.wiki.get_page_properties(question_text, "CanonicalAnswer")
        if answer_title and 'fulltext' in answer_title[0]:
            answer_response = self.utils.wiki.get_page_properties(answer_title[0]['fulltext'], "Answer")[0]
            answer_text = answer_title[0]['fulltext'] + "\n" + answer_response

            ans_messages = await self.utils.send_wrapper(channel, answer_text)
            if ans_messages:
                if len(ans_messages) != 1:
                    self.question_titles_for_large_answers[ans_messages[-1].id] = answer_title[0]['fulltext']
                await ans_messages[-1].add_reaction(self.approve_result_emoji_name)
                await ans_messages[-1].add_reaction(self.reject_result_emoji_name)

            self.increment_page_stats("Stats:" + answer_title[0]['fulltext'], "ServedCount")
        else:
            await channel.send("No Canonical Response found for that question")

    async def send_related_and_follow_up_questions(self, answer_page, event_channel):
        self.increment_page_stats("Stats:" + answer_page, "ThumbsUp")

        question_query = self.utils.wiki.get_page_properties(answer_page, "RelatedQuestion", "FollowUpQuestion")

        if question_query:
            for rel_q_name in question_query["RelatedQuestion"]:
                rel_q_text = rel_q_name["displaytitle"] or rel_q_name["fulltext"]
                await self.send_possible_question_and_react(event_channel, "Related question: " + rel_q_text)
            for fol_q_name in question_query["FollowUpQuestion"]:
                fol_q_text = fol_q_name["displaytitle"] or fol_q_name["fulltext"]
                await self.send_possible_question_and_react(event_channel, "Related question: " + fol_q_text)
        else:
            await self.utils.send_wrapper(event_channel, "Thanks for marking the answers as good, there are " +
                                          "unfortunately no related or follow up questions to that answer. If you " +
                                          "have any questions after reading that, feel free to ask them here and ill " +
                                          "do my best to help with answers to them.")

    async def alert_helpers_and_put_channel_in_feedback_mode(self, answer_page, event_channel, server, link_to_message):
        self.increment_page_stats("Stats:" + answer_page, "ThumbsDown")
        flagged_content_message = self.utils.wiki.get_page_content("MediaWiki:Stampy-flagged")
        if flagged_content_message:
            flagged_message = await self.utils.send_wrapper(event_channel, flagged_content_message)

            feedback_channel = server.get_channel(self.feedback_channel_id)
            await self.utils.send_wrapper(
                feedback_channel,
                f"There was a question flagged as having issues over in channel <#{event_channel.id}>.\n" +
                f"The exact message that was flagged was {link_to_message}"
            )
            task = asyncio.create_task(self.return_to_questions_after_flag(answer_page, event_channel,
                                                                           flagged_message[0].created_at, 900))
            self.channels_waiting_to_return_to_questions[event_channel.id] = task

            # TODO: if conversation with stampy starts up some other way (user asks stampy a question) we need to kill these
            # TODO: use self.channels_...to_questions[channelid].cancel()

    async def return_to_questions_after_flag(self, answer_page, event_channel, flag_timestamp, wait):
        await asyncio.sleep(wait)
        # let the flag be resolved between the user and helpers, and only then continue
        # the metric is that at least two messages have been sent, and no further messages have been sent for a while
        earliest_message_timestamp = None
        latest_message_timestamp = None
        async for message in event_channel.history(limit=2):
            earliest_message_timestamp = min(message.created_at, earliest_message_timestamp) if earliest_message_timestamp else message.created_at
            latest_message_timestamp = max(message.created_at, latest_message_timestamp) if latest_message_timestamp else message.created_at
        if earliest_message_timestamp > flag_timestamp \
                and latest_message_timestamp < datetime.datetime.utcnow() - datetime.timedelta(seconds=20): #wait):
            await self.send_related_and_follow_up_questions(answer_page, event_channel)
        else:
            new_wait = min(2*wait, self.max_wait)  # if no conversation has happened, or it is still ongoing wait
            new_task = asyncio.create_task(self.return_to_questions_after_flag(answer_page, event_channel,
                                                                               flag_timestamp, new_wait))
            self.channels_waiting_to_return_to_questions[event_channel.id] = new_task

    async def look_up_question_from_user(self, message):
        direct_match_text = self.utils.wiki.get_page_content(message.content)
        if direct_match_text:
            await self.serve_answer(message.channel, message.content)
            return Response(text="", confidence=10)

        questions_matched_by_semanticsearch = ["SemanticSearchPlaceholder1", "SemanticSearchPlaceholder2"]
        # TODO: eventually connect this to something
        for question_text in questions_matched_by_semanticsearch:
            await self.send_possible_question_and_react(message.channel, question_text)
        reply = await message.reply(self.none_of_the_above_text)
        if reply:
            await reply.add_reaction(self.select_message_emoji_name)

        return Response(text="", confidence=10)

    async def add_user_question_to_wiki(self, none_message):
        question_message = await none_message.channel.fetch_message(none_message.reference.message_id)
        self.utils.wiki.edit(question_message.content, f"Question Asked by user {question_message.author.name} during "
                             + "the course of an FAQ session")

        wiki_page_link = f"https://stampy.ai/wiki/{question_message.content.replace(' ', '_').replace('?','%3F')}"
        await self.utils.send_wrapper(
            none_message.channel,
            "Adding your question to the wiki. If you would like to elaborate on the question " +
            f"you can head over to {wiki_page_link}.\nWhenever someone answers it, they will let you know"
        )

    # GENERAL FUNCTIONS

    async def send_possible_question_and_react(self, channel, question_title):
        sq_message = await self.utils.send_wrapper(channel, question_title)
        if sq_message:
            await sq_message[-1].add_reaction(self.select_message_emoji_name)

    def increment_page_stats(self, stats_page_name, stat_name, fail_if_stat_not_found=False):
        """Increments the stat with the name `stat_name` on the page with name `stats_page_name`."""
        stats_served_count = self.utils.wiki.get_page_properties(stats_page_name, stat_name)
        if stats_served_count:
            stat_count_incremented = stats_served_count[0]+1
        else:
            if fail_if_stat_not_found:
                raise ValueError(f"Stat {stat_name} was not present on page {stats_page_name}." +
                                 "If you wished to create the property, unset the failIfStatNotFound parameter")
            else:
                stat_count_incremented = 1
        body = {
            "action": "pfautoedit",
            "form": "Stats",
            "target": stats_page_name,
            "format": "json",
            "query": f"stats[{stat_name.lower()}]={stat_count_incremented}",
        }
        print("DEBUG:" + str(self.utils.wiki.post(body)))

def get_base_name(emoji):
    """this is a necesary evil, we could use exclusively custom emotes to avoid having to use this"""
    if isinstance(emoji, str):
        return emoji
    else:
        return emoji.name
