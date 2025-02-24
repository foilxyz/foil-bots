# Liquidity Loom Bot

## Prerequisites

1. Install Python 3.11 or higher

   ```bash
   # On macOS using homebrew:
   brew install python@3.11

   # On Ubuntu/Debian:
   sudo apt update
   sudo apt install python3.11 python3.11-venv
   ```

2. Install Poetry (Python dependency management)
   ```bash
   curl -sSL https://install.python-poetry.org | python3 -
   ```

## Setup

1. Clone the repository

   ```bash
   git clone https://github.com/yourusername/liquidity-loom.git
   cd liquidity-loom
   ```

2. Install dependencies

   ```bash
   poetry install
   ```

3. Create your environment file

   ```bash
   cp .env.example .env
   ```

4. Configure your `.env` file with your settings:

   ```env
   NETWORK_RPC_URL="https://sepolia.infura.io/v3/YOUR-API-KEY"
   FOIL_ADDRESS="0xe59c049a3424bafb05701fefeb16eaab823e507e"

   # Trading parameters
   RISK_SPREAD_SPACING_WIDTH=5
   LP_RANGE_WIDTH=20
   MIN_POSITION_SIZE=100000000000000000
   MAX_POSITION_SIZE=200000000000000000
   TRAILING_AVERAGE_DAYS=28

   # Your wallet's private key
   WALLET_PK="your-private-key-here"

   # FOIL API URL
   FOIL_API_URL="https://api.staging.foil.xyz"

   # Bot run interval in seconds
   BOT_RUN_INTERVAL=600
   ```

## Running the Bot

1. Activate the poetry shell

   ```bash
   poetry shell
   ```

2. Run the bot
   ```bash
   python -m src.bot
   ```

## Development

1. Install development dependencies

   ```bash
   poetry install --with dev
   ```

2. Run linting

   ```bash
   poetry run ruff check src/
   ```

3. Run formatter

   ```bash
   poetry run black src/
   ```

4. Run type checking
   ```bash
   poetry run mypy src/
   ```

## Troubleshooting

- If poetry command not found, add to PATH:

  ```bash
  export PATH="$HOME/.local/bin:$PATH"
  ```

- If you get SSL errors with poetry:

  ```bash
  export PYTHON_KEYRING_BACKEND=keyring.backends.null.Keyring
  ```

- For Windows users, use PowerShell and replace `export` with `$env:`
