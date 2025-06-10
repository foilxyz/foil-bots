import sys

from . import run_bot


def main():
    """Run the bot once - ideal for cron jobs"""
    try:
        run_bot()
    except KeyboardInterrupt:
        print("Bot stopped by user")
        sys.exit(0)
    except Exception as e:
        print(f"Bot failed with error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
