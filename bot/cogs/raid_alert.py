import discord
from discord.ext import commands

class RaidAlert(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.guild_alert_config = {}

    @discord.app_commands.command(name="ping", description="Check if the bot is alive.")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong! 🏓", ephemeral=True)

    @discord.app_commands.command(name="setalertchannel", description="Set the channel for raid alerts.")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def setalertchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild_id = interaction.guild.id
        config = self.guild_alert_config.get(guild_id, {})
        if not config.get("enabled", False):
            await interaction.response.send_message("Raid alert feature is not enabled. Use /togglealert to enable it first.", ephemeral=True)
            return
        self.guild_alert_config.setdefault(guild_id, {})["channel_id"] = channel.id
        await interaction.response.send_message(f"Raid alert channel set to {channel.mention}", ephemeral=True)

    @discord.app_commands.command(name="setalertrole", description="Set the role to tag for raid alerts.")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def setalertrole(self, interaction: discord.Interaction, role: discord.Role):
        guild_id = interaction.guild.id
        config = self.guild_alert_config.get(guild_id, {})
        if not config.get("enabled", False):
            await interaction.response.send_message("Raid alert feature is not enabled. Use /togglealert to enable it first.", ephemeral=True)
            return
        self.guild_alert_config.setdefault(guild_id, {})["role_id"] = role.id
        await interaction.response.send_message(f"Raid alert role set to {role.mention}", ephemeral=True)

    @discord.app_commands.command(name="togglealert", description="Enable or disable the raid alert feature.")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def togglealert(self, interaction: discord.Interaction, enabled: bool):
        guild_id = interaction.guild.id
        if guild_id not in self.guild_alert_config:
            self.guild_alert_config[guild_id] = {}
        self.guild_alert_config[guild_id]["enabled"] = enabled
        state = "enabled" if enabled else "disabled"
        await interaction.response.send_message(f"Raid alert feature has been {state}.", ephemeral=True)

async def setup(bot):
    await bot.add_cog(RaidAlert(bot))