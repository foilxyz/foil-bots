"""
Arbitrage Bot - A bot for cryptocurrency arbitrage on the foil contract.
"""

import asyncio
import logging
from datetime import datetime
from decimal import Decimal

from shared.clients.discord_client import DiscordNotifier
from shared.utils.async_web3_utils import create_async_web3_provider

from .api_client import GarbApiClient
from .arb import ArbitrageLogic
from .config import ArbitrageConfig
from .foil import Foil
from .position import Position


class ArbitrageBot:
    """Main arbitrage bot implementation"""

    def __init__(self):
        """Initialize the arbitrage bot"""
        # Load configuration - use reload_config to ensure fresh values
        self.config = ArbitrageConfig.reload_config()

        # Setup logging
        self.logger = self._setup_logger()
        self.logger.info("Initializing Arbitrage Bot...")

        # Initialize Web3 connection asynchronously - this will be properly awaited in the start method
        self.w3 = None  # Will be initialized in start()

        # Initialize Discord client
        self.discord = DiscordNotifier.get_instance("ArbitrageBot", self.config)

        # These will be initialized in the start method
        self.foil = None
        self.position = None
        self.arb_logic = None
        self.api_client = None

        self.logger.info("Arbitrage Bot initialization complete")
        self.discord.send_message("🤖 Arbitrage Bot initialized and ready!")

    def _setup_logger(self) -> logging.Logger:
        """Initialize logging configuration"""
        logger = logging.getLogger("ArbitrageBot")

        # Only add handlers if the logger doesn't already have any
        # This prevents duplicate logging
        if not logger.handlers:
            logger.setLevel(logging.INFO)

            # Create console handler with formatting
            handler = logging.StreamHandler()
            formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
            handler.setFormatter(formatter)
            logger.addHandler(handler)

            # Prevent propagation to the root logger to avoid duplicate logs
            logger.propagate = False

        return logger

    async def start(self):
        """Start the arbitrage bot"""
        self.logger.info(f"Starting bot with {self.config.trade_interval} second interval...")
        self.discord.send_message(f"🚀 Bot started with {self.config.trade_interval} second interval")

        # Initialize async web3 provider
        self.w3 = await create_async_web3_provider(self.config.rpc_url, self.logger)

        # Load account address - no Web3 instance needed for this
        self.account_address = self.w3.eth.account.from_key(self.config.wallet_pk).address
        self.logger.info(f"Using wallet address: {self.account_address}")

        # Initialize API client
        self.api_client = GarbApiClient(self.config.foil_api_url)

        # Initialize components that need web3
        self.foil = Foil(self.w3)
        # Initialize the foil contract data asynchronously
        await self.foil.initialize()

        self.position = Position(self.account_address, self.foil, self.w3)
        self.arb_logic = ArbitrageLogic(self.foil, self.position)

        while True:
            try:
                start_time = datetime.now()
                self.logger.info(f"Starting Bot Run - Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}")

                # Get all data concurrently - trailing price from API, pool price from contract, and position
                # Use API client for trailing average price
                avg_price_task = asyncio.create_task(self.api_client.get_trailing_average("ethereum-gas"))
                pool_price_task = asyncio.create_task(self.foil.get_current_price_d18())
                position_task = asyncio.create_task(self.position.hydrate_current_position())

                # Wait for all tasks to complete
                avg_trailing_price, current_pool_price, _ = await asyncio.gather(
                    avg_price_task, pool_price_task, position_task
                )

                self.logger.info(f"Price data - API Avg: {avg_trailing_price} gwei, Pool: {current_pool_price}")

                # Run arbitrage logic with the converted trailing price
                result = await self.arb_logic.run(Decimal(avg_trailing_price), Decimal(current_pool_price))

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
