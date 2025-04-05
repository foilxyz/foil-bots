import asyncio
import logging
import threading
from typing import Any, Dict, Optional, Type, TypeVar

import discord
from discord.ext import commands

# Generic BaseConfig type to allow different bot configs
T = TypeVar("T", bound="BaseConfig")


class BaseConfig:
    """Interface for configs that provide Discord settings"""

    discord_bot_token: Optional[str] = None
    discord_channel_id: Optional[str] = None


class DiscordNotifier:
    """
    Discord notification client for bots in the monorepo
    """

    # Dictionary to store instances by bot_name
    _instances: Dict[str, "DiscordNotifier"] = {}

    @classmethod
    def get_instance(cls, bot_name: str, config: Any) -> "DiscordNotifier":
        """Get or create a Discord notifier instance for a specific bot"""
        if bot_name not in cls._instances:
            cls._instances[bot_name] = DiscordNotifier(bot_name, config)
        return cls._instances[bot_name]

    def __init__(self, bot_name: str, config: Any):
        """
        Initialize Discord notifier

        Args:
            bot_name: Name of the bot using this notifier (for logging)
            config: Config object with discord_bot_token and discord_channel_id
        """
        self.bot_name = bot_name
        self.logger = logging.getLogger(f"{bot_name}.Discord")
        self.config = config

        # Check if Discord is configured
        self.enabled = bool(getattr(config, "discord_bot_token", None) and getattr(config, "discord_channel_id", None))

        if not self.enabled:
            self.logger.warning("Discord notifications disabled: missing token or channel ID")
            return

        # Initialize Discord client
        intents = discord.Intents.default()
        self.bot = commands.Bot(command_prefix="!", intents=intents)

        # Get channel ID as int
        try:
            self.channel_id = int(config.discord_channel_id)
        except (ValueError, TypeError):
            self.logger.error(f"Invalid discord_channel_id: {config.discord_channel_id}")
            self.enabled = False
            return

        self.ready = False
        self.message_queue = asyncio.Queue()
        self.channel_cache = {}

        # Set up event handlers
        @self.bot.event
        async def on_ready():
            self.logger.info(f"Discord bot logged in as {self.bot.user}")

            # Cache the channel
            try:
                channel = await self.bot.fetch_channel(self.channel_id)
                self.channel_cache[self.channel_id] = channel
            except Exception as e:
                self.logger.error(f"Error fetching channel {self.channel_id}: {str(e)}")

            self.ready = True
            # Start processing messages from queue
            asyncio.create_task(self._process_message_queue())

        # Start the bot in the background
        self._start_bot()

    def _start_bot(self):
        """Start the Discord bot in a background thread"""
        if not self.enabled:
            return

        thread_name = f"DiscordBot-{self.bot_name}"

        def run_bot():
            """Run the Discord bot in a new event loop"""
            import asyncio

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Store the loop in the thread
            thread = threading.current_thread()
            thread.name = thread_name
            thread._asyncio_loop = loop

            try:
                loop.run_until_complete(self.bot.start(self.config.discord_bot_token))
            except Exception as e:
                self.logger.error(f"Error in Discord bot: {str(e)}")

        # Start bot in a daemon thread so it doesn't block program exit
        thread = threading.Thread(target=run_bot, daemon=True, name=thread_name)
        thread.start()
        self.logger.info(f"Discord bot started in background thread: {thread_name}")

    def _get_bot_loop(self):
        """Get the event loop where the bot is running"""
        # Find the thread where the bot is running
        thread_name = f"DiscordBot-{self.bot_name}"
        for thread in threading.enumerate():
            if thread.name == thread_name:
                return getattr(thread, "_asyncio_loop", None)

        # Fallback: try to get the current event loop
        try:
            return asyncio.get_event_loop()
        except RuntimeError:
            # Create a new loop if none exists in this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            return loop

    async def _process_message_queue(self):
        """Process messages from the queue once the bot is ready"""
        while True:
            # Get next message from queue
            message_data = await self.message_queue.get()

            try:
                if isinstance(message_data, tuple):
                    message, channel_id = message_data
                else:
                    message, channel_id = message_data, self.channel_id

                # Get channel from cache or fetch it
                channel = self.channel_cache.get(channel_id)
                if not channel:
                    try:
                        channel = await self.bot.fetch_channel(channel_id)
                        self.channel_cache[channel_id] = channel
                    except Exception as e:
                        self.logger.error(f"Error fetching channel {channel_id}: {str(e)}")
                        self.message_queue.task_done()
                        continue

                # Send the message
                await channel.send(message)
                self.logger.info(f"Discord message sent to channel {channel_id}")

            except Exception as e:
                self.logger.error(f"Error sending Discord message: {str(e)}")

            finally:
                # Mark task as done
                self.message_queue.task_done()

    async def _queue_message(self, message: str, channel_id: Optional[int] = None):
        """Async method to properly await putting messages in the queue"""
        if channel_id:
            await self.message_queue.put((message, channel_id))
        else:
            await self.message_queue.put(message)

    def send_message(self, message: str, channel_id: Optional[int] = None):
        """Queue a message to be sent to the configured Discord channel"""
        if not self.enabled:
            return

        try:
            # Run coroutine in the bot's event loop
            target_channel = channel_id or self.channel_id
            loop = self._get_bot_loop()

            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(self._queue_message(message, target_channel), loop)
            else:
                self.logger.warning("Could not get bot's event loop, message not sent")

        except Exception as e:
            self.logger.error(f"Error queueing Discord message: {str(e)}")
