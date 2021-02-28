import re
import json
import discord
from modules.module import Module


class Reply(Module):
    def __str__(self):
        return "YouTube Reply Posting Module"

    def __init__(self):
        Module.__init__(self)

    def isPostRequest(self, text):
        """Is this message asking us to post a reply?"""
        print(text)
        if text:
            return text.lower().endswith("post this") or text.lower().endswith(
                "send this"
            )
        else:
            return False

    def isAllowed(self, message, client):
        """[Deprecated] Is the message author authorised to make stampy post replies?"""
        postingrole = discord.utils.find(
            lambda r: r.name == "poaster", message.guild.roles
        )
        return postingrole in message.author.roles

    def extractReply(self, text):
        """Pull the text of the reply out of the message"""
        lines = text.split("\n")
        replymessage = ""
        for line in lines:
            # pull out the quote syntax "> " and a user if there is one
            match = re.match("([^#]+#\d\d\d\d )?> (.*)", line)
            if match:
                replymessage += match.group(2) + "\n"

        return replymessage

    def postReply(self, text, questionid):
        """Actually post the reply to YouTube. Currently this involves a horrible hack"""

        # first build the dictionary that will be passed to youtube.comments().insert as the 'body' arg
        body = {
            "snippet": {
                "parentId": questionid,
                "textOriginal": text,
                "authorChannelId": {"value": "UCFDiTXRowzFvh81VOsnf5wg"},
            }
        }

        # now we're going to put it in a json file, which CommentPoster.py will read and send it
        with open("topost.json") as postfile:
            topost = json.load(postfile)

        topost.append(body)

        with open("topost.json", "w") as postfile:
            json.dump(topost, postfile, indent="\t")

        print("dummy, posting %s to %s" % (text, questionid))

    def canProcessMessage(self, message, client=None):
        """From the Module() Interface. Is this a message we can process?"""
        if self.isatme(message):
            text = self.isatme(message)

            if self.isPostRequest(text):
                print("this is a posting request")
                # if self.isAllowed(message, client):
                #   print("the user is allowed")
                #   return (9, "")
                # else:
                #   return (9, "Only people with the `poaster` role can do that")
                return (9, "Ok, I'll post this when it has more than 30 stamp points")

        return (0, "")

    async def processMessage(self, message, client):
        """From the Module() Interface. Handle a reply posting request message"""
        return (0, "")

    async def postMessage(self, message, approvers=[]):

        approvers.append(message.author)
        approvers = [a.name for a in approvers]
        approvers = list(set(approvers))  # deduplicate

        if len(approvers) == 1:
            approverstring = approvers[0]
        elif len(approvers) == 2:
            approverstring = " and ".join(approvers)
        else:
            approvers[-1] = "and " + approvers[-1]
            approverstring = ", ".join(approvers)  # oxford comma baybee

        text = self.isatme(message)  # strip off stampy's name
        replymessage = self.extractReply(text)
        replymessage += (
            "\n -- _I am a bot. This reply was approved by %s_" % approverstring
        )

        report = ""

        if message.reference:  # if this is a reply
            reference = await message.channel.fetch_message(
                message.reference.message_id
            )
            reftext = reference.clean_content
            questionURL = reftext.split("\n")[-1].strip("<> \n")
            if "youtube.com" not in questionURL:
                return "I'm confused about what YouTube comment to reply to..."
        else:
            if not self.utils.latest_question_posted:
                # return (10, "I can't do that because I don't remember the URL of the last question I posted here. I've probably been restarted since that happened")
                report = "I don't remember the URL of the last question I posted here, so I've probably been restarted since that happened. I'll just post to the dummy thread instead...\n\n"
                self.utils.latest_question_posted = {
                    "url": "https://www.youtube.com/watch?v=vuYtSDMBLtQ&lc=Ugx2FUdOI6GuxSBkOQd4AaABAg"
                }  # use the dummy thread

            questionURL = self.utils.latest_question_posted["url"]

        questionid = re.match(r".*lc=([^&]+)", questionURL).group(1)

        quotedreplymessage = "> " + replymessage.replace("\n", "\n> ")
        report += "Ok, posting this:\n %s\n\nas a response to this question: <%s>" % (
            quotedreplymessage,
            questionURL,
        )

        self.postReply(replymessage, questionid)

        return report

    async def evaluateMessageStamps(self, message):
        "Return the total stamp value of all the stamps on this message, and a list of who approved it"
        total = 0
        print("Evaluating message")

        approvers = []

        reactions = message.reactions
        if reactions:
            print(reactions)
            for reaction in reactions:
                reacttype = getattr(reaction.emoji, "name", "")
                if reacttype in ["stamp", "goldstamp"]:
                    print("STAMP")
                    users = await reaction.users().flatten()
                    for user in users:
                        approvers.append(user)
                        print("  From", user.id, user)
                        stampvalue = self.utils.modules_dict[
                            "StampsModule"
                        ].get_user_stamps(user)
                        total += stampvalue
                        print("  Worth", stampvalue)

        return (total, approvers)

    def hasBeenRepliedTo(self, message):
        reactions = message.reactions
        print("Testing if question has already been replied to")
        print("The message has these reactions:", reactions)
        if reactions:
            for reaction in reactions:
                reacttype = getattr(reaction.emoji, "name", reaction.emoji)
                print(reacttype)
                if reacttype in ["📨", ":incoming_envelope:"]:
                    print("Message has envelope emoji, it's already replied to")
                    return True
                elif reacttype in ["🚫", ":no_entry_sign:"]:
                    print("Message has no entry sign, it's vetoed")
                    return True

        print("Message has no envelope emoji, it has not already replied to")
        return False

    async def processRawReactionEvent(self, event, client=None):
        eventtype = event.event_type
        emoji = getattr(event.emoji, "name", event.emoji)

        if emoji in ["stamp", "goldstamp"]:
            print("GUILD = ", self.utils.GUILD)
            guild = discord.utils.find(
                lambda g: g.name == self.utils.GUILD, client.guilds
            )
            channel = discord.utils.find(
                lambda c: c.id == event.channel_id, guild.channels
            )
            message = await channel.fetch_message(event.message_id)
            if self.isatme(message) and self.isPostRequest(self.isatme(message)):
                #   self.maybePostMessage(message)

                # print("isatme:", isatme(message))
                # print("isPostRequest", self.isPostRequest(isatme(message)))
                # print(await self.evaluateMessageStamps(message))

                if self.hasBeenRepliedTo(message):  # did we already reply?
                    return

                stampscore, approvers = await self.evaluateMessageStamps(message)
                if stampscore > 30:
                    report = await self.postMessage(message, approvers)
                    await message.add_reaction(
                        "📨"
                    )  # mark it with an envelope to show it was sent
                    await channel.send(report)
                else:
                    report = (
                        "This reply has %s stamp points. I will send it when it has 30"
                        % stampscore
                    )
                    await channel.send(report)

        # if message.author.id == 736241264856662038:  # votes for stampy don't affect voting
        #   return
        # if message.author.id == event.user_id:  # votes for yourself don't affect voting
        #   if eventtype == 'REACTION_ADD' and emoji in ['stamp', 'goldstamp']:
        #       await channel.send("<@" + str(event.user_id) + "> just awarded a stamp to themselves...")
        #   return

        # if emoji in ['stamp', 'goldstamp']:

        #   msgid = event.message_id
        #   fromid = event.user_id
        #   toid = message.author.id
        #   # print(msgid, re)
        #   string = "%s,%s,%s,%s" % (msgid, emoji, fromid, toid)
        #   print(string)

        #   print("### STAMP AWARDED ###")
        #   self.addvote(emoji, fromid, toid, negative=(eventtype=='REACTION_REMOVE'))
        #   self.save_votesdict_to_json()
        #   print("Score before stamp:", self.get_user_stamps(toid))
        #   self.calculate_stamps()
        #   print("Score after stamp:", self.get_user_stamps(toid))
        #   # "msgid,type,from,to"
