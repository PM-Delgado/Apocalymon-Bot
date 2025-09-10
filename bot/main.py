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
bot = commands.Bot(command_prefix='/', intents=intents)

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
    logger.info(f'Loaded cogs: {list(bot.cogs.keys())}')
    
    # Debug: Check loaded commands
    logger.info("=== COMMAND DEBUG INFO ===")
    logger.info(f"Total tree commands: {len(list(bot.tree.walk_commands()))}")
    
    for command in bot.tree.walk_commands():
        # Check if it's a guild-specific command
        guild_info = "Global" if not hasattr(command, 'guild') or command.guild is None else f"Guild: {command.guild.id}"
        logger.info(f"Command: {command.name} | {guild_info}")
    
    logger.info("========================")
    logger.info('------')

@bot.command()
@commands.is_owner()
async def reload(ctx):
    """Reload all cogs (owner only)."""
    cogs = ['bot.cogs.raid_alert', 'bot.cogs.language_config']
    for ext in cogs:
        try:
            await bot.reload_extension(ext)
            logger.info(f'Reloaded {ext}')
        except Exception as e:
            logger.error(f'Failed to reload {ext}: {e}')

@bot.command()
@commands.is_owner()
async def sync(ctx):
    """Manually sync commands to test guild (owner only)."""
    try:
        guild = discord.Object(id=GUILD_ID)
        
        # Debug info before sync
        commands_to_sync = [cmd for cmd in bot.tree.walk_commands() if GUILD_ID in (cmd.guild_ids or [])]
        logger.info(f"Commands that should sync to guild {GUILD_ID}: {[cmd.name for cmd in commands_to_sync]}")
        
        synced = await bot.tree.sync(guild=guild)
        logger.info(f'Synced {len(synced)} commands to test guild {GUILD_ID}')
        logger.info(f'Synced commands: {[cmd.name for cmd in synced]}')
        
        await ctx.send(f'✅ Synced {len(synced)} commands: {", ".join([cmd.name for cmd in synced])}')
        
    except Exception as e:
        logger.error(f'Failed to sync commands: {e}')
        await ctx.send(f'❌ Failed to sync: {e}')

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
