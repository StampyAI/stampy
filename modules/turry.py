import os
import sys
import re
import json
import asyncio
import logging
import traceback
import requests
import discord
import traceback
import websockets
import ssl
from modules.module import Module
import atexit


class Turry(Module):
    def __init__(self):
        Module.__init__(self)
        self.dnd_url = "http://api.aidungeon.io/graphql"
        self.ws_url = "wss://api.aidungeon.io/subscriptions"
        self.timeout = 1800
        self.token = os.getenv("AI_DUNGEON_TOKEN")
        self.ws = None
        self.adventure_id = "a314f913-7b9e-4777-a48a-b8432e0dceaa"
        self.last_seen_id = None

        self.re_do = re.compile(r"(\*|_)((.*\n)*.*)(\*|_)")
        self.re_say = re.compile(r"([^#]+#\d\d\d\d )?> (.*)")
        self.re_story = re.compile(r"^```([\s\S]*?)```$")

        atexit.register(self.exit_handler)
        return

    def can_process_message(self, message, client=None):
        if hasattr(message.channel, "name") and message.channel.name == "seed":
            command, text = self.get_message_type(message)
            if command:
                return 7, ""
        return 0, ""

    async def process_message(self, message, client=None):
        reply = ""
        if hasattr(message.channel, "name") and message.channel.name == "seed":
            command, text = self.get_message_type(message)
            if command:
                self.ws = await self.get_initialized_websocket()
                await message.channel.trigger_typing()
                if command == "do" or command == "say" or command == "story":
                    response = await self.process_game_next(
                        "do", text, self.adventure_id, self.last_seen_id
                    )
                    if response:
                        reply = response[0]
                        self.last_seen_id = response[1]
                if command == "continue":
                    response = await self.process_game_next(
                        "start", "", self.adventure_id, self.last_seen_id
                    )
                    reply = response[0]
                    self.last_seen_id = response[1]
                if reply:
                    return 7, reply
        return 0, ""

    def __str__(self):
        return "Turry's D&D Module"

    async def get_initialized_websocket(self):
        ws = await websockets.connect(self.ws_url, subprotocols=["graphql-ws"])
        await ws.send(
            '{"type":"connection_init","payload":{"token":"' + self.token + '"}}'
        )
        while True:
            resp = await ws.recv()
            print(
                "Turry Module: Message received during websocket initialization to AI Dungeon:"
            )
            print(resp)
            if json.loads(resp)["type"] == "connection_ack":
                break
        return ws

    async def process_game_restart(self):
        ws = self.ws
        await ws.send(
            '{"id":"1","type":"start","payload":{"variables":{"scenarioId":"1666826","prompt":null},"extensions":{},"operationName":null,"query":"mutation ($scenarioId: String, $prompt: String) {  addAdventure(scenarioId: $scenarioId, prompt: $prompt) {    id    publicId    title    description    musicTheme    tags    nsfw    published    createdAt    updatedAt    deletedAt    publicId    __typename  }}","auth":{"token":"hello"}}}'
        )
        # await ws.send('{"id":"1","type":"start","payload":{"variables":{},"extensions":{},"query":"subscription {"userUpdated": {"id": "hasPremium","scales": "__typename"}}","auth":{"token":"hello"}}}')
        while True:
            resp = await ws.recv()
            print("Message received during restart():")
            print(resp)
            json_payload = json.loads(resp)

            if json_payload["type"] == "data" and json_payload["id"] == "1":
                await ws.close()
                adventure_id_new = json_payload["payload"]["data"]["addAdventure"][
                    "publicId"
                ]
                print(adventure_id_new)
                return adventure_id_new

    async def process_game_next(self, command, text, adventure_id, last_seen_id):
        ws = self.ws
        print("adventure id:")
        print(adventure_id)

        # subscribe to current adventure
        await ws.send(
            '{"id":"1","type":"start","payload":{"variables":{"publicId":"'
            + str(adventure_id)
            + '"},"extensions":{},"query":"subscription ($publicId: String) { adventureUpdated(publicId: $publicId) { ...AdventurePlayFragment __typename }}fragment AdventurePlayFragment on Adventure { id playPublicId publicId thirdPerson actionCount lastAction { ...ActionFragment __typename } ...AdventureControllerFragment ...AudioAdventureControllerFragment ...ReviewAdventureControllerFragment __typename}fragment ActionFragment on Action { id text adventureId undoneAt deletedAt __typename}fragment AdventureControllerFragment on Adventure { id actionLoading error gameState events thirdPerson userId characters { id userId name __typename } ...ActionAdventureControllerFragment ...AlterControllerFragment ...QuestControllerFragment ...RememberControllerFragment ...ShareControllerFragment __typename}fragment ActionAdventureControllerFragment on Adventure { id publicId actionCount choices error mode thirdPerson userId worldId characters { id userId name __typename } ...DeathControllerFragment __typename}fragment DeathControllerFragment on Adventure { id publicId mode died __typename}fragment AlterControllerFragment on Adventure { id publicId mode __typename}fragment QuestControllerFragment on Adventure { id publicId lastAction { id text __typename } quests { id text completed active actionGainedId actionCompletedId __typename } __typename}fragment RememberControllerFragment on Adventure { id memory authorsNote __typename}fragment ShareControllerFragment on Adventure { id userId thirdPerson playPublicId characters { id userId name __typename } __typename}fragment AudioAdventureControllerFragment on Adventure { id music lastAction { id text __typename } __typename}fragment ReviewAdventureControllerFragment on Adventure { id actionCount __typename}","auth":{"token":"hello"}}}'
        )


        # send message
        await ws.send(
            '{"id":"2","type":"start","payload":{"variables":{"input":{"publicId":"'
            + str(adventure_id)
            + '","type":"'
            + command
            + '","text":'
            + json.dumps(text)
            + ',"choicesMode":false}},"extensions":{},"query":"mutation ($input: ActionInput) { addAction(input: $input) { time message __typename }}","auth":{"token":"hello"}}}'
        )

        # listen until a response is returned
        while True:
            resp = await ws.recv()
            print("Message received during next():")
            print(resp)
            json_payload = json.loads(resp)

            if json_payload["type"] == "data" and json_payload["id"] == "2":
                error_message = Turry.get_deeply_nested(
                    json_payload, ["payload", "data", "addAction", "message"]
                )
                if error_message is not None:
                    print(
                        "Got a message back after sending an action... assuming it's an error..."
                    )
                    print(error_message)
                    await ws.close()
                    return error_message, last_seen_id

            if json_payload["type"] == "data" and json_payload["id"] == "1":
                action_response = Turry.get_deeply_nested(
                    json_payload, ["payload", "data", "adventureUpdated", "lastAction"]
                )
                if (
                    action_response is not None
                    and "text" in action_response
                    and "id" in action_response
                    and action_response["id"] != last_seen_id
                ):
                    await ws.close()
                    return action_response["text"], action_response["id"]

    async def process_game_command(self, adventure_id, command):
        ws = self.ws

        await ws.send(
            '{"id":"1","type":"start","payload":{"variables":{"input":{"publicId":"'
            + str(adventure_id)
            + '","type":"' + command + '","choicesMode":false}},"extensions":{},"query":"mutation ($input: ActionInput) { addAction(input: $input) { time message __typename }}","auth":{"token":"hello"}}}'
        )

        while True:
            resp = await ws.recv()
            print(resp)
            json_payload = json.loads(resp)

            if json_payload["type"] == "data" and json_payload["id"] == "1":
                action_response = Turry.get_deeply_nested(
                    json_payload, ["payload", "data", "adventureUpdated", "lastAction"]
                )
                if (
                    action_response is not None
                    and "text" in action_response
                    and "id" in action_response
                ):
                    await ws.close()
                    return action_response["text"], action_response["id"]
            if json_payload["type"] == "complete":
                await ws.close()
                return True

    def exit_handler(self):
        if self.ws:
            self.ws.close()

    @staticmethod
    def get_deeply_nested(body, keys):
        current_value = body
        for key in keys:
            if current_value is None:
                return None
            if key not in current_value:
                return None
            current_value = current_value[key]
        return current_value

    def get_message_type(self, message):

        content, command, text = message.clean_content, None, None

        if content.startswith(">"):
            command = "say"
            text = self.extract_quote(content)
        if re.match(self.re_story, content):
            command = "story"
            text = re.match(self.re_story, content).group(1)
        if re.match(self.re_do, content):
            command = "do"
            text = re.match(self.re_do, content).group(2).lower()
        if self.is_at_me(message):
            content = self.is_at_me(message)
            if content.lower().startswith("retcon that to:"):
                command = "alter"
                text = self.extract_quote(text)
            if content.lower() == "i guess that did happen":
                command = "redo"
            if content.lower() == "that isn't what happened":
                command = "retry"
            if content.lower() == "what happened next?":
                command = "continue"

        return command, text

    @staticmethod
    def extract_quote(text):
        """Pull the quote text out of the message"""
        lines = text.split("\n")
        message = ""
        for line in lines:
            # pull out the quote syntax "> " and a user if there is one
            match = re.match(r"([^#]+#\d\d\d\d )?> (.*)", line)
            if match:
                message += match.group(2) + " "

        return message
