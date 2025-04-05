"""
Main entry point for the Arbitrage Bot
"""

import asyncio
import logging

from . import ArbitrageBot


async def main_async():
    """Async main function"""
    try:
        bot = ArbitrageBot()
        await bot.start()
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Fatal error: {str(e)}")
        raise


def main():
    """Main function"""
    # Configure basic logging - only once
    root_logger = logging.getLogger()

    # Only configure if no handlers exist already
    if not root_logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        )

    # Run the async main function
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
