import discord
import logging
from discord import app_commands
from discord.ext import commands, tasks
import yaml
from bot.utils.settings_manager import settings_manager
from datetime import datetime, timedelta
import pytz
import os
import json
import re

GUILD_ID = int(os.getenv('GUILD_ID'))

class RaidAlert(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.settings_manager = settings_manager
        self.guild_alert_config = self.settings_manager.settings
        self.sent_messages = {}
        self.completed_raids = set()
        # Timezones
        self.timezones = {
            "korea": pytz.timezone("Asia/Seoul"),
            "brasilia": pytz.timezone("America/Sao_Paulo"),
            "london": pytz.timezone("Europe/London"),
            "new_york": pytz.timezone("America/New_York"),
            "los_angeles": pytz.timezone("America/Los_Angeles")
        }
        self.default_tz = self.timezones["korea"]
        self.lisbon = self.timezones["london"] # Logs timezone
        # Raid cleanup
        self.last_cleanup_time = None
        self.COMPLETED_RAIDS_CLEANUP_INTERVAL = 7 * 24 * 60 * 60
        # Raids loaded from config
        self.raids = self._load_raid_schedule()
        # List of (guild_id, raid_dict) for test/dummy alerts
        self.test_raids = []
        # Start background loop
        self._raid_alert_loop.start()

    def cog_unload(self):
        self._raid_alert_loop.cancel()

    ###########################################################
    # Utilities
    ###########################################################

    def _log(self, level: str, msg: str) -> None:
        logger = logging.getLogger('discord')
        log_method = getattr(logger, level.lower(), logger.info)
        log_method(msg)

    def _load_raid_schedule(self, config_path="raid_schedule.yaml"):
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "raid_schedule.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config["raids"]

    def _get_current_kst(self):
        return datetime.now(self.default_tz)

    def _clean_boss_name(self, raw_name: str) -> str:
        return re.sub(r'^\W+\s+', '', raw_name).strip()

    def _get_raid_config(self, raid_name: str) -> dict:
        clean_name = self._clean_boss_name(raid_name)
        return next((r for r in self.raids if self._clean_boss_name(r["name"]) == clean_name), {})

    def _get_image_url(self, raid_name: str) -> str:
        raid_config = self._get_raid_config(raid_name)
        if image_file := raid_config.get("image"):
            return f"{os.getenv('DSR_RAID_ALERT_ICONS')}/{image_file}?v={int(datetime.now().timestamp())}"
        raise ValueError(f"❌ Missing image config for {raid_name}")

    def _get_map_url(self, raid_name: str) -> str: 
        raid_config = self._get_raid_config(raid_name)
        if map_file := raid_config.get("map_image"):
            return f"{os.getenv('DSR_RAID_ALERT_MAPS')}/{map_file}?v={int(datetime.now().timestamp())}"
        raise ValueError(f"❌ Missing map image config for {raid_name}")

    def _get_remaining_minutes(self, seconds_total: int) -> int:
        # Round up if more than 30 seconds
        if seconds_total <= 0:
            return 0
        minutes = seconds_total // 60
        seconds = seconds_total % 60
        if seconds > 50:
            minutes += 1
        return minutes

    ###########################################################
    # Status and Color Helpers
    ###########################################################

    def _compute_status(self, time_diff):
        # Determine raid status based on time difference (seconds)
        minutes_until = self._get_remaining_minutes(int(time_diff))
        if time_diff < -300:
            return "finished"
        elif minutes_until > 5:
            return "upcoming"
        elif 1 <= minutes_until <= 5:
            return "starting"
        elif minutes_until == 0 or (time_diff < 0 and time_diff >= -300):
            return "ongoing"

    def _get_raid_status(self, time_diff):
        # Return (status, color) tuple
        status = self._compute_status(time_diff)
        color = {
            "upcoming": 0xFF0000,
            "starting": 0xFFFF00,
            "ongoing": 0x00FF00,
            "finished": 0x808080,
        }[status]
        return status, color

    ###########################################################
    # Embed and Content Helpers
    ###########################################################

    def _create_embed_content(self, raid, time_until_raid_seconds):
        # Build Discord embed for raid alert
        guild_id = raid.get('guild_id')
        locale = self._get_guild_locale(guild_id)
        tz = self._get_guild_timezone(guild_id)
        display_time = raid["next_time"].astimezone(tz)
        minutes_until = self._get_remaining_minutes(int(time_until_raid_seconds))
        clean_name = self._clean_boss_name(raid['name'])
        status, color = self._get_raid_status(time_until_raid_seconds)
        
        # Get localized strings from guild's locale
        raid_alerts = locale.get('raid_alerts', {})
        self._log("DEBUG", f"✅✅✅ Localized texts for {guild_id} - {list(raid_alerts.keys())}")
        
        if status in ("upcoming", "starting"):
            desc_status = f"⏳ " + raid_alerts['starts_in'].format(minutes=minutes_until)
        elif status == "ongoing":
            minutes_ongoing = max(0, int((-time_until_raid_seconds) // 60))
            desc_status = "⚔️ **" + raid_alerts['started_ago'].format(minutes=minutes_ongoing) + "**"
        else:
            desc_status = raid_alerts['finished']
            
        total_offset = display_time.utcoffset().total_seconds()
        offset_hours = int(total_offset // 3600)
        offset_minutes = int((total_offset % 3600) // 60)
        tz_offset = f"GMT{'+' if offset_hours >=0 else '-'}{abs(offset_hours)}"
        if offset_minutes != 0:
            tz_offset += f":{abs(offset_minutes):02d}"
        time_str = f"{display_time.strftime('%H:%M')} ({tz_offset})"
        embed = discord.Embed(
            title=clean_name,
            color=color
        )

        # Build embed fields
        embed.add_field(name="", value=raid_alerts['location'].format(location=raid['map']), inline=False)
        embed.add_field(name="", value=raid_alerts['time'].format(time=time_str), inline=False)
        embed.add_field(name="", value=desc_status, inline=False)
        embed.set_thumbnail(url=self._get_image_url(clean_name))
        embed.set_footer(text=raid_alerts.get('footer'))
        map_image_url = self._get_map_url(clean_name)
        if map_image_url:
            embed.set_image(url=map_image_url)
        return embed, status

    def _create_message_content(self, raid, time_until_raid_seconds, role_mention, status):
        # Build message content for raid alert
        guild_id = raid.get('guild_id')
        locale = self._get_guild_locale(guild_id)
        raid_alerts = locale.get('raid_alerts', {})
        minutes_until = self._get_remaining_minutes(int(time_until_raid_seconds))
        
        if status == "ongoing":
            minutes_ongoing = max(0, int((-time_until_raid_seconds) // 60))
            ongoing_str = raid_alerts['started_ago'].format(minutes=minutes_ongoing)
        if status in ("upcoming", "starting"):
            base_str = raid_alerts['starts_in'].format(minutes=minutes_until)
            content = f"||{role_mention}||\n**{raid['name'].upper()}** | {base_str}!"
        elif status == "ongoing":
            content = f"||{role_mention}||\n**{raid['name'].upper()}** | {ongoing_str}!"
        else:
            finished_str = raid_alerts['finished']
            content = f"||{role_mention}||\n**{raid['name'].upper()}** | {finished_str}!"
        return content

    ###########################################################
    # Raid Time Calculations
    ###########################################################

    def _get_next_daily_time(self, time_str):
        now = self._get_current_kst()
        raid_time = datetime.strptime(time_str, "%H:%M").time()
        raid_dt = self.default_tz.localize(datetime.combine(now.date(), raid_time))
        if raid_dt <= now:
            raid_dt += timedelta(days=1)
        return raid_dt

    def _get_next_biweekly_time(self, time_str, base_date_str):
        now = self._get_current_kst()
        base_date = self.default_tz.localize(datetime.strptime(base_date_str, "%Y-%m-%d"))
        raid_time = datetime.strptime(time_str, "%H:%M").time()
        diff_days = (now.date() - base_date.date()).days
        cycles = diff_days // 14
        next_date = base_date + timedelta(days=cycles * 14)
        raid_dt = self.default_tz.localize(datetime.combine(next_date.date(), raid_time))
        if raid_dt <= now:
            raid_dt += timedelta(days=14)
        return raid_dt

    def _get_next_rotation_time(self, base_time_str, base_date_str):
        now = self._get_current_kst()
        base_date = self.default_tz.localize(datetime.strptime(base_date_str, "%Y-%m-%d"))
        base_hour, base_minute = map(int, base_time_str.split(":"))
        now_midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)
        base_midnight = base_date.replace(hour=0, minute=0, second=0, microsecond=0)
        diff_days = (now_midnight - base_midnight).days
        raid_time = base_date + timedelta(days=diff_days)
        raid_time = raid_time.replace(hour=base_hour, minute=base_minute)
        raid_time += timedelta(minutes=diff_days * 25)
        if raid_time <= now:
            diff_days += 1
            raid_time = base_date + timedelta(days=diff_days)
            raid_time = raid_time.replace(hour=base_hour, minute=base_minute)
            raid_time += timedelta(minutes=diff_days * 25)
        return raid_time

    ###########################################################
    # Raid List (real + test/dummy)
    ###########################################################

    def _get_upcoming_raids(self):
        # Build list of all upcoming raids (real + test)
        raids = []
        for cfg in self.raids:
            name = cfg["name"]
            map_name = cfg["map"]
            freq = cfg.get("frequency", "daily")
            times = cfg.get("times", [])
            base_date = cfg.get("base_date")
            if freq == "rotation":
                base_time = times[0]
                next_time_dt = self._get_next_rotation_time(base_time, base_date)
                raids.append({
                    "name": name,
                    "map": map_name,
                    "next_time": next_time_dt,
                    "scheduled_time": base_time,
                    "image": self._get_image_url(self._clean_boss_name(name)),
                })
                continue
            for t in times:
                if freq == "biweekly":
                    next_time_dt = self._get_next_biweekly_time(t, base_date)
                else:
                    next_time_dt = self._get_next_daily_time(t)
                raids.append({
                    "name": name,
                    "map": map_name,
                    "next_time": next_time_dt,
                    "scheduled_time": t,
                    "image": self._get_image_url(self._clean_boss_name(name)),
                })
        # Add test/dummy raids (from /testalert) to the list
        for guild_id, test_raid in getattr(self, 'test_raids', []):
            raids.append(test_raid)
        raids.sort(key=lambda r: r["next_time"])
        return raids

    ###########################################################
    # Send or Update Raid Alert Message
    ###########################################################

    async def _send_or_update_raid_alert(self, guild_id, raid):
        config = self.guild_alert_config.get(str(guild_id))
        raid_config = config.get('raid_alerts') if config else None
        if not config or not raid_config.get("enabled"):
            self._log("DEBUG", f"❌ Guild {guild_id} not enabled or config missing.")
            return
        channel_id = raid_config.get("channel_id")
        role_id = raid_config.get("role_id")
        if not channel_id or not role_id:
            self._log("DEBUG", f"❌ Guild {guild_id} missing channel or role config.")
            return
        channel = self.bot.get_channel(channel_id)
        if not channel:
            self._log("DEBUG", f"❌ Channel {channel_id} not found in guild {guild_id}.")
            return
        
        role_mention = f"<@&{role_id}>"
        time_until_raid_seconds = (raid["next_time"] - self._get_current_kst()).total_seconds()
        embed, status = self._create_embed_content(raid, time_until_raid_seconds)
        content = self._create_message_content(raid, time_until_raid_seconds, role_mention, status)

        # For real raids (no guild_id), use global key. For tests, include guild_id
        if 'guild_id' in raid:  # Test raid
            key = (raid['guild_id'], raid["name"], raid["scheduled_time"])
        else:  # Real raid
            key = (raid["name"], raid["scheduled_time"])

        self._log("DEBUG", f"send_or_update_raid_alert: key={key}, status={status}, time_until={time_until_raid_seconds}")
        # If already sent, update only if status or color changed
        if key in self.sent_messages:
            try:
                msg_id = self.sent_messages[key]['message_id']
                self._log("DEBUG", f"🔄 Attempting to update message {msg_id} in channel {channel_id}")
                msg = await channel.fetch_message(msg_id)
                prev_embed = self.sent_messages[key]['embed']
                # Only update the last field and color if changed
                prev_status_field = prev_embed.fields[-1].value if prev_embed.fields else None
                new_status_field = embed.fields[-1].value if embed.fields else None
                prev_color = prev_embed.color.value if prev_embed.color else None
                new_color = embed.color.value if embed.color else None
                
                if prev_status_field != new_status_field or prev_color != new_color or msg.content != content:
                    # Update only the last field and color
                    prev_embed.set_field_at(len(prev_embed.fields)-1, name="", value=new_status_field, inline=False)
                    prev_embed.color = embed.color
                    await msg.edit(content=content, embed=prev_embed, allowed_mentions=discord.AllowedMentions(roles=True))
                    self.sent_messages[key]['embed'] = prev_embed  # Store the modified embed
                    self.sent_messages[key]['last_update'] = self._get_current_kst()
                    self._log("DEBUG", f"🆕 Updated message {msg_id} for {key}")
                else:
                    self._log("DEBUG", f"🔴 No change for message {msg_id} for {key}, skipping edit.")
            except Exception as e:
                self._log("DEBUG", f"❌ Failed to update message {msg_id} for {key}: {e}")
                
        else:
            sent = await channel.send(content=content, embed=embed, allowed_mentions=discord.AllowedMentions(roles=True))
            self.sent_messages[key] = {
                'message_id': sent.id,
                'channel_id': channel_id,
                'embed': embed,
                'raid': raid,
                'last_update': self._get_current_kst()
            }
            self._log("DEBUG", f"🆕 Sent new message {sent.id} for {key}")

    ###########################################################
    # Main Raid Alert Loop
    ###########################################################
    @tasks.loop(seconds=10)
    async def _raid_alert_loop(self):
        now_kst = self._get_current_kst()
        upcoming_raids = self._get_upcoming_raids()
        # Periodic cleanup of completed_raids (every 7 days)
        if self.last_cleanup_time is None or (now_kst - self.last_cleanup_time).total_seconds() > self.COMPLETED_RAIDS_CLEANUP_INTERVAL:
            cutoff = now_kst - timedelta(seconds=self.COMPLETED_RAIDS_CLEANUP_INTERVAL)
            before = len(self.completed_raids)
            completed_raids_copy = set(self.completed_raids)
            for key in completed_raids_copy:
                try:
                    raid_time = datetime.strptime(key[2], "%Y-%m-%d %H:%M:%S")
                    raid_time = self.default_tz.localize(raid_time)
                    if raid_time < cutoff:
                        self.completed_raids.remove(key)
                except Exception:
                    continue
            after = len(self.completed_raids)
            self._log("CLEANUP", f"Cleaned up completed_raids: {before} -> {after}")
            self.last_cleanup_time = now_kst

        # For each enabled guild, send/update alerts
        for guild_id, config in self.guild_alert_config.items():
            # Ensure we have a valid config structure
            raid_config = config.get('raid_alerts', {})
            if not raid_config.get('enabled', False):
                continue
            
            # Filter raids to only those for this guild (convert to string for type match)
            guild_raids = [r for r in upcoming_raids if r.get('guild_id') == str(guild_id)]
            for raid in guild_raids:
                time_diff = (raid["next_time"] - now_kst).total_seconds()
                # Match key format from send_or_update_raid_alert
                if 'guild_id' in raid:  # Test raid
                    key = (raid['guild_id'], raid["name"], raid["scheduled_time"])
                else:  # Real raid
                    key = (raid["name"], raid["scheduled_time"])
                # Update for all non-finished raids #TODO CHECK
                status = self._get_raid_status(time_diff)
                if status != "finished" and key not in self.completed_raids:
                    self._log("DEBUG", f"🛠️ Will send/update alert for {key}")
                    await self._send_or_update_raid_alert(guild_id, raid)
                
                # If finished, update message to finished state before removing
                if key in self.sent_messages and status == "finished":
                    self._log("INFO", f"🏁 Marking {key} as finished, updating message to finished state before removal")
                    # Force update to finished state
                    await self._send_or_update_raid_alert(guild_id, raid)
                    del self.sent_messages[key]
                    self.completed_raids.add(key)

    @_raid_alert_loop.before_loop
    async def before_raid_alert_loop(self):
        # Wait for bot to be ready before starting loop
        await self.bot.wait_until_ready()

    ###########################################################
    # Bot Commands
    ###########################################################

    @app_commands.command(name="testalert", description="Create a dummy raid alert for testing.")
    @app_commands.guilds(discord.Object(id=int(os.getenv('GUILD_ID'))))
    @app_commands.checks.has_permissions(administrator=True)
    async def testalert(self, interaction: discord.Interaction):
        # Send a test/dummy raid alert for this guild
        guild_id = interaction.guild.id
        now = self._get_current_kst()
        next_time = now + timedelta(minutes=5)
        dummy_raid = {
            "name": "😈 BlackSeraphimon",
            "map": "???",
            "next_time": next_time,
            "scheduled_time": next_time.strftime("%H:%M"),
            "image": self._get_image_url(self._clean_boss_name("BlackSeraphimon")),
            "guild_id": str(guild_id)  # Convert to string to match config keys
        }
        # Remove any previous test alert for this guild
        self.test_raids = [(gid, r) for (gid, r) in self.test_raids if gid != guild_id]
        self.test_raids.append((guild_id, dummy_raid))
        await self._send_or_update_raid_alert(guild_id, dummy_raid)
        locale = self._get_guild_locale(str(guild_id))
        await interaction.response.send_message(
            locale['commands']['testalert']['success'],
            ephemeral=True
        )

    @app_commands.command(name="setalerttz", description="Set the timezone for raid alerts.")
    @app_commands.guilds(discord.Object(id=int(os.getenv('GUILD_ID'))))
    @app_commands.describe(timezone="Choose between supported timezones: korea, brasilia, london, new_york, los_angeles")
    @app_commands.checks.has_permissions(administrator=True)
    async def settimezone(self, interaction: discord.Interaction, timezone: str):
        guild_id = str(interaction.guild.id)
        locale = self._get_guild_locale(guild_id)
        valid_zones = ["korea", "brasilia", "london", "new_york", "los_angeles"]
        if timezone.lower() not in valid_zones:
            await interaction.response.send_message(
                locale['commands']['settimezone']['invalid_timezone'],
                ephemeral=True
            )
            return

        self.settings_manager.load_settings()
        guild_settings = self.settings_manager.get_guild_settings(guild_id)
        guild_settings["timezone"] = timezone.lower()
        self.settings_manager.update_guild_settings(guild_id, guild_settings)
        
        await interaction.response.send_message(
            locale['commands']['settimezone']['success'].format(timezone=timezone.lower()),
            ephemeral=True
        )

    @app_commands.command(name="setalertchannel", description="Set the channel for raid alerts.")
    @app_commands.guilds(discord.Object(id=int(os.getenv('GUILD_ID'))))
    @app_commands.checks.has_permissions(administrator=True)
    async def setalertchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        guild_id = str(interaction.guild.id)
        locale = self._get_guild_locale(guild_id)
        self.settings_manager.load_settings()
        current_settings = self.settings_manager.get_guild_settings(guild_id)
        raid_alerts = current_settings.get('raid_alerts', {})
        raid_alerts['channel_id'] = channel.id
        self.settings_manager.update_guild_settings(guild_id, {'raid_alerts': raid_alerts})
        
        await interaction.response.send_message(
            locale['commands']['setalertchannel']['success'].format(channel=channel.mention),
            ephemeral=True
        )

    @app_commands.command(name="setalertrole", description="Set the role to tag for raid alerts.")
    @app_commands.guilds(discord.Object(id=int(os.getenv('GUILD_ID'))))
    @app_commands.checks.has_permissions(administrator=True)
    async def setalertrole(self, interaction: discord.Interaction, role: discord.Role):
        guild_id = str(interaction.guild.id)
        locale = self._get_guild_locale(guild_id)
        current_settings = self.settings_manager.get_guild_settings(guild_id)
        raid_alerts = current_settings.get('raid_alerts', {})
        raid_alerts['role_id'] = role.id
        self.settings_manager.update_guild_settings(guild_id, {'raid_alerts': raid_alerts})
        
        await interaction.response.send_message(
            locale['commands']['setalertrole']['success'].format(role=role.mention),
            ephemeral=True
        )

    @app_commands.command(name="togglealert", description="Enable or disable the raid alert feature.")
    @app_commands.guilds(discord.Object(id=int(os.getenv('GUILD_ID'))))
    @app_commands.checks.has_permissions(administrator=True)
    async def togglealert(self, interaction: discord.Interaction, enabled: bool):
        guild_id = str(interaction.guild.id)
        current_settings = self.settings_manager.get_guild_settings(guild_id)
        raid_alerts = current_settings.get('raid_alerts', {})
        raid_alerts['enabled'] = enabled
        self.settings_manager.update_guild_settings(guild_id, {'raid_alerts': raid_alerts})
        state = "enabled" if enabled else "disabled"
        locale = self._get_guild_locale(guild_id)
        await interaction.response.send_message(
            locale['commands']['togglealert'][f'success_{state}'], ephemeral=True
        )

    def _get_guild_timezone(self, guild_id):
        self.settings_manager.load_settings()
        guild_settings = self.settings_manager.settings.get(str(guild_id), {})
        return self.timezones.get(
            guild_settings.get('timezone'),
            self.default_tz
        )

    def _get_guild_locale(self, guild_id):
        try:
            self.settings_manager.load_settings()
            guild_settings = self.settings_manager.settings.get(str(guild_id), {})
            lang = guild_settings.get('language', 'english').lower()
            lang_map = {'english': 'en', 'portuguese': 'pt', 'spanish': 'es'}
            lang_code = lang_map.get(lang, 'en')
            
            # Get absolute path to locales directory
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
            locale_path = os.path.join(base_dir, 'locales', f'{lang_code}.json')
            
            self._log("DEBUG", f"⏳ Loading locale for guild {guild_id}: {lang} -> {locale_path}")
            
            if not os.path.exists(locale_path):
                self._log("ERROR", f"❌ Locale file not found: {locale_path}")
                raise FileNotFoundError(f"❌ Locale file not found: {locale_path}")
                
            with open(locale_path, 'r', encoding='utf-8') as f:
                locale_data = json.load(f)
                self._log("DEBUG", f"✅ Loaded locale for {guild_id}: {list(locale_data['raid_alerts'].keys())}")
                return locale_data
                
        except Exception as e:
            self._log("ERROR", f"❌ Failed to load locale for guild {guild_id}: {str(e)}")
            return {}

###########################################################
# Cog Setup
###########################################################

async def setup(bot):
    guild_id = int(os.getenv('GUILD_ID'))
    cog = RaidAlert(bot)
    await bot.add_cog(cog)
    
    # Move all commands to the guild
    for command in cog.walk_app_commands():
        command.guild = discord.Object(id=guild_id)
    
    logger = logging.getLogger('discord')
