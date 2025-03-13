# Loom Bot

A bot for automated liquidity provision on the FOIL protocol, built with Python.

## Features

- Automated position management for FOIL protocol
- Real-time price monitoring and position optimization
- Discord notifications for important events and errors
- Configurable trading parameters
- Support for both LP and trader positions

## Setup

1. Clone the repository
2. Install dependencies with Poetry:
   ```bash
   cd loom-bot
   poetry install
   ```
3. Create a `.env` file based on `.env.example`:
   ```bash
   cp .env.example .env
   ```

## Configuration

Configure your environment variables in `.env`:

```env
NETWORK_RPC_URL="https://mainnet.infura.io/v3/YOUR_KEY"

# Contract addresses
FOIL_ADDRESS="0x..."

# Trading parameters
RISK_SPREAD_SPACING_WIDTH=5
LP_RANGE_WIDTH=20
MIN_POSITION_SIZE=100000000000000000
MAX_POSITION_SIZE=200000000000000000
TRAILING_AVERAGE_DAYS=28

# Wallet PK
WALLET_PK="0x..."

# FOIL API URL
FOIL_API_URL="https://api.staging.foil.xyz"

# Bot run interval in seconds
BOT_RUN_INTERVAL=60

# Discord
DISCORD_BOT_TOKEN="..."
DISCORD_CHANNEL_ID="..."
```

## Usage

Run the bot using Poetry:

```bash
poetry run loom-bot
```

Or directly with Python:

```bash
# From the monorepo root
poetry run python -m loom-bot.src.bot

# Or from the loom-bot directory
cd loom-bot
poetry run python -m src.bot
```

## Discord Notifications

The bot sends notifications for:

- Bot initialization and startup
- Price updates
- Position creation and closure
- Errors and warnings
- Bot shutdown
