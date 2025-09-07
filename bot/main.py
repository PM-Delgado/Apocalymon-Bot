import os
import discord
import logging
import asyncio
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = os.getenv('GUILD_ID') # DEVELOPMENT MODE

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

# Create bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='/', intents=intents)

# Sync slash commands on startup (global)
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    logger.info('------')
    try:
        # DEVELOPMENT MODE
        #synced = await bot.tree.sync()
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        logger.info(f'Synced {len(synced)} commands to guild {GUILD_ID}.')
        #logger.info(f'Synced {len(synced)} global slash commands.')
    except Exception as e:
        logger.error(f'Failed to sync slash commands: {e}')

async def main():
    initial_cogs = ['bot.cogs.raid_alert']
    for cog in initial_cogs:
        try:
            await bot.load_extension(cog)
            logger.info(f'Loaded cog: {cog}')
        except Exception as e:
            logger.error(f'Failed to load cog {cog}: {e}')
    if TOKEN is None:
        logger.error('DISCORD_BOT_TOKEN not set in environment!')
    else:
        await bot.start(TOKEN)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info(f'Bot stopped by user.')