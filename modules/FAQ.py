import asyncio
import datetime
import re
from asyncio import Task

import discord

from modules.module import Module, Response
from servicemodules.discordConstants import faq_hub_channel_id, stampy_id, feedback_channel_id
from utilities.discordutils import DiscordMessage
from utilities.serviceutils import ServiceMessage


class FAQ(Module):
    select_message_emoji_name = "👆"
    approve_result_base_name = "green_stamp"
    approve_result_emoji_name = f"<:{approve_result_base_name}:870032324279033896>"
    reject_result_emoji_name = "🚩"
    reaction_emoji_list = [select_message_emoji_name, approve_result_base_name, reject_result_emoji_name]
    faq_user_channel_prefix = "FAQ session with "
    none_of_the_above_text = "None of the above (add this question to the wiki for team Stampy to answer)"
    max_wait = 3600

    question_titles_for_large_answers: dict["id": str] = {}
    none_of_the_above_questions: dict["id": str] = {}
    channels_waiting_to_return_to_questions: dict[int, Task] = {}

    def process_message(self, message: ServiceMessage):
        # if type(message.channel) == discord.DMChannel:
        #     return Response()
        if re.match(r"Stampy, I have a large amount of questions", message.content):
            return Response(confidence=10, callback=self.start_faq_session, args=[message])
        elif message.content.endswith("?") and message.channel.name.endswith(f"[{message.author.id}]"):
            return Response(callback=self.look_up_question_from_user, args=[message], confidence=10)

    async def process_raw_reaction_event(self, event):
        if event.event_type == "REACTION_REMOVE" or str(event.member.id) == stampy_id \
                or event.emoji.name not in self.reaction_emoji_list:
            return  # ignore our own reacts, as well as reacts that have no associated command

        server = event.member.guild
        channel_id = event.channel_id
        event_channel = discord.utils.get(server.get_channel(int(faq_hub_channel_id)).threads, id=channel_id)
        if not event_channel or not event_channel.name.startswith(self.faq_user_channel_prefix):
            return  # ignore all reacts not in FAQ channels

        reacted_message = await event_channel.fetch_message(event.message_id)

        if not any(event.emoji.name == get_base_name(x.emoji) and x.me for x in reacted_message.reactions):
            return  # only process if stampy put a reaction in a message and the user clicked it to add another

        if event.emoji.name == self.select_message_emoji_name:
            if reacted_message.content == self.none_of_the_above_text:
                await self.add_user_question_to_wiki(reacted_message)
            else:
                question_text = reacted_message.content.removeprefix("Follow-up question: ")\
                                                        .removeprefix("Related question: ")

                await self.serve_answer(event_channel, question_text)

        elif event.emoji.name == self.approve_result_base_name:
            if event.message_id in self.question_titles_for_large_answers:
                answer_page = self.question_titles_for_large_answers[event.message_id]
            else:
                answer_page = reacted_message.content.split("\n")[0]

            await self.send_related_and_follow_up_questions(answer_page, event_channel)

        elif event.emoji.name == self.reject_result_emoji_name:
            if event.message_id in self.question_titles_for_large_answers:
                answer_page = self.question_titles_for_large_answers[event.message_id]
            else:
                answer_page = reacted_message.content.split("\n")[0]

            await self.alert_helpers_and_put_channel_in_feedback_mode(
                answer_page, event_channel, server,
                f"https://discord.com/channels/{event.member.guild.id}/{event.channel_id}/{event.message_id}")

    ###########
    # INITIALIZATION FLOW
    ###########

    async def start_faq_session(self, message: ServiceMessage):
        if message.channel.id != faq_hub_channel_id or not isinstance(message, DiscordMessage):
            return
            # I am not familiar enough with slack to add threads functionality to all services. refactoring is needed.
        faq_thread = await self.get_thread_for_user(message.author.display_name, message.author.id)

        if not faq_thread or not await self.send_intro(faq_thread, message.author.id):
            return Response(text="Something went wrong in the creation of a personal FAQ Channel", confidence=10)

        return Response(text="Sure thing, ask me all the questions you want :)", confidence=10)

    async def get_thread_for_user(self, display_name, author_id):
        faq_name = f"{self.faq_user_channel_prefix}{display_name} [{author_id}]"
        original_channel = self.utils.client.guilds[0].get_channel(int(faq_hub_channel_id))
        for thread in original_channel.threads:
            if thread.name.endswith(f"[{author_id}]"):
                return thread
        async for thread in original_channel.archived_threads():
            if thread.name.endswith(f"[{author_id}]"):
                await thread.edit(archived=False)
                return thread

        return await original_channel.create_thread(name=faq_name)

    async def send_intro(self, channel, author_id):
        stampy_intro = self.utils.wiki.get_page_content("MediaWiki:Stampy-intro")
        if stampy_intro:
            for chunk in self.utils.split_message_for_discord(stampy_intro.replace("$username", f"<@{author_id}>")):
                await channel.send(chunk)

        suggested_questions = self.utils.wiki.get_page_properties("Initial questions", "SuggestedQuestion")

        if suggested_questions:
            try:
                for q in suggested_questions:
                    await self.send_possible_question_and_react(channel, q["fulltext"])
                    # q["displaytitle"] or # TODO: figure out a way to show displaytitle without breaking things
                return True
            except (KeyError, IndexError) as e:
                for chunk in self.utils.split_message_for_discord(
                        "Something has gone wrong in the fetching of Initial Questions, the @bot-dev team will come "
                        + "to your rescue shortly.\nWhen they do, show them this: \n" + e
                ):
                    await channel.send(chunk)
        return False

    ###########
    # QUESTION EXPANSION AND FEEDBACK FLOW
    ###########

    async def look_up_question_from_user(self, message):
        direct_match_text = self.utils.wiki.get_page_content(message.content)
        if direct_match_text:
            await self.serve_answer(message.channel, message.content)
            return Response(text="", confidence=10)

        questions_matched_by_semanticsearch = ["SemanticSearchPlaceholder1", "SemanticSearchPlaceholder2"]
        # TODO: eventually connect this to something
        for question_text in questions_matched_by_semanticsearch:
            await self.send_possible_question_and_react(message.channel, question_text)
        none_of_the_above_msg = await self.send_possible_question_and_react(message.channel, question_text)
        if none_of_the_above_msg:
            self.none_of_the_above_questions[str(none_of_the_above_msg.id)] = question_text

        return Response(text="", confidence=10)

    async def serve_answer(self, channel, question_text):
        answer_title = self.utils.wiki.get_page_properties(question_text, "CanonicalAnswer")
        if answer_title and 'fulltext' in answer_title[0]:
            answer_response = self.utils.wiki.get_page_properties(answer_title[0]['fulltext'], "Answer")[0]
            answer_text = answer_title[0]['fulltext'] + "\n" + answer_response

            ####
            answer_chunks = self.utils.split_message_for_discord(answer_text)
            if answer_chunks:
                for chunk in answer_chunks[:-1]:
                    channel.send(chunk)
                last_message = await channel.send(answer_chunks[-1])
                await last_message.add_reaction(self.approve_result_emoji_name)
                await last_message.add_reaction(self.reject_result_emoji_name)

                if len(answer_chunks) > 1:
                    self.question_titles_for_large_answers[str(last_message.id)] = answer_title[0]['fulltext']
            # self.increment_page_stats("Stats:" + answer_title[0]['fulltext'], "ServedCount")
        else:
            await channel.send("No Canonical Response found for that question")

    async def add_user_question_to_wiki(self, none_message):
        question_message = await none_message.channel.fetch_message(none_message.reference.message_id)
        self.utils.wiki.edit(question_message.content, f"Question Asked by user {question_message.author.name} during "
                             + "the course of an FAQ session")

        wiki_page_link = f"https://stampy.ai/wiki/{question_message.content.replace(' ', '_').replace('?','%3F')}"
        none_message.channel.send(
            "Adding your question to the wiki. If you would like to elaborate on the question " +
            f"you can head over to {wiki_page_link}.\nWhenever someone answers it, they will let you know"
        )

    async def send_related_and_follow_up_questions(self, answer_page, event_channel):
        # self.increment_page_stats("Stats:" + answer_page, "ThumbsUp")

        question_query = self.utils.wiki.get_page_properties(answer_page, "RelatedQuestion", "FollowUpQuestion")

        if question_query and (question_query["RelatedQuestion"] or question_query["FollowUpQuestion"]):
            for rel_q_name in question_query["RelatedQuestion"]:
                rel_q_text = rel_q_name["fulltext"]  # rel_q_name["displaytitle"] or
                await self.send_possible_question_and_react(event_channel, "Related question: " + rel_q_text)
            for fol_q_name in question_query["FollowUpQuestion"]:
                fol_q_text = fol_q_name["fulltext"]  # fol_q_name["displaytitle"] or
                await self.send_possible_question_and_react(event_channel, "Related question: " + fol_q_text)
        else:
            await event_channel.send("Thanks for marking the answers as good, there are " +
                                     "unfortunately no related or follow up questions to that answer. If you " +
                                     "have any questions after reading that, feel free to ask them here and ill " +
                                     "do my best to help with answers to them.")

    ###########
    # QUESTION EXPANSION AND FEEDBACK FLOW
    # TODO: this could be made more robust
    ###########

    async def alert_helpers_and_put_channel_in_feedback_mode(self, answer_page, event_channel, server, link_to_message):
        # self.increment_page_stats("Stats:" + answer_page, "ThumbsDown")
        flagged_content_message = self.utils.wiki.get_page_content("MediaWiki:Stampy-flagged")
        if flagged_content_message:
            for chunk in self.utils.split_message_for_discord(flagged_content_message):
                await event_channel.send(chunk)

            feedback_channel = server.get_channel(int(feedback_channel_id))
            feedback_message = await feedback_channel.send(
                f"There was a question flagged as having issues over in channel <#{event_channel.id}>.\n" +
                f"The exact message that was flagged was {link_to_message}"
            )
            task = asyncio.create_task(self.return_to_questions_after_flag(answer_page, event_channel,
                                                                           feedback_message.created_at, 900))
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
            earliest_message_timestamp = min(message.created_at, earliest_message_timestamp) \
                if earliest_message_timestamp else message.created_at
            latest_message_timestamp = max(message.created_at, latest_message_timestamp) \
                if latest_message_timestamp else message.created_at
        if earliest_message_timestamp > flag_timestamp \
                and latest_message_timestamp < datetime.datetime.utcnow() - datetime.timedelta(seconds=wait):
            await self.send_related_and_follow_up_questions(answer_page, event_channel)
        else:
            new_wait = min(2*wait, self.max_wait)  # if no conversation has happened, or it is still ongoing wait
            new_task = asyncio.create_task(self.return_to_questions_after_flag(answer_page, event_channel,
                                                                               flag_timestamp, new_wait))
            self.channels_waiting_to_return_to_questions[event_channel.id] = new_task

    ###########
    # GENERIC USE FUNCTIONS
    ###########

    async def send_possible_question_and_react(self, channel, question_title):
        chunks = self.utils.split_message_for_discord(question_title)
        for i, chunk in enumerate(chunks):
            msg = await channel.send(chunk)
            if i == len(chunks)-1:
                await msg.add_reaction(self.select_message_emoji_name)
        return msg

    """command_dict: dict["re", tuple[function, list["args"]]] = {
        : (, [])
    }"""


def get_base_name(emoji):
    """discord handles default unicone emoji and custom emoji differently
    we could use exclusively custom emotes to avoid having to use this"""
    if isinstance(emoji, str):
        return emoji
    else:
        return emoji.name
