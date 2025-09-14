import discord
import logging
from discord.ext import commands
from discord import app_commands
from bot.main import supabase
import os

class LanguageConfig(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @app_commands.command(
        name="setlanguage",
        description="Set the server's language preference.")
    @app_commands.guilds(discord.Object(id=int(os.getenv('GUILD_ID'))))
    @app_commands.describe(language="Choose between supported languages: english, portuguese, spanish")
    @app_commands.checks.has_permissions(administrator=True)
    async def set_language(self, interaction: discord.Interaction, language: str) -> None:
        valid_languages = {
            'english': 'en',
            'portuguese': 'pt',
            'spanish': 'es'
        }
        lang_lower = language.lower()
        
        if lang_lower not in valid_languages:
            await interaction.response.send_message("Invalid language. Available options: english, portuguese, spanish", ephemeral=True)
            return

        guild_id = str(interaction.guild.id)
        lang_code = valid_languages[lang_lower]
        
        # Update guild settings directly via Supabase
        supabase.table('guild_settings').upsert({
            'guild_id': guild_id,
            'language': lang_lower
        }).execute()

        response = supabase.table('locales').select("*") \
            .filter("language", "eq", lang_code) \
            .filter("namespace", "eq", "commands") \
            .filter("key", "eq", "set_language.success") \
            .execute()

        if response.data:
            success_msg = response.data[0]['value']
        else:
            # Fallback if translation missing
            success_msg = f"Language has been set to {language.capitalize()}"

        await interaction.response.send_message(success_msg, ephemeral=True)

        
async def setup(bot: commands.Bot) -> None:
    cog = LanguageConfig(bot)
    await bot.add_cog(cog)
