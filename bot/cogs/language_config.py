import discord
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
        await interaction.response.defer(ephemeral=True)

        valid_languages = {
            'english': 'en',
            'portuguese': 'pt',
            'spanish': 'es'
        }
        lang_lower = language.lower()
        guild_id = str(interaction.guild.id)
        
        if lang_lower not in valid_languages:
            prev_language = supabase.table('guild_settings').select('language') \
                .filter('guild_id', 'eq', guild_id) \
                .execute()
            
            prev_lang_code = prev_language.data[0]['language'] if prev_language.data else 'en'
            response = supabase.table('locales').select("value") \
                .filter("language", "eq", prev_lang_code) \
                .filter("namespace", "eq", "commands") \
                .filter("key", "eq", "set_language.invalid_language") \
                .execute()
            
            invalid_language = response.data[0]['value']
            await interaction.followup.send(invalid_language, ephemeral=True)
            return

        lang_code = valid_languages[lang_lower]

        supabase.table('guild_settings').upsert({
            'guild_id': guild_id,
            'language': lang_code
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

        await interaction.followup.send(success_msg, ephemeral=True)

        
async def setup(bot: commands.Bot) -> None:
    cog = LanguageConfig(bot)
    await bot.add_cog(cog)
