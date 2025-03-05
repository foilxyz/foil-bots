import logging
from typing import Optional

import discord
from discord.ext import commands

from .config import BotConfig


class DiscordNotifier:
    """
    Discord notification client for the Loom Bot
    """

    _instance: Optional["DiscordNotifier"] = None

    @classmethod
    def get_instance(cls) -> "DiscordNotifier":
        """Get or create the singleton instance"""
        if cls._instance is None:
            cls._instance = DiscordNotifier()
        return cls._instance

    def __init__(self):
        self.logger = logging.getLogger("LoomBot.Discord")
        self.config = BotConfig.get_config()

        # Check if Discord is configured
        self.enabled = bool(self.config.discord_bot_token and self.config.discord_channel_id)

        if not self.enabled:
            self.logger.warning("Discord notifications disabled: missing token or channel ID")
            return

        # Initialize Discord client
        intents = discord.Intents.default()
        intents.message_content = True

        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.channel_id = int(self.config.discord_channel_id)
        self.ready = False

        # Set up event handlers
        @self.bot.event
        async def on_ready():
            self.logger.info(f"Discord bot logged in as {self.bot.user}")
            self.ready = True

        # Start the bot in the background
        self._start_bot()

    def _start_bot(self):
        """Start the Discord bot in a background thread"""
        import threading

        def run_bot():
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            loop.run_until_complete(self.bot.start(self.config.discord_bot_token))

        # Start bot in a daemon thread so it doesn't block program exit
        thread = threading.Thread(target=run_bot, daemon=True)
        thread.start()
        self.logger.info("Discord bot started in background thread")

    async def _send_message_async(self, message: str):
        """Send a message to the configured channel (async version)"""
        if not self.enabled:
            return

        try:
            # Wait for bot to be ready
            if not self.ready:
                self.logger.warning("Discord bot not ready yet, message might not be sent")

            # Get the channel
            channel = self.bot.get_channel(self.channel_id)
            if not channel:
                self.logger.error(f"Could not find Discord channel with ID {self.channel_id}")
                return

            # Send the message
            await channel.send(message)
            self.logger.info(f"Discord message sent to channel {self.channel_id}")

        except Exception as e:
            self.logger.error(f"Error sending Discord message: {str(e)}")

    def send_message(self, message: str):
        """Send a message to the configured Discord channel"""
        if not self.enabled:
            return

        import asyncio

        # Create a new event loop for this thread if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        # Run the async send function
        if loop.is_running():
            # If we're already in an event loop, create a task
            asyncio.create_task(self._send_message_async(message))
        else:
            # Otherwise run the coroutine directly
            loop.run_until_complete(self._send_message_async(message))
