# Fluxor Bot

A bot for automated trading on Foil prediction markets with multi-market support and AI-powered predictions.

## Features

- **Multi-Market Support**: Manages multiple markets across different market group addresses
- **Async Processing**: Concurrent execution of strategies across all configured markets
- **Liquidity Position Management**: Creates and manages liquidity positions on prediction markets
- **AI-Powered Predictions**: Uses OpenAI to analyze claim statements and predict market outcomes
- **Risk Management**: Configurable position sizing and spread parameters
- **Discord Integration**: Real-time notifications and alerts

## Configuration

The bot is configured through environment variables:

### Required Variables

```bash
# Network and wallet configuration
FLUXOR_BOT_RPC_URL=https://your-rpc-endpoint
FLUXOR_BOT_WALLET_PK=your_private_key

# Market configuration - JSON array of market groups
FLUXOR_BOT_MARKET_GROUPS='[{"marketGroupAddress": "0x123...", "marketIds": [1, 2, 3]}, {"marketGroupAddress": "0x456...", "marketIds": [1]}]'

# OpenAI API configuration (required for AI predictions)
FLUXOR_BOT_OPENAI_API_KEY=your_openai_api_key
```

### Optional Variables

```bash
# Bot behavior
FLUXOR_BOT_BOT_RUN_INTERVAL=600  # Seconds between runs (default: 600)
FLUXOR_BOT_POSITION_SIZE=1000    # Position size in tokens (default: 1000)

# Strategy parameters
FLUXOR_BOT_RISK_SPREAD_SPACING_WIDTH=0.1  # Risk spread width (default: 0.1)
FLUXOR_BOT_LP_RANGE_WIDTH=0.2             # LP range width (default: 0.2)

# Discord notifications (optional)
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_CHANNEL_ID=your_discord_channel_id
```

## AI Prediction System

The bot uses OpenAI's GPT models to analyze prediction market claim statements and estimate the likelihood of resolution. For each market, the bot will:

1. Extract the claim statement from the smart contract
2. Send it to OpenAI for analysis
3. Receive a percentage likelihood (0-100%) that the claim will resolve to 1
4. Log the prediction and store it for strategy use

Example log output:

```
📝 Claim Statement: The BLS nonfarm payrolls reading for May 2025 is less than 50,000: 0 if no.
🤖 AI Prediction: 15% likelihood of resolving to 1
```

## Market Group Configuration

The `FLUXOR_BOT_MARKET_GROUPS` environment variable expects a JSON array where each object contains:

- `marketGroupAddress`: The Ethereum address of the market group contract
- `marketIds`: Array of numeric market IDs to trade within that group

Example:

```json
[
  {
    "marketGroupAddress": "0x1234567890123456789012345678901234567890",
    "marketIds": [1, 2, 3, 4]
  },
  {
    "marketGroupAddress": "0x0987654321098765432109876543210987654321",
    "marketIds": [1]
  }
]
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

## Architecture

- **MarketManager**: Coordinates multiple market tasks and async execution
- **MarketTask**: Individual market trading logic and strategy execution
- **Foil**: Smart contract interaction and market data management
- **Position**: Liquidity position creation and management
- **Strategy**: Trading logic and decision making (placeholder implementation)
- **OpenAI Integration**: AI-powered claim statement analysis and predictions

## Strategy Development

The current strategy implementation is a placeholder. The `FluxorStrategy` class provides the framework for implementing custom trading strategies that can leverage:

- Market price data
- AI predictions (`foil.ai_prediction`)
- Position management capabilities
- Risk parameters from configuration

## Logging

The bot provides detailed logging for:

- Market initialization and connection status
- Claim statements and AI predictions
- Strategy execution and performance
- Error handling and debugging

## Discord Integration

When configured, the bot sends notifications for:

- Bot initialization and market setup
- Strategy execution summaries
- Errors and important events
- Performance metrics
