import discord
from discord.ext import commands
from discord import app_commands
from bot.utils.settings_manager import settings_manager
import os

class LanguageConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings = settings_manager

    @app_commands.command(
        name="setlanguage",
        description="Set the server's language preference.")
    @app_commands.guilds(discord.Object(id=int(os.getenv('GUILD_ID'))))
    @app_commands.describe(language="Choose between supported languages: english, portuguese, spanish")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_language(self, interaction: discord.Interaction, language: str) -> None:
        await interaction.response.defer(ephemeral=True)

        valid_languages = {
            'english': 'en',
            'portuguese': 'pt',
            'spanish': 'es'
        }
        lang_lower = language.lower()
        guild_id = str(interaction.guild.id)
        
        if lang_lower not in valid_languages:
            invalid_msg = self.settings.get_localization(guild_id).get('commands', {}).get('set_language.invalid_language')
            await interaction.followup.send(invalid_msg, ephemeral=True)
            return

        lang_code = valid_languages[lang_lower]

        self.settings.update_guild_settings(guild_id, {'language': lang_code})
        response = self.settings.get_localization(guild_id).get('commands', {}).get('set_language.success')
        
        success_msg = response or f"Language has been set to {language.capitalize()}"

        await interaction.followup.send(success_msg, ephemeral=True)

        
async def setup(bot: commands.Bot) -> None:
    cog = LanguageConfig(bot)
    await bot.add_cog(cog)
