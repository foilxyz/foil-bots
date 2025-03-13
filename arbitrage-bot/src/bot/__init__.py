"""
Arbitrage Bot - A bot for cryptocurrency arbitrage on the foil contract.
"""

import asyncio
import logging
from datetime import datetime

from web3 import Web3

from shared.clients.discord_client import DiscordNotifier
from shared.utils.async_web3_utils import create_async_web3_provider

from .arb import ArbitrageLogic
from .config import ArbitrageConfig
from .foil import Foil
from .position import Position


class ArbitrageBot:
    """Main arbitrage bot implementation"""

    def __init__(self):
        """Initialize the arbitrage bot"""
        # Load configuration
        self.config = ArbitrageConfig.get_config()

        # Setup logging
        self.logger = self._setup_logger()
        self.logger.info("Initializing Arbitrage Bot...")

        # Initialize Web3 connection asynchronously - this will be properly awaited in the start method
        self.w3 = None  # Will be initialized in start()

        # Initialize Discord client
        self.discord = DiscordNotifier.get_instance("ArbitrageBot", self.config)

        # Load account address - no Web3 instance needed for this
        self.account_address = Web3.to_checksum_address(self.config.wallet_pk)
        self.logger.info(f"Using wallet address: {self.account_address}")

        # These will be initialized in the start method
        self.foil = None
        self.position = None
        self.arb_logic = None

        self.logger.info("Arbitrage Bot initialization complete")
        self.discord.send_message("🤖 Arbitrage Bot initialized and ready!")

    def _setup_logger(self) -> logging.Logger:
        """Initialize logging configuration"""
        logger = logging.getLogger("ArbitrageBot")
        logger.setLevel(logging.INFO)

        # Create console handler with formatting
        handler = logging.StreamHandler()
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)

        return logger

    async def start(self):
        """Start the arbitrage bot"""
        self.logger.info(f"Starting bot with {self.config.trade_interval} second interval...")
        self.discord.send_message(f"🚀 Bot started with {self.config.trade_interval} second interval")

        # Initialize async web3 provider
        self.w3 = await create_async_web3_provider(self.config.rpc_url, self.logger)

        # Initialize components that need web3
        self.foil = Foil(self.w3)
        self.position = Position(self.account_address, self.foil, self.w3)
        self.arb_logic = ArbitrageLogic(self.foil, self.position)

        while True:
            try:
                start_time = datetime.now()
                self.logger.info(f"Starting Bot Run - Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

                # Get all data concurrently - trailing price, pool price, and position
                avg_price_task = asyncio.create_task(self.foil.get_avg_trailing_price())
                pool_price_task = asyncio.create_task(self.foil.get_current_pool_price())
                position_task = asyncio.create_task(self.position.hydrate_current_position())

                # Wait for all tasks to complete
                avg_trailing_price, current_pool_price, _ = await asyncio.gather(
                    avg_price_task, pool_price_task, position_task
                )

                self.logger.info(f"Price data - Avg: {avg_trailing_price}, Pool: {current_pool_price}")

                # Run arbitrage logic
                result = await self.arb_logic.run(avg_trailing_price, current_pool_price)

                if result["performed_arb"]:
                    self.discord.send_message(
                        f"✅ Successfully executed arbitrage:\n"
                        f"- Price Difference: {result['price_difference']}\n"
                        f"- Profit: {result.get('profit', 'N/A')}"
                    )
                else:
                    self.logger.info(f"No arbitrage performed: {result['reason']}")

                end_time = datetime.now()
                duration = (end_time - start_time).total_seconds()
                self.logger.info(f"Completed Run in {duration:.2f}s - Next in {self.config.trade_interval}s")

                await asyncio.sleep(self.config.trade_interval)

            except KeyboardInterrupt:
                self.logger.info("Bot stopped by user")
                self.discord.send_message("⛔ Bot stopped by user")
                raise

            except Exception as e:
                self.logger.error(f"Error during bot execution: {str(e)}")
                self.discord.send_message(f"❌ **Error**: {str(e)}")
                self.logger.info(f"Next run in {self.config.trade_interval}s")
                await asyncio.sleep(self.config.trade_interval)
