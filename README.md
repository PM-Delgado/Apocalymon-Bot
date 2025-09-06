# ApocalymonBot

A modular Discord bot using discord.py, with cogs for features and best practices for production.

## Getting Started

1. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```
2. Set your bot token in the `.env` file.
3. Run the bot:
   ```sh
   python bot/main.py
   ```

## Project Structure

- `bot/` - Main bot code
  - `cogs/` - Feature modules (cogs)
  - `utils/` - Utility modules
- `.env` - Environment variables (never commit secrets)
- `config.yaml` - Static config (e.g., raid schedule)
