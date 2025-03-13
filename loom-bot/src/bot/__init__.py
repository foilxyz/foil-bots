import asyncio
import logging
from datetime import datetime

from web3 import Web3

from shared.clients.discord_client import DiscordNotifier
from shared.utils.web3_utils import create_web3_provider

from .api_client import FoilAPIClient
from .config import BotConfig
from .exceptions import SkipBotRun
from .foil import Foil
from .position import Position
from .strategy import BotStrategy


class LoomBot:
    def __init__(self):
        # Load configuration
        self.config = BotConfig.get_config()

        # Setup logging
        self.logger = self._setup_logger()
        self.logger.info("Initializing Loom Bot...")

        # Initialize Web3 connection
        self.w3 = create_web3_provider(self.config.rpc_url, self.logger)

        # Initialize API client
        self.api_client = FoilAPIClient(self.config.foil_api_url)

        # Load foil
        self.foil = Foil(self.w3)

        # Initialize Discord notifier
        self.discord = DiscordNotifier.get_instance("LoomBot", self.config)

        # Load account address
        self.account_address = self.w3.eth.account.from_key(self.config.wallet_pk).address
        self.logger.info(f"Using wallet address: {self.account_address}")

        # Load position
        self.position = Position(self.account_address, self.foil, self.w3)

        self.logger.info("Bot initialization complete")

        # Send initialization message to Discord
        self.discord.send_message("🤖 Loom Bot initialized and ready!")

    def _setup_logger(self) -> logging.Logger:
        """Initialize logging configuration"""
        logger = logging.getLogger("LoomBot")
        logger.setLevel(logging.INFO)

        # Create console handler with formatting
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    async def start(self):
        """Start the bot"""
        self.logger.info(f"Starting bot with {self.config.bot_run_interval} second interval...")
        self.discord.send_message(f"🚀 Bot started with {self.config.bot_run_interval} second interval")

        strategy = BotStrategy(self.position, self.foil, self.account_address)

        while True:
            try:
                start_time = datetime.now()
                self.logger.info(f"Starting Bot Run - Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

                # get prices
                trailing_avg_price = self.api_client.get_trailing_average(
                    resource_slug="ethereum-gas",
                )
                current_market_price = self.foil.get_current_price_d18()
                current_market_price = self.w3.from_wei(current_market_price, "ether")
                self.logger.info(f"Price Details - Trailing Avg: {trailing_avg_price}, Current: {current_market_price}")

                strategy.run(current_market_price, trailing_avg_price)

                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                self.logger.info(f"Completed Run in {duration:.2f}s - Next in {self.config.bot_run_interval}s")

                await asyncio.sleep(self.config.bot_run_interval)
            except KeyboardInterrupt:
                self.logger.info("Bot stopped by user")
                self.discord.send_message("⛔ Bot stopped by user")
                raise
            except SkipBotRun:
                self.logger.info("Skipping bot run due to already optimized position")
                self.logger.info(f"Next run in {self.config.bot_run_interval}s")
                await asyncio.sleep(self.config.bot_run_interval)
            except Exception as e:
                self.logger.error(f"Error during bot execution: {str(e)}")
                self.discord.send_message(f"❌ **Error**: {str(e)}")
                self.logger.info(f"Next run in {self.config.bot_run_interval}s")
                await asyncio.sleep(self.config.bot_run_interval)
