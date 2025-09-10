import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.settings_manager import settings_manager
import json
import os

class LanguageConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings_manager = settings_manager

    @app_commands.command(
        name="language",
        description="Set the server's language preference")
    @app_commands.guilds(discord.Object(id=int(os.getenv('GUILD_ID'))))
    @app_commands.describe(language="Choose a language: english, portuguese, spanish")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_language(self, interaction: discord.Interaction, language: str):
        """Slash command implementation"""
        valid_languages = ['english', 'portuguese', 'spanish']
        lang_lower = language.lower()
        
        if lang_lower not in valid_languages:
            await interaction.response.send_message("Invalid language. Available options: english, portuguese, spanish", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        self.settings_manager.update_guild_settings(guild_id, {"language": lang_lower})

        # Get success message from corresponding locale file
        lang_map = {'english': 'en', 'portuguese': 'pt', 'spanish': 'es'}
        with open(f'locales/{lang_map[lang_lower]}.json', 'r', encoding='utf-8') as f:
            locale = json.load(f)
        await interaction.response.send_message(locale['commands']['set_language']['success'], ephemeral=True)
        
async def setup(bot):
    guild_id = int(os.getenv('GUILD_ID'))
    cog = LanguageConfig(bot)
    await bot.add_cog(cog)
    
    # Move the command to the guild
    for command in cog.walk_app_commands():
        command.guild = discord.Object(id=guild_id)
    
    print(f"[DEBUG] LanguageConfig commands moved to guild {guild_id}")
