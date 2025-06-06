# Fluxor Bot

A bot for automated trading on Foil prediction markets with AI-powered predictions and dynamic market discovery via API.

## Features

- **Dynamic Market Discovery**: Automatically discovers and manages markets via the Foil API
- **Async Processing**: Concurrent execution of strategies across all discovered markets
- **Liquidity Position Management**: Creates and manages liquidity positions on prediction markets
- **AI-Powered Predictions**: Uses OpenAI to analyze market questions and predict outcomes
- **Risk Management**: Configurable position sizing and spread parameters
- **Discord Integration**: Real-time notifications and alerts
- **Cron-Friendly**: Designed to run as scheduled jobs rather than continuously

## Configuration

The bot is configured through environment variables:

### Required Variables

```bash
# Network and wallet configuration
NETWORK_RPC_URL=https://your-rpc-endpoint
FLUXOR_BOT_WALLET_PK=your_private_key

# API configuration
FLUXOR_BOT_FOIL_API_URL=https://api.foil.com
FLUXOR_BOT_COLLATERAL_ASSET=USDC
FLUXOR_BOT_CHAIN_ID=1
FLUXOR_BOT_BASE_TOKEN_NAME=ETH

# OpenAI API configuration (required for AI predictions)
FLUXOR_BOT_OPENAI_API_KEY=your_openai_api_key
```

### Optional Variables

```bash
# Bot behavior
FLUXOR_BOT_POSITION_SIZE=1.0    # Position size in tokens (default: 1.0)

# Strategy parameters
FLUXOR_BOT_RISK_SPREAD_SPACING_WIDTH=0.1  # Risk spread width (default: 0.1)
FLUXOR_BOT_LP_RANGE_WIDTH=0.2             # LP range width (default: 0.2)

# Discord notifications (optional)
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_CHANNEL_ID=your_discord_channel_id
```

## Dynamic Market Discovery

The bot now automatically discovers markets through the Foil API instead of requiring manual configuration. It fetches:

- Market groups based on collateral asset, chain ID, and base token
- All active markets within those groups (markets ending in the future)
- Market parameters including Uniswap position manager addresses
- Market questions and price tick ranges

This eliminates the need for manual market configuration and ensures the bot always works with current, active markets.

## AI Prediction System

The bot uses OpenAI's GPT models to analyze prediction market questions and estimate the likelihood of resolution. For each market, the bot will:

1. Extract the market question from the API response
2. Send it to OpenAI for analysis
3. Receive a percentage likelihood (0-100%) that the market will resolve to 1
4. Log the prediction and store it for strategy use

Example log output:

```
📝 Market Question: Will BTC reach $100,000 by end of 2024?
🤖 AI Prediction: 25% likelihood of resolving to 1
```

## Installation and Usage

1. **Install dependencies**:

   ```bash
   poetry install
   ```

2. **Set environment variables** (see Configuration section above)

3. **Run the bot**:
   ```bash
   poetry run fluxor-bot
   ```

### Cron Configuration

The bot is designed to run as scheduled cron jobs. Here's an example cron configuration to run the bot every 10 minutes:

```bash
# Run Fluxor Bot every 10 minutes
*/10 * * * * cd /path/to/fluxor-bot && poetry run fluxor-bot >> /var/log/fluxor-bot.log 2>&1
```

For deployment on platforms like Render, you can configure the `fluxor-bot` command as a cron job in your deployment settings.

## Architecture

- **MarketManager**: Coordinates API calls and manages multiple market tasks with async execution
- **MarketTask**: Individual market trading logic and strategy execution
- **Foil**: Smart contract interaction and market data management (now uses API data)
- **Position**: Liquidity position creation and management
- **Strategy**: Trading logic and decision making
- **AsyncFoilAPIClient**: GraphQL API client for fetching market data
- **OpenAI Integration**: AI-powered market question analysis and predictions

## Strategy Development

The bot includes a placeholder strategy implementation that can be customized for your trading logic. The strategy receives:

- Market data from the API (questions, price ranges, end times)
- AI predictions for market outcomes
- Current positions and liquidity data
- Contract interfaces for executing trades

## Migration from Environment Configuration

**Breaking Change**: The bot no longer uses the `FLUXOR_BOT_MARKET_GROUPS` environment variable. Instead, it dynamically discovers markets via the API using the new configuration parameters. This provides:

- Automatic discovery of new markets
- No need to manually update market configurations
- Always trading on current, active markets
- Simplified deployment and maintenance

## Logging

The bot provides detailed logging for:

- Market initialization and connection status
- Market questions and AI predictions
- Strategy execution and performance
- Error handling and debugging

## Discord Integration

When configured, the bot sends notifications for:

- Bot initialization and market setup
- Strategy execution summaries
- Errors and important events
- Performance metrics
