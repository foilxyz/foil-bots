import asyncio
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

        self.bot = commands.Bot(command_prefix="!", intents=intents)
        self.channel_id = int(self.config.discord_channel_id)
        self.ready = False
        self.message_queue = asyncio.Queue()

        # Set up event handlers
        @self.bot.event
        async def on_ready():
            self.logger.info(f"Discord bot logged in as {self.bot.user}")
            self.ready = True
            # Start processing messages from queue
            asyncio.create_task(self._process_message_queue())

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

    async def _process_message_queue(self):
        """Process messages from the queue once the bot is ready"""
        while True:
            message = await self.message_queue.get()
            try:
                channel = await self.bot.fetch_channel(self.channel_id)
                await channel.send(message)
                self.logger.info(f"Discord message sent to channel {self.channel_id}")
            except Exception as e:
                self.logger.error(f"Error sending Discord message: {str(e)}")
            finally:
                self.message_queue.task_done()

    def send_message(self, message: str):
        """Queue a message to be sent to the configured Discord channel"""
        if not self.enabled:
            return

        try:
            # Get the event loop from the bot's thread
            loop = asyncio.get_event_loop()
            # Add message to queue
            loop.create_task(self.message_queue.put(message))
        except Exception as e:
            self.logger.error(f"Error queueing Discord message: {str(e)}")
