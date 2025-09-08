import os
import discord
import logging
import asyncio
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID')) # DEVELOPMENT MODE

# Set up logging with timestamps
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s %(levelname)s:%(name)s: %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger('discord')

# Create bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Log every command usage (text and slash)
@bot.listen('on_command')
async def log_text_command(ctx):
    logger.info(f'Text command used: {ctx.command} by {ctx.author} in {ctx.guild}/{ctx.channel}')

@bot.listen('on_app_command_completion')
async def log_slash_command(interaction, command):
    logger.info(f'Slash command used: /{command.name} by {interaction.user} in {interaction.guild}/{interaction.channel}')

@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    logger.info('------')

@bot.command()
@commands.is_owner()
async def reload(ctx):
    """Reload all cogs (owner only)."""
    cogs = ['bot.cogs.raid_alert']
    for ext in cogs:
        try:
            await bot.reload_extension(ext)
            logger.info(f'Reloaded {ext}')
        except Exception as e:
            logger.error(f'Failed to reload {ext}: {e}')

@bot.command()
@commands.is_owner()
async def sync(ctx):
    """Manually sync all slash commands to the test guild (owner only)."""
    try:
        guild = discord.Object(id=GUILD_ID)
        synced = await bot.tree.sync(guild=guild)
        logger.info(f'Synced {len(synced)} commands to guild {GUILD_ID}.')
    except Exception as e:
        logger.error(f'Failed to sync commands: {e}')

async def load_cogs():
    for filename in os.listdir("./bot/cogs"):
        if filename.endswith(".py"):
            ext = f"bot.cogs.{filename[:-3]}"
            try:
                await bot.load_extension(ext)
                logger.info(f"✅ Loaded extension {ext}")
            except Exception as e:
                logger.error(f"❌ Failed to load extension {ext}: {e}")


async def main():
    if TOKEN is None:
        logger.error('DISCORD_BOT_TOKEN not set in environment!')
        return
    
    await load_cogs()
    await bot.start(TOKEN)

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info(f'Bot stopped by user.')