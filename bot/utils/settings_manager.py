from bot.main import supabase
import pytz
from typing import Dict, Any

class SettingsManager:
    _instance = None
    timezones = {
        "korea": pytz.timezone("Asia/Seoul"),
        "brasilia": pytz.timezone("America/Sao_Paulo"),
        "london": pytz.timezone("Europe/London"),
        "new_york": pytz.timezone("America/New_York"),
        "los_angeles": pytz.timezone("America/Los_Angeles")
    }

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance._init_settings()
        return cls._instance

    def _init_settings(self):
        self.load_settings()
        self.load_localizations()
        self.load_raid_alerts()

    def load_settings(self):
        response = supabase.table('guild_settings').select('*').execute()
        self.guild_settings = {str(item['guild_id']): item for item in response.data}

    def load_localizations(self):
        response = supabase.table('locales').select('*').execute()
        self.localizations = {}
        for item in response.data:
            lang = item['language']
            namespace = item['namespace']
            key = item['key']
            value = item['value']
            if lang not in self.localizations:
                self.localizations[lang] = {}
            if namespace not in self.localizations[lang]:
                self.localizations[lang][namespace] = {}
            self.localizations[lang][namespace][key] = value

    def load_raid_alerts(self):
        response = supabase.table('guild_raid_alerts').select('*').execute()
        self.raid_alerts = {str(item['guild_id']): item for item in response.data}

    def get_guild_settings(self, guild_id: str) -> Dict[str, Any]:
        return self.guild_settings.get(str(guild_id), {})

    def get_timezone(self, guild_id: str):
        tz_name = self.guild_settings.get(str(guild_id), {}).get('timezone', 'korea')
        return self.timezones.get(tz_name, self.timezones['korea'])

    def get_localization(self, guild_id: str) -> Dict[str, Any]:
        lang = self.guild_settings.get(str(guild_id), {}).get('language', 'en')
        return self.localizations.get(lang, {})

    def get_raid_alerts(self, guild_id: str) -> Dict[str, Any]:
        return self.raid_alerts.get(str(guild_id), {})

    def update_guild_settings(self, guild_id: str, updates: Dict[str, Any]):
        guild_id = str(guild_id)
        current = self.get_guild_settings(guild_id)
        updated = {**current, **updates}
        self.guild_settings[guild_id] = updated
        supabase.table('guild_settings').upsert({
            'guild_id': guild_id,
            **updated
        }).execute()

    def update_raid_alerts(self, guild_id: str, updates: Dict[str, Any]):
        guild_id = str(guild_id)
        current = self.get_raid_alerts(guild_id)
        updated = {**current, **updates}
        self.raid_alerts[guild_id] = updated
        supabase.table('guild_raid_alerts').upsert({
            'guild_id': guild_id,
            **updated
        }).execute()
    
# Singleton instance for all cogs to use
settings_manager = SettingsManager()
