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
        self.adventure_id = "4c35b5ca-ee26-4894-87ad-1600f4ae8aae"
        self.last_seen_id = None
        atexit.register(self.exit_handler)
        return

    def can_process_message(self, message, client=None):
        if hasattr(message.channel, "name") and message.channel.name == "seed":
            return 7, ""
        return 0, ""

    async def process_message(self, message, client=None):
        self.ws = await self.get_initialized_websocket()
        if hasattr(message.channel, "name") and message.channel.name == "seed":
            text = message.clean_content
            match = re.search("^(![^\s]*)(\n|\s|\r|$)", text)
            command = match.group(1)
            prompt = text.replace(command + ' ', '')


            #if command == "!new":
            #    self.adventure_id = await self.process_game_restart()
            #    if self.adventure_id:
            #        response = "New game started: " + self.adventure_id
            if self.adventure_id:
                if command == "!do":
                    message = await self.process_game_next("do", prompt, self.adventure_id, self.last_seen_id)
                    if message:
                        response = message[0]
                        self.last_seen_id = message[1]
                elif command == "!say":
                    message = await self.process_game_next("say", prompt, self.adventure_id, self.last_seen_id)
                    if message:
                        response = message[0]
                        self.last_seen_id = message[1]
                elif command == "!story":
                    message = await self.process_game_next("story", prompt, self.adventure_id, self.last_seen_id)
                    if message:
                        response = message[0]
                        self.last_seen_id = message[1]
                elif command == "!start":
                    message = await self.process_game_next("start", '', self.adventure_id, self.last_seen_id)
                    response = message[0]
                    self.last_seen_id = message[1]

                if response:
                    return 7, response
        """Handle the message, return a string which is your response.
        This is an async function so it can interact with the Discord API if it needs to"""
        return 0, ""

    async def process_reaction_event(
        self, reaction, user, event_type="REACTION_ADD", client=None
    ):
        """event_type can be 'REACTION_ADD' or 'REACTION_REMOVE'
        Use this to allow modules to handle adding and removing reactions on messages"""
        return 0, ""

    async def process_raw_reaction_event(self, event, client=None):
        """event is a discord.RawReactionActionEvent object
        Use this to allow modules to handle adding and removing reactions on messages"""
        return 0, ""

    def __str__(self):
        return "Turry Module"

    async def get_initialized_websocket(self):
        ws = await websockets.connect(self.ws_url, subprotocols=['graphql-ws'])
        await ws.send('{"type":"connection_init","payload":{"token":"' + self.token + '"}}')
        while True:
            resp = await ws.recv()
            print('Turry Module: Message received during websocket initialization to AI Dungeon:')
            print(resp)
            if json.loads(resp)["type"] == "connection_ack":
                break
        return ws

    async def process_game_restart(self):
        ws = self.ws
        await ws.send('{"id":"1","type":"start","payload":{"variables":{"scenarioId":"1665210","prompt":null},"extensions":{},"operationName":null,"query":"mutation ($scenarioId: String, $prompt: String) {  addAdventure(scenarioId: $scenarioId, prompt: $prompt) {    id    publicId    title    description    musicTheme    tags    nsfw    published    createdAt    updatedAt    deletedAt    publicId    __typename  }}","auth":{"token":"hello"}}}')
        #await ws.send('{"id":"1","type":"start","payload":{"variables":{},"extensions":{},"query":"subscription {\n  userUpdated {\n    id\n    hasPremium\n    scales\n    __typename\n  }\n}\n","auth":{"token":"hello"}}}')
        while True:
            resp = await ws.recv()
            print('Message received during restart():')
            print(resp)
            json_payload = json.loads(resp)

            if json_payload["type"] == "data" and json_payload["id"] == "1":
                await ws.close()
                adventure_id_new = json_payload["payload"]["data"]["addAdventure"]["publicId"]
                print(adventure_id_new)
                return adventure_id_new

    async def process_game_next(self, command, text, adventure_id, last_seen_id):
        ws = self.ws
        print("adventure id:")
        print(adventure_id)

        # subscribe to current adventure
        await ws.send('{"id":"1","type":"start","payload":{"variables":{"publicId":"' + str(adventure_id) + '"},"extensions":{},"query":"subscription ($publicId: String) { adventureUpdated(publicId: $publicId) { ...AdventurePlayFragment __typename }}fragment AdventurePlayFragment on Adventure { id playPublicId publicId thirdPerson actionCount lastAction { ...ActionFragment __typename } ...AdventureControllerFragment ...AudioAdventureControllerFragment ...ReviewAdventureControllerFragment __typename}fragment ActionFragment on Action { id text adventureId undoneAt deletedAt __typename}fragment AdventureControllerFragment on Adventure { id actionLoading error gameState events thirdPerson userId characters { id userId name __typename } ...ActionAdventureControllerFragment ...AlterControllerFragment ...QuestControllerFragment ...RememberControllerFragment ...ShareControllerFragment __typename}fragment ActionAdventureControllerFragment on Adventure { id publicId actionCount choices error mode thirdPerson userId worldId characters { id userId name __typename } ...DeathControllerFragment __typename}fragment DeathControllerFragment on Adventure { id publicId mode died __typename}fragment AlterControllerFragment on Adventure { id publicId mode __typename}fragment QuestControllerFragment on Adventure { id publicId lastAction { id text __typename } quests { id text completed active actionGainedId actionCompletedId __typename } __typename}fragment RememberControllerFragment on Adventure { id memory authorsNote __typename}fragment ShareControllerFragment on Adventure { id userId thirdPerson playPublicId characters { id userId name __typename } __typename}fragment AudioAdventureControllerFragment on Adventure { id music lastAction { id text __typename } __typename}fragment ReviewAdventureControllerFragment on Adventure { id actionCount __typename}","auth":{"token":"hello"}}}')

        # send message
        await ws.send('{"id":"2","type":"start","payload":{"variables":{"input":{"publicId":"' + str(adventure_id) + '","type":"' + command + '","text":' + json.dumps(text) + ',"choicesMode":false}},"extensions":{},"query":"mutation ($input: ActionInput) { addAction(input: $input) { time message __typename }}","auth":{"token":"hello"}}}')

        # listen until a response is returned
        while True:
            resp = await ws.recv()
            print('Message received during next():')
            print(resp)
            json_payload = json.loads(resp)

            if json_payload["type"] == "data" and json_payload["id"] == "2":
                error_message = Turry.get_deeply_nested(json_payload, ["payload", "data", "addAction", "message"])
                if error_message is not None:
                    print("Got a message back after sending an action... assuming it's an error...")
                    print(error_message)
                    await ws.close()
                    return error_message, last_seen_id

            if json_payload["type"] == "data" and json_payload["id"] == "1":
                action_response = Turry.get_deeply_nested(json_payload, ["payload", "data", "adventureUpdated", "lastAction"])
                if (action_response is not None and "text" in action_response and "id" in action_response and
                        action_response["id"] != last_seen_id):
                    await ws.close()
                    return action_response["text"], action_response["id"]

    async def process_game_revert(self, adventure_id):
        ws = await self.get_initialized_websocket()
        print("adventure id:" + adventure_id)

        # subscribe to current adventure
        await ws.send('{"id":"1","type":"start","payload":{"variables":{"input":{"publicId":"' + str(adventure_id) + '","type":"undo","choicesMode":false}},"extensions":{},"query":"mutation ($input: ActionInput) { addAction(input: $input) { time message __typename }}","auth":{"token":"hello"}}}')

        while True:
            resp = await ws.recv()
            print('Message received during revert():')
            print(resp)
            json_payload = json.loads(resp)

            if json_payload["type"] == "complete":
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



