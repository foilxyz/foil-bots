import asyncio
import logging
import sys

from . import LoomBot


def main():
    try:
        bot = LoomBot()
        asyncio.run(bot.start())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        logging.error(f"Bot stopped due to error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
