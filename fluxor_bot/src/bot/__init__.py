import asyncio
import logging
from datetime import datetime

from shared.clients.discord_client import DiscordNotifier
from shared.utils.web3_utils import create_web3_provider

from .config import BotConfig
from .exceptions import SkipBotRun
from .market_manager import MarketManager


class FluxorBot:
    def __init__(self):
        # Load configuration - use reload_config to ensure fresh values
        self.config = BotConfig.reload_config()

        # Setup logging
        self.logger = self._setup_logger()
        self.logger.info("Initializing Fluxor Bot...")

        # Initialize Web3 connection
        self.w3 = create_web3_provider(self.config.rpc_url, self.logger)

        # Load account address
        self.account_address = self.w3.eth.account.from_key(self.config.wallet_pk).address
        self.logger.info(f"Using wallet address: {self.account_address}")

        # Initialize Discord notifier
        self.discord = DiscordNotifier.get_instance("FluxorBot", self.config)

        # Initialize market manager
        self.market_manager = MarketManager(self.config, self.w3, self.account_address)

        # Log configuration summary
        market_ids = self.market_manager.get_markets_summary()
        total_markets = self.market_manager.get_market_count()

        self.logger.info("Configuration Summary:")
        self.logger.info(f"- Total Markets: {total_markets}")
        for market_id in market_ids:
            self.logger.info(f"- Market: {market_id}")

        self.logger.info("Bot initialization complete")

        # Send initialization message to Discord
        if self.discord:
            init_message = "🤖 **Fluxor Bot Initialized**\n"
            init_message += f"- Total Markets: {total_markets}\n"
            for market_id in market_ids:
                init_message += f"- Market: {market_id}\n"
            init_message += f"- Run Interval: {self.config.bot_run_interval}s"
            self.discord.send_message(init_message)

    def _setup_logger(self) -> logging.Logger:
        """Initialize logging configuration"""
        # Configure the root logger to catch all logs
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)

        # Clear any existing handlers to avoid duplicates
        root_logger.handlers.clear()

        # Create console handler with formatting
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        root_logger.addHandler(handler)

        # Get the FluxorBot logger
        logger = logging.getLogger("FluxorBot")
        logger.setLevel(logging.INFO)

        return logger

    async def start(self):
        """Start the bot"""
        self.logger.info(f"Starting bot with {self.config.bot_run_interval} second interval...")

        if self.discord:
            self.discord.send_message(f"🚀 Bot started with {self.config.bot_run_interval} second interval")

        while True:
            try:
                start_time = datetime.now()
                self.logger.info(f"Starting Bot Run - Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

                # Run all market strategies concurrently
                await self.market_manager.run_all_markets()

                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                self.logger.info(f"Completed Run in {duration:.2f}s - Next in {self.config.bot_run_interval}s")

                await asyncio.sleep(self.config.bot_run_interval)

            except KeyboardInterrupt:
                self.logger.info("Bot stopped by user")
                if self.discord:
                    self.discord.send_message("⛔ Bot stopped by user")
                raise
            except SkipBotRun:
                self.logger.info("Skipping bot run")
                self.logger.info(f"Next run in {self.config.bot_run_interval}s")
                await asyncio.sleep(self.config.bot_run_interval)
            except Exception as e:
                self.logger.error(f"Error during bot execution: {str(e)}")
                if self.discord:
                    self.discord.send_message(f"❌ **Error**: {str(e)}")
                self.logger.info(f"Next run in {self.config.bot_run_interval}s")
                await asyncio.sleep(self.config.bot_run_interval)
