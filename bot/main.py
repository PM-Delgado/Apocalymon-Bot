import os
import logging
import asyncio
from datetime import datetime
from typing import List
import discord
from discord.ext import commands
from dotenv import load_dotenv
from supabase import create_client, Client

# Initialize environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
GUILD_ID = int(os.getenv('GUILD_ID'))
SUPABASE_URL = os.getenv('SUPABASE_URL')
SUPABASE_KEY = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Configure centralized logging
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(name)s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
    ]
)
logger = logging.getLogger('discord')

# Bot instance
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='/', intents=intents)

@bot.listen('on_app_command_completion')
async def log_slash_command(
    interaction: discord.Interaction, 
    command: discord.app_commands.Command
) -> None:
    logger.info(
        f'Slash command "/{command.name}" used by {interaction.user} '
        f'in {interaction.guild.name}/{interaction.channel.name}'
    )

@bot.command()
@commands.is_owner()
async def reload(ctx):
    cogs = ['bot.cogs.raid_alert', 'bot.cogs.language_config']
    for ext in cogs:
        try:
            await bot.reload_extension(ext)
            logger.info(f'✅ Reloaded [{ext}]')
        except Exception as e:
            logger.error(f'❌ Failed to reload [{ext}]: {e}')

@bot.command()
@commands.is_owner()
async def sync(ctx):
    try:
        synced = await bot.tree.sync(guild=discord.Object(id=GUILD_ID))
        logger.info(f'✅ Synced {len(synced)} commands to Guild {GUILD_ID}')
        logger.info(f'📋 Synced commands: {[cmd.name for cmd in synced]}')
        
    except Exception as e:
        logger.error(f'❌ Failed to sync commands: {e}')

async def load_cogs() -> None:
    cogs_to_load: List[str] = [
        "bot.cogs.language_config",
        "bot.cogs.raid_alert"
    ]
    
    logger.info("Starting cog loading process...")
    
    for cog_path in cogs_to_load:
        try:
            await bot.load_extension(cog_path)
            logger.info(f"✅ Successfully loaded cog [{cog_path}]")
        except Exception as error:
            logger.error(
                f"❌ Failed to load cog [{cog_path}] - {type(error).__name__}: {error}",
                exc_info=True
            )

@bot.event
async def on_guild_join(guild: discord.Guild):
    try:
        supabase.table("guilds").upsert({
            "guild_id": guild.id,
            "name": guild.name
        }).execute()

        supabase.table("guild_settings").upsert({
            "guild_id": guild.id,
            "prefix": "/",
            "language": "english",
            "timezone": "london"
        }).execute()

        logger.info(f"✅ New guild added: {guild.name} ({guild.id}) with default settings")
    except Exception as e:
        logger.error(f"❌ Failed to add new guild {guild.name} ({guild.id}): {e}")



@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user} (ID: {bot.user.id})')
    logger.info(f'Loaded cogs: {list(bot.cogs.keys())}')

    # Backfill Supabase with current guilds
    for guild in bot.guilds:
        try:
            supabase.table("guilds").upsert({
                "guild_id": guild.id,
                "name": guild.name
            }).execute()

            supabase.table("guild_settings").upsert({
                "guild_id": guild.id,
                "prefix": "/",
                "language": "english",
                "timezone": "london"
            }).execute()

            logger.info(f"✅ Synced guild {guild.name} ({guild.id}) to Supabase")
        except Exception as e:
            logger.error(f"❌ Failed syncing guild {guild.name}: {e}")
    
    for command in bot.tree.walk_commands():
        # Check if it's a guild-specific command
        guild_info = "Global" if not hasattr(command, 'guild') or command.guild is None else f"Guild: {command.guild.id}"
        logger.info(f"Command: {command.name} | {guild_info}")
    
    logger.info("========================")

async def main() -> None:
    if not TOKEN:
        logger.critical("DISCORD_BOT_TOKEN environment variable not set!")
        raise ValueError("Missing required DISCORD_BOT_TOKEN environment variable")
    
    start_time = datetime.now()
    
    try:
        logger.info("Starting bot initialization...")
        await load_cogs()
        logger.info(f"Bot initialized in {(datetime.now() - start_time).total_seconds():.2f}s")
        await bot.start(TOKEN)
    except Exception as error:
        logger.critical(
            f"Fatal error during bot operation: {type(error).__name__} - {error}",
            exc_info=True
        )
        raise

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info(f'Bot stopped by user.')
