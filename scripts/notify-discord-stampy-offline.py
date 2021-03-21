import discord
import asyncio

from config import ENVIRONMENT_TYPE, bot_dev_channels, discord_token

from discord.ext.commands import Bot

bot = Bot(command_prefix="!")

import discord
import asyncio

client = discord.Client()


@client.event
async def on_ready():
    print("Logged in as")
    print(client.user.name)
    print(client.user.id)
    await client.get_channel(bot_dev_channels[ENVIRONMENT_TYPE]).send("A new stampy is dead")
    print("------")
    exit()


client.run(discord_token)

#
# @bot.command()
# async def send(message):
#     await bot.get_channel(803448149946662923).send(message)
#     # await bot.get_channel(bot_dev_channels[ENVIRONMENT_TYPE]).send(message)
#
#
# async def main():
#     await send("random message")
#
#
# asyncio.run(main())
