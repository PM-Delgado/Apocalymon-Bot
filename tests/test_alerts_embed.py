import pytest
import pytz
from unittest.mock import MagicMock, patch
from bot.cogs.raid_alert import RaidAlert
from datetime import datetime

@pytest.mark.parametrize("language,timezone,expected_gmt", [
    ("english", "korea", "GMT+9"),
    ("portuguese", "brasilia", "GMT-3"),
    ("english", "london", "GMT+1"),
    ("spanish", "los_angeles", "GMT-7"),
    ("portuguese", "new_york", "GMT-4"),
])
def test_embed_content_for_locales_and_timezones(language, timezone, expected_gmt):
    bot = MagicMock()
    timezones = {
        "korea": pytz.timezone("Asia/Seoul"),
        "brasilia": pytz.timezone("America/Sao_Paulo"),
        "london": pytz.timezone("Europe/London"),
        "new_york": pytz.timezone("America/New_York"),
        "los_angeles": pytz.timezone("America/Los_Angeles")
    }
    with patch.object(RaidAlert, "_raid_alert_loop", create=True):
        cog = RaidAlert(bot)
        guild_id = "123456"
        cog.settings_manager.update_guild_settings(guild_id, {"language": language})
        
        with patch.object(cog, '_get_guild_timezone') as mock_tz:
            mock_tz.return_value = timezones[timezone]
            raid = {
                "name": "🪽 Andromon",
                "map": "Gear Savannah",
                "next_time": cog.default_tz.localize(datetime(2025, 9, 14, 12, 0)),
                "scheduled_time": "12:00",
                "guild_id": guild_id
            }
            embed, status = cog._create_embed_content(raid, 600)

            # Assert the correct language string is present
            if language == "english":
                assert "⏳ Starts in" in embed.fields[2].value
            elif language == "portuguese":
                assert "⏳ Começa em" in embed.fields[2].value
            elif language == "spanish":
                assert "⏳ Comienza en" in embed.fields[2].value
            assert expected_gmt in embed.fields[1].value
            
            # Assert the correct timezone is reflected in the embed
            displayed_time = embed.fields[1].value
            if timezone == "korea":
                assert "(GMT+9" in displayed_time
            elif timezone == "brasilia":
                assert "(GMT-3" in displayed_time
            elif timezone == "london":
                assert "(GMT+1" in displayed_time
            elif timezone == "los_angeles":
                assert "(GMT-7" in displayed_time
            elif timezone == "new_york":
                assert "(GMT-4" in displayed_time