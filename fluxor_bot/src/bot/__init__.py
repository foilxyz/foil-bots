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
        self.logger.info("Configuration Summary:")
        self.logger.info(f"- API URL: {self.config.foil_api_url}")
        self.logger.info(f"- Chain ID: {self.config.chain_id}")
        self.logger.info(f"- Base Token: {self.config.base_token_name}")

        self.logger.info("Bot initialization complete")

        # Send initialization message to Discord
        if self.discord:
            init_message = "🤖 **Fluxor Bot Initialized**\n"
            init_message += f"- API URL: {self.config.foil_api_url}\n"
            init_message += f"- Chain ID: {self.config.chain_id}\n"
            init_message += f"- Base Token: {self.config.base_token_name}\n"
            init_message += "- Markets will be fetched dynamically from API"
            self.discord.send_message(init_message)

    def _setup_logger(self) -> logging.Logger:
        """Setup logger configuration"""
        logger = logging.getLogger("FluxorBot")
        logger.setLevel(logging.INFO)

        if not logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            logger.addHandler(handler)

        return logger

    async def run(self):
        """Run the bot once"""
        try:
            # Run all markets
            await self.market_manager.run_all_markets()

        except SkipBotRun as e:
            self.logger.warning(f"Skipping bot run: {e}")

            if self.discord:
                self.discord.send_message(f"⏭️ **Bot Run Skipped**\n{e}")

        except Exception as e:
            self.logger.error(f"Bot run failed: {e}")

            if self.discord:
                self.discord.send_message(f"💥 **Bot Run Failed**\n```{e}```")

            raise


def run_bot():
    """Main entry point for the bot"""
    try:
        bot = FluxorBot()
        asyncio.run(bot.run())

    except Exception as e:
        logging.error(f"Failed to run bot: {e}")
        raise
