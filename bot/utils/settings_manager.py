import json
import os

class SettingsManager:
    _instance = None
    SETTINGS_FILE = 'server_settings.json'
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance.load_settings()
        return cls._instance
    
    def load_settings(self):
        """Load settings from JSON file"""
        try:
            with open(self.SETTINGS_FILE, 'r', encoding='utf-8') as f:
                self.settings = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            self.settings = {}
    
    def save_settings(self):
        """Save settings to JSON file"""
        with open(self.SETTINGS_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.settings, f, indent=4)
    
    def get_guild_settings(self, guild_id: str):
        """Get settings for a specific guild"""
        return self.settings.get(str(guild_id), {})
    
    def update_guild_settings(self, guild_id: str, new_settings: dict):
        """Update settings for a specific guild"""
        guild_id = str(guild_id)
        current = self.get_guild_settings(guild_id)
        self.settings[guild_id] = {**current, **new_settings}
        self.save_settings()

# Singleton instance for all cogs to use
settings_manager = SettingsManager()
