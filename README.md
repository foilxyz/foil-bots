# Loom Bot

A Web3 bot for automated market making on the FOIL protocol, built with Python.

## Features

- Automated position management for FOIL protocol
- Real-time price monitoring and position optimization
- Discord notifications for important events and errors
- Configurable trading parameters
- Support for both LP and trader positions (trader: coming soon)

## Prerequisites

- Python 3.8 or higher
- Web3.py
- Discord.py
- Access to an Ethereum node (e.g., Infura)
- Discord bot token and channel ID

## Installation

1. Clone the repository:

```bash
git clone <repository-url>
cd loom-bot
```

2. Install dependencies:

```bash
pip install -r requirements.txt
```

3. Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

4. Configure your environment variables in `.env`:

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

## Discord Bot Setup

1. Create a new Discord application at [Discord Developer Portal](https://discord.com/developers/applications)
2. Create a bot for your application
3. Enable the "Message Content Intent" in the Bot section
4. Copy the bot token and add it to your `.env` file
5. Invite the bot to your server with proper permissions:
   - Send Messages
   - Read Message History
6. Get your channel ID (right-click channel → Copy ID) and add it to your `.env` file

## Usage

Run the bot:

```bash
python -m src.bot
```

The bot will:

- Connect to the FOIL protocol
- Monitor market prices
- Manage positions based on configured strategy
- Send notifications to Discord for important events

## Discord Notifications

The bot sends notifications for:

- Bot initialization and startup
- Price updates
- Position creation and closure
- Errors and warnings
- Bot shutdown

## Configuration

Key configuration parameters in `.env`:

- `NETWORK_RPC_URL`: Your Ethereum node URL
- `FOIL_ADDRESS`: FOIL contract address
- `WALLET_PK`: Your wallet's private key
- `RISK_SPREAD_SPACING_WIDTH`: Width of risk spread spacing
- `LP_RANGE_WIDTH`: Width of LP range
- `MIN_POSITION_SIZE`: Minimum position size in wei
- `MAX_POSITION_SIZE`: Maximum position size in wei
- `TRAILING_AVERAGE_DAYS`: Number of days for trailing average
- `BOT_RUN_INTERVAL`: Bot execution interval in seconds
- `DISCORD_BOT_TOKEN`: Your Discord bot token
- `DISCORD_CHANNEL_ID`: Target Discord channel ID

## Error Handling

The bot includes comprehensive error handling:

- Transaction simulation before execution
- Position transition checks
- Network connection monitoring
- Discord notifications for errors

## Security

- Never share your private key or bot token
- Keep your `.env` file secure and never commit it to version control
- Use environment variables for sensitive data
- Consider using a dedicated wallet for the bot

## Contributing

1. Fork the repository
2. Create your feature branch
3. Commit your changes
4. Push to the branch
5. Create a new Pull Request

## License

MIT

## Disclaimer

This bot is for educational purposes only. Use at your own risk. The authors are not responsible for any financial losses incurred through the use of this bot.
