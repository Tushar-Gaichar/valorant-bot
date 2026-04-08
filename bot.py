import asyncio
import os

import discord
from discord.ext import commands
from dotenv import load_dotenv

from database import Database
from keep_alive import start_web_server

load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix="!", intents=intents)
bot.db = Database()


@bot.event
async def on_ready():
    print(f"✅ Logged in as {bot.user} ({bot.user.id})")
    try:
        synced = await bot.tree.sync()
        print(f"📡 Synced {len(synced)} slash command(s)")
    except Exception as e:
        print(f"❌ Failed to sync commands: {e}")


async def load_cogs():
    for cog in ["cogs.stats", "cogs.admin"]:
        await bot.load_extension(cog)
        print(f"🔧 Loaded {cog}")


async def main():
    # Web server starts immediately in background — Render sees PORT bound right away
    asyncio.create_task(start_web_server(bot))
    
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)

asyncio.run(main())
