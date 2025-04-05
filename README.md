# FOIL Bots Monorepo

A monorepo containing Web3 bots for automated trading and liquidity provision.

## Projects

This monorepo contains the following projects:

### 1. Loom Bot

A bot for automated liquidity provision on the FOIL protocol. It monitors market prices and optimizes LP positions based on market conditions.

### 2. Arbitrage Bot

A bot for cryptocurrency arbitrage across different DEXes. It scans multiple exchanges for price differences and executes trades when profitable opportunities are found.

## Shared Components

Both bots share common functionality through the `shared` directory:

- **Config Management**: Standardized configuration loading from environment variables
- **Discord Integration**: Real-time notifications and monitoring
- **Web3 Utilities**: Transaction handling, simulation, and blockchain interaction

## Directory Structure

```
foil-bots/
├── shared/                  # Shared modules
│   ├── clients/             # Shared client implementations
│   │   └── discord_client.py
│   ├── config/              # Configuration management
│   │   └── config_manager.py
│   └── utils/               # Utility functions
│       └── web3_utils.py
├── loom-bot/                # FOIL LP Bot
│   ├── src/
│   │   └── bot/
│   │       ├── strategy.py
│   │       ├── position.py
│   │       └── ...
│   └── .env.example
└── arbitrage-bot/           # Arbitrage Bot
    ├── src/
    │   └── bot/
    │       ├── strategy.py
    │       ├── markets.py
    │       └── ...
    └── .env.example
```

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd foil-bots
```

2. Install Poetry if you haven't already:

```bash
curl -sSL https://install.python-poetry.org | python3 -
```

3. Install dependencies using Poetry:

```bash
# Install root project dependencies
poetry install

# For loom-bot only
cd loom-bot
poetry install

# For arbitrage-bot only
cd ../arbitrage-bot
poetry install
```

## Configuration

Each bot has its own `.env` file for configuration. Copy the example files and customize:

```bash
# For Loom Bot
cp loom-bot/.env.example loom-bot/.env

# For Arbitrage Bot
cp arbitrage-bot/.env.example arbitrage-bot/.env
```

## Running the Bots

### Loom Bot

```bash
# From the root directory
poetry run loom-bot

# Or from the loom-bot directory
cd loom-bot
poetry run loom-bot
```

### Arbitrage Bot

```bash
# From the root directory
poetry run arbitrage-bot

# Or from the arbitrage-bot directory
cd arbitrage-bot
poetry run arbitrage-bot
```

## Discord Setup

Both bots can send notifications to Discord. To set this up:

1. Create a Discord bot at the [Discord Developer Portal](https://discord.com/developers/applications)
2. Add the bot to your server
3. Get the bot token and channel ID
4. Add these to your `.env` files

## Development

To add a new shared component:

1. Add the code to the appropriate directory in `shared/`
2. Import it in your bot code using the pattern: `from shared.module.file import Component`

## License

MIT

## Disclaimer

These bots are for educational purposes only. Use at your own risk. The authors are not responsible for any financial losses incurred through the use of these bots.
