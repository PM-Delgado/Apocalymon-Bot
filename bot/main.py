import os
import logging
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()
TOKEN = os.getenv('DISCORD_BOT_TOKEN')

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('discord')

# Create bot instance
bot = commands.Bot(command_prefix='!')

# Load cogs
initial_cogs = ['bot.cogs.raid_alert']
for cog in initial_cogs:
    try:
        bot.load_extension(cog)
        logger.info(f'Loaded cog: {cog}')
    except Exception as e:
        logger.error(f'Failed to load cog {cog}: {e}')

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    logger.info('------')

if __name__ == '__main__':
    if TOKEN is None:
        logger.error('DISCORD_BOT_TOKEN not set in environment!')
    else:
        bot.run(TOKEN)
