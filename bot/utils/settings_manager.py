from bot.main import supabase

class SettingsManager:
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SettingsManager, cls).__new__(cls)
            cls._instance.load_settings()
        return cls._instance
    
    def load_settings(self):
        response = supabase.table('guild_settings').select('guild_id, settings').execute()
        self.settings = {str(item['guild_id']): item['settings'] for item in response.data}
    
    
    def get_guild_settings(self, guild_id: str):
        return self.settings.get(str(guild_id), {})
    
    def update_guild_settings(self, guild_id: str, new_settings: dict):
        guild_id = str(guild_id)
        current = self.get_guild_settings(guild_id)
        updated_settings = {**current, **new_settings}
        self.settings[guild_id] = updated_settings
        supabase.table('guild_settings').upsert({
            'guild_id': guild_id,
            'settings': updated_settings
        }).execute()
    
# Singleton instance for all cogs to use
settings_manager = SettingsManager()
