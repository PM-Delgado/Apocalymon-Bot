
###########################################################
# DSR Raid Alert Cog for Apocalymon Bot
###########################################################

import discord
from discord import app_commands
from discord.ext import commands, tasks
import yaml
from datetime import datetime, timedelta
import pytz
import os

# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------
GUILD_ID = int(os.getenv('GUILD_ID'))

# ---------------------------------------------------------
# RaidAlert Cog
# ---------------------------------------------------------
class RaidAlert(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        # {guild_id: {enabled, channel_id, role_id}}
        self.guild_alert_config = {}
        # {(guild_id, raid_name, scheduled_time): {'message_id', 'channel_id', 'embed', 'raid', 'last_update'}}
        self.sent_messages = {}
        # {(guild_id, raid_name, scheduled_time)}
        self.completed_raids = set()
        # Timezones
        self.kst = pytz.timezone("Asia/Seoul")
        self.brt = pytz.timezone("America/Sao_Paulo")
        self.lisbon = pytz.timezone("Europe/Lisbon")
        # Cleanup interval (7 days)
        self.last_cleanup_time = None
        self.COMPLETED_RAIDS_CLEANUP_INTERVAL = 7 * 24 * 60 * 60
        # Load raid schedule from YAML
        self.raids = self.load_raid_schedule()
        # List of (guild_id, raid_dict) for test/dummy alerts
        self.test_raids = []
        # Start background loop
        self.raid_alert_loop.start()

    def cog_unload(self):
        self.raid_alert_loop.cancel()

    ###########################################################
    # Utilities
    ###########################################################

    def log(self, level, msg):
        # Log with timestamp in Lisbon timezone
        now = datetime.now(self.lisbon).strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{now}] [{level}] {msg}")

    def load_raid_schedule(self, config_path="raid_schedule.yaml"):
        config_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "raid_schedule.yaml")
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        return config["raids"]

    def get_current_kst(self):
        return datetime.now(self.kst)

    def clean_boss_name(self, raw_name: str) -> str:
        # Remove emoji and extra spaces
        return (raw_name.replace('🎃 ', '').replace('😈 ', '').replace('👹 ', '').replace('🤖 ', '').replace('🎲 ', '').replace('🪨 ', '').replace('🪽 ', '').strip())

    def get_image_path(self, name: str) -> str:
        # Return custom icon if available, else fallback to wiki image
        custom_icons = {
            "Pumpkinmon": os.getenv("DSR_RAID_ALERT_ICONS") + "/Pumpkinmon.png",
            "Gotsumon": os.getenv("DSR_RAID_ALERT_ICONS") + "/Gotsumon.png",
            "BlackSeraphimon": os.getenv("DSR_RAID_ALERT_ICONS") + "/BlackSeraphimon.png",
            "Ophanimon: Falldown Mode": os.getenv("DSR_RAID_ALERT_ICONS") + "/Ophanimon.png",
            "Megidramon": os.getenv("DSR_RAID_ALERT_ICONS") + "/Megidramon.png",
            "Omnimon": os.getenv("DSR_RAID_ALERT_ICONS") + "/Omnimon.png",
            "Andromon": os.getenv("DSR_RAID_ALERT_ICONS") + "/Andromon.png"
        }
        if name in custom_icons:
            return f"{custom_icons[name]}?v={int(datetime.now().timestamp())}"
        safe_name = name.replace(":", "_")
        return f"https://media.dsrwiki.com/dsrwiki/digimon/{safe_name}/{safe_name}.webp?v={int(datetime.now().timestamp())}"

    def get_map_image_url(self, map_name, boss_name=None):
        # Return custom map if available, else fallback to wiki map
        custom_maps = {
            "Pumpkinmon": os.getenv("DSR_RAID_ALERT_MAPS") + "/Pumpkinmon_map.jpg",
            "Gotsumon": os.getenv("DSR_RAID_ALERT_MAPS") + "/Gotsumon_map.jpg",
            "BlackSeraphimon": os.getenv("DSR_RAID_ALERT_MAPS") + "/BlackSeraphimon_map.jpg",
            "Ophanimon: Falldown Mode": os.getenv("DSR_RAID_ALERT_MAPS") + "/Ophanimon_map.jpg",
            "Megidramon": os.getenv("DSR_RAID_ALERT_MAPS") + "/Megidramon_map.jpg",
            "Omnimon": os.getenv("DSR_RAID_ALERT_MAPS") + "/Omnimon_map.jpg",
            "Andromon": os.getenv("DSR_RAID_ALERT_MAPS") + "/Andromon_map.jpg"
        }
        clean_name = self.clean_boss_name(boss_name) if boss_name else None
        if clean_name and clean_name in custom_maps:
            return f"{custom_maps[clean_name]}?v={int(datetime.now().timestamp())}"
        map_translation = {
            "Shibuya": "시부야",
            "Valley of Darkness": "어둠성 계곡",
            "Campground": "캠핑장",
            "Subway Station": "지하철 역",
            "???": "???",
            "Gear Savannah": "기어 사바나"
        }
        kr_name = map_translation.get(map_name)
        if not kr_name:
            return None
        if kr_name == "???":
            return f"https://media.dsrwiki.com/dsrwiki/map/ApocalymonArea.webp?v={int(datetime.now().timestamp())}"
        safe_name = "".join(kr_name.split())
        return f"https://media.dsrwiki.com/dsrwiki/map/{safe_name}.webp?v={int(datetime.now().timestamp())}"

    def get_remaining_minutes(self, seconds_total: int) -> int:
        # Round up if more than 30 seconds
        if seconds_total <= 0:
            return 0
        minutes = seconds_total // 60
        seconds = seconds_total % 60
        if seconds > 30:
            minutes += 1
        return minutes

    def format_minutos_pt(self, n: int) -> str:
        # Format minutes in Portuguese
        return "1 minuto" if n == 1 else f"{n} minutos"

    ###########################################################
    # Status and Color Helpers
    ###########################################################

    def compute_status(self, time_diff):
        # Determine raid status based on time difference (seconds)
        minutes_until = self.get_remaining_minutes(int(time_diff))
        if time_diff < -300:
            return "finished"
        elif minutes_until > 5:
            return "upcoming"
        elif 1 <= minutes_until <= 5:
            return "starting"
        elif minutes_until == 0 or (time_diff < 0 and time_diff >= -300):
            return "ongoing"

    def get_raid_status(self, time_diff):
        # Return (status, color) tuple
        status = self.compute_status(time_diff)
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

    def create_embed_content(self, raid, time_until_raid_seconds):
        # Build Discord embed for raid alert
        brt_time = raid["next_time"].astimezone(self.brt)
        minutes_until = self.get_remaining_minutes(int(time_until_raid_seconds))
        clean_name = self.clean_boss_name(raid['name'])
        status, color = self.get_raid_status(time_until_raid_seconds)
        if status in ("upcoming", "starting"):
            desc_status = f"⏳ Em {self.format_minutos_pt(minutes_until)}"
        elif status == "ongoing":
            minutes_ongoing = max(0, int((-time_until_raid_seconds) // 60))
            desc_status = f"⚔️ **Começou há {self.format_minutos_pt(minutes_ongoing)}**"
        else:
            desc_status = "✅ **Raid finalizada!**"
        horario_str = brt_time.strftime('%H:%M')
        embed = discord.Embed(
            title=clean_name,
            color=color
        )
        embed.add_field(name="", value=f"📍 {raid['map']}", inline=False)
        embed.add_field(name="", value=f"⏰ {horario_str}", inline=False)
        embed.add_field(name="", value=f"{desc_status}", inline=False)
        embed.set_thumbnail(url=self.get_image_path(clean_name))
        embed.set_footer(text="DSR Raid Alert | Done by Douleur")
        map_image_url = self.get_map_image_url(raid['map'], clean_name)
        if map_image_url:
            embed.set_image(url=map_image_url)
        return embed, status

    def create_content(self, raid, time_until_raid_seconds, role_mention, status):
        # Build message content for raid alert
        minutes_until = self.get_remaining_minutes(int(time_until_raid_seconds))
        if status == "ongoing":
            minutes_ongoing = max(0, int((-time_until_raid_seconds) // 60))
            ongoing_str = f"Começou há {self.format_minutos_pt(minutes_ongoing)}"
        if status in ("upcoming", "starting"):
            content = f"||{role_mention}||\n**{raid['name'].upper()}** | Começa em {self.format_minutos_pt(minutes_until)}!"
        elif status == "ongoing":
            content = f"||{role_mention}||\n**{raid['name'].upper()}** | {ongoing_str}!"
        else:
            content = f"||{role_mention}||\n**{raid['name'].upper()}** | Raid finalizada!"
        return content

    ###########################################################
    # Raid Time Calculations
    ###########################################################

    def get_next_daily_time(self, time_str):
        # Next daily raid time (KST)
        now = self.get_current_kst()
        raid_time = datetime.strptime(time_str, "%H:%M").time()
        raid_dt = self.kst.localize(datetime.combine(now.date(), raid_time))
        if raid_dt <= now:
            raid_dt += timedelta(days=1)
        return raid_dt

    def get_next_biweekly_time(self, time_str, base_date_str):
        # Next biweekly raid time (KST)
        now = self.get_current_kst()
        base_date = self.kst.localize(datetime.strptime(base_date_str, "%Y-%m-%d"))
        raid_time = datetime.strptime(time_str, "%H:%M").time()
        diff_days = (now.date() - base_date.date()).days
        cycles = diff_days // 14
        next_date = base_date + timedelta(days=cycles * 14)
        raid_dt = self.kst.localize(datetime.combine(next_date.date(), raid_time))
        if raid_dt <= now:
            raid_dt += timedelta(days=14)
        return raid_dt

    def get_next_rotation_time(self, base_time_str, base_date_str):
        # Next rotation raid time (e.g., Andromon)
        now = self.get_current_kst()
        base_date = self.kst.localize(datetime.strptime(base_date_str, "%Y-%m-%d"))
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

    def get_upcoming_raids(self):
        # Build list of all upcoming raids (real + test)
        raids = []
        for cfg in self.raids:
            name = cfg["name"]
            map_name = cfg["map"]
            freq = cfg.get("frequency", "daily")
            times = cfg.get("times", [])
            base_date = cfg.get("base_date")
            if freq == "rotation":  # Andromon case
                base_time = times[0]
                next_time_dt = self.get_next_rotation_time(base_time, base_date)
                raids.append({
                    "name": name,
                    "map": map_name,
                    "next_time": next_time_dt,
                    "scheduled_time": base_time,
                    "image": self.get_image_path(self.clean_boss_name(name)),
                })
                continue
            for t in times:
                if freq == "biweekly":
                    next_time_dt = self.get_next_biweekly_time(t, base_date)
                else:
                    next_time_dt = self.get_next_daily_time(t)
                raids.append({
                    "name": name,
                    "map": map_name,
                    "next_time": next_time_dt,
                    "scheduled_time": t,
                    "image": self.get_image_path(self.clean_boss_name(name)),
                })
        # Add test/dummy raids (from /testalert) to the list
        for guild_id, test_raid in getattr(self, 'test_raids', []):
            raids.append(test_raid)
        raids.sort(key=lambda r: r["next_time"])
        return raids

    ###########################################################
    # Send or Update Raid Alert Message
    ###########################################################
    async def send_or_update_raid_alert(self, guild_id, raid):
        config = self.guild_alert_config.get(guild_id)
        if not config or not config.get("enabled"):
            self.log("DEBUG", f"Guild {guild_id} not enabled or config missing.")
            return
        channel_id = config.get("channel_id")
        role_id = config.get("role_id")
        if not channel_id or not role_id:
            self.log("DEBUG", f"Guild {guild_id} missing channel or role config.")
            return
        channel = self.bot.get_channel(channel_id)
        if not channel:
            self.log("DEBUG", f"Channel {channel_id} not found in guild {guild_id}.")
            return
        role_mention = f"<@&{role_id}>"
        time_until_raid_seconds = (raid["next_time"] - self.get_current_kst()).total_seconds()
        embed, status = self.create_embed_content(raid, time_until_raid_seconds)
        content = self.create_content(raid, time_until_raid_seconds, role_mention, status)
        key = (guild_id, raid["name"], raid["next_time"].strftime("%Y-%m-%d %H:%M:%S"))
        self.log("DEBUG", f"send_or_update_raid_alert: key={key}, status={status}, time_until={time_until_raid_seconds}")
        # If already sent, update only if status or color changed
        if key in self.sent_messages:
            try:
                msg_id = self.sent_messages[key]['message_id']
                self.log("DEBUG", f"Attempting to update message {msg_id} in channel {channel_id}")
                msg = await channel.fetch_message(msg_id)
                prev_embed = self.sent_messages[key]['embed']
                # Only update the last field and color if changed
                prev_status_field = prev_embed.fields[-1].value if prev_embed.fields else None
                new_status_field = embed.fields[-1].value if embed.fields else None
                prev_color = prev_embed.color.value if prev_embed else None
                new_color = embed.color.value if embed else None
                if prev_status_field != new_status_field or prev_color != new_color or msg.content != content:
                    # Update only the last field and color
                    prev_embed.set_field_at(len(prev_embed.fields)-1, name="", value=new_status_field, inline=False)
                    prev_embed.color = embed.color
                    await msg.edit(content=content, embed=prev_embed, allowed_mentions=discord.AllowedMentions(roles=True))
                    self.sent_messages[key]['embed'] = prev_embed
                    self.sent_messages[key]['last_update'] = self.get_current_kst()
                    self.log("DEBUG", f"Updated message {msg_id} for {key}")
                else:
                    self.log("DEBUG", f"No change for message {msg_id} for {key}, skipping edit.")
            except Exception as e:
                self.log("DEBUG", f"Failed to update message {msg_id} for {key}: {e}")
                sent = await channel.send(content=content, embed=embed, allowed_mentions=discord.AllowedMentions(roles=True))
                self.sent_messages[key]['message_id'] = sent.id
                self.sent_messages[key]['last_update'] = self.get_current_kst()
                self.sent_messages[key]['embed'] = embed
                self.log("DEBUG", f"Sent new message {sent.id} for {key} after update failure")
        else:
            sent = await channel.send(content=content, embed=embed, allowed_mentions=discord.AllowedMentions(roles=True))
            self.sent_messages[key] = {
                'message_id': sent.id,
                'channel_id': channel_id,
                'embed': embed,
                'raid': raid,
                'last_update': self.get_current_kst()
            }
            self.log("DEBUG", f"Sent new message {sent.id} for {key}")

    ###########################################################
    # Main Raid Alert Loop
    ###########################################################
    @tasks.loop(seconds=10)
    async def raid_alert_loop(self):
        now_kst = self.get_current_kst()
        self.log("DEBUG", f"raid_alert_loop running at {now_kst}")
        upcoming_raids = self.get_upcoming_raids()
        # Periodic cleanup of completed_raids (every 7 days)
        if self.last_cleanup_time is None or (now_kst - self.last_cleanup_time).total_seconds() > self.COMPLETED_RAIDS_CLEANUP_INTERVAL:
            cutoff = now_kst - timedelta(seconds=self.COMPLETED_RAIDS_CLEANUP_INTERVAL)
            before = len(self.completed_raids)
            completed_raids_copy = set(self.completed_raids)
            for key in completed_raids_copy:
                try:
                    raid_time = datetime.strptime(key[2], "%Y-%m-%d %H:%M:%S")
                    raid_time = self.kst.localize(raid_time)
                    if raid_time < cutoff:
                        self.completed_raids.remove(key)
                except Exception:
                    continue
            after = len(self.completed_raids)
            self.log("CLEANUP", f"Cleaned up completed_raids: {before} -> {after}")
            self.last_cleanup_time = now_kst

        # For each enabled guild, send/update alerts
        for guild_id, config in self.guild_alert_config.items():
            self.log("DEBUG", f"Checking guild {guild_id} for alerts. Config: {config}")
            if not config.get("enabled"):
                continue
            for raid in upcoming_raids:
                time_diff = (raid["next_time"] - now_kst).total_seconds()
                key = (guild_id, raid["name"], raid["next_time"].strftime("%Y-%m-%d %H:%M:%S"))
                self.log("DEBUG", f"Considering raid {raid['name']} at {raid['next_time']} (key={key}, time_diff={time_diff})")
                # Only alert/update if within 10min before or 5min after
                if -300 <= time_diff <= 600 and key not in self.completed_raids:
                    self.log("DEBUG", f"Will send/update alert for {key}")
                    await self.send_or_update_raid_alert(guild_id, raid)
                # If finished, update message to finished state before removing
                if key in self.sent_messages and self.compute_status(time_diff) == "finished":
                    self.log("INFO", f"Marking {key} as finished, updating message to finished state before removal")
                    # Force update to finished state
                    await self.send_or_update_raid_alert(guild_id, raid)
                    del self.sent_messages[key]
                    self.completed_raids.add(key)

    @raid_alert_loop.before_loop
    async def before_raid_alert_loop(self):
        # Wait for bot to be ready before starting loop
        await self.bot.wait_until_ready()

    ###########################################################
    # Bot Commands
    ###########################################################

    @discord.app_commands.command(name="testalert", description="Send a dummy raid alert for testing.")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def testalert(self, interaction: discord.Interaction):
        # Send a test/dummy raid alert for this guild
        guild_id = interaction.guild.id
        now = self.get_current_kst()
        next_time = now + timedelta(minutes=0)
        dummy_raid = {
            "name": "😈 BlackSeraphimon",
            "map": "???",
            "next_time": next_time,
            "scheduled_time": next_time.strftime("%H:%M"),
            "image": self.get_image_path(self.clean_boss_name("BlackSeraphimon")),
        }
        # Remove any previous test alert for this guild
        self.test_raids = [(gid, raid) for (gid, raid) in self.test_raids if gid != guild_id]
        self.test_raids.append((guild_id, dummy_raid))
        key = (guild_id, dummy_raid["name"], next_time.strftime("%Y-%m-%d %H:%M:%S"))
        if key in self.sent_messages:
            del self.sent_messages[key]
        await self.send_or_update_raid_alert(guild_id, dummy_raid)
        await interaction.response.send_message("Test raid alert sent (scheduled for 10 minutes from now).", ephemeral=True)

    @discord.app_commands.command(name="ping", description="Check if the bot is alive.")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def ping(self, interaction: discord.Interaction):
        await interaction.response.send_message("Pong! 🏓", ephemeral=True)

    @discord.app_commands.command(name="setalertchannel", description="Set the channel for raid alerts.")
    @discord.app_commands.checks.has_permissions(administrator=True)
    async def setalertchannel(self, interaction: discord.Interaction, channel: discord.TextChannel):
        # Set the channel for raid alerts
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
        # Set the role to tag for raid alerts
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
        # Enable or disable the raid alert feature
        guild_id = interaction.guild.id
        if guild_id not in self.guild_alert_config:
            self.guild_alert_config[guild_id] = {}
        self.guild_alert_config[guild_id]["enabled"] = enabled
        state = "enabled" if enabled else "disabled"
        await interaction.response.send_message(f"Raid alert feature has been {state}.", ephemeral=True)

###########################################################
# Cog Setup
###########################################################
async def setup(bot):
    await bot.add_cog(RaidAlert(bot), guild=discord.Object(id=GUILD_ID))