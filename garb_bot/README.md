# Arbitrage Bot

A bot for automated arbitrage across different markets.

## Overview

This bot analyzes price differences between various markets and executes trades to capitalize on arbitrage opportunities.

## Setup

1. Clone the repository
2. Install dependencies with Poetry:
   ```bash
   cd arbitrage-bot
   poetry install
   ```
3. Copy `.env.example` to `.env` and update the values

## Usage

Run the bot using Poetry:

```bash
poetry run arbitrage-bot
```

Or directly with Python:

```bash
poetry run python -m src.bot
```

## Configuration

Edit the `.env` file to configure the bot's behavior:

- `DISCORD_WEBHOOK_URL`: Webhook URL for Discord notifications
- `PRIVATE_KEY`: Private key for the bot's wallet
- `RPC_URL`: RPC URL for blockchain connection
- Other configuration options
