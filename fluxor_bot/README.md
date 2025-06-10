# FluxorBot 🤖

An autonomous liquidity provisioning bot for Foil prediction markets, powered by OpenAI and designed for forking and customization.

## 🚀 What FluxorBot Does

**FluxorBot automatically provides liquidity to ALL active prediction markets** by:

1. **🔍 Auto-Discovery**: Discovers all active markets via Foil API
2. **🧠 AI Analysis**: Analyzes each market question using OpenAI's GPT models
3. **💰 Smart Positioning**: Creates optimal liquidity positions based on AI predictions
4. **⚡ Auto-Rebalancing**: Continuously rebalances positions when AI predictions deviate
5. **📊 Quirky Reporting**: Generates nerdy social media posts about trading activity
6. **🐦 X Integration**: Automatically posts AI-generated summaries to X (Twitter)

## 🎯 Core Features

### Autonomous Market Making

- **Zero Manual Configuration**: Automatically finds and trades on all active Foil markets
- **AI-Driven Predictions**: Uses GPT-4o-mini to analyze market questions and predict outcomes
- **Dynamic Position Sizing**: Creates liquidity positions around AI prediction confidence levels
- **Smart Rebalancing**: Automatically adjusts positions when predictions change significantly

### Built for Developers

- **Fork-Friendly Architecture**: Clean, modular codebase designed for customization
- **Configurable Strategy**: Easy to modify trading logic and risk parameters
- **Comprehensive Logging**: Detailed logs for debugging and monitoring
- **Discord Integration**: Real-time notifications and quirky AI-generated summaries
- **X (Twitter) Integration**: Automatic posting of AI-generated trading summaries

## 🛠 Quick Start (Forking Guide)

### 1. Fork & Install

```bash
git clone https://github.com/yourusername/foil-bots
cd foil-bots/fluxor_bot
poetry install
```

### 2. Environment Configuration

Create a `.env` file in the project root:

```bash
# 🔑 Required - Wallet & Network
NETWORK_RPC_URL=https://mainnet.base.org
FLUXOR_BOT_WALLET_PK=your_private_key_here

# 🔗 Required - Foil API
FOIL_API_URL=https://api.foil.xyz/graphql
FLUXOR_BOT_CHAIN_ID=8453
FLUXOR_BOT_BASE_TOKEN_NAME=WETH

# 🧠 Required - OpenAI API
FLUXOR_BOT_OPENAI_API_KEY=sk-your-openai-key-here

# 💰 Trading Parameters
FLUXOR_BOT_COLLATERAL_SIZE=10.0           # USDC per position
FLUXOR_BOT_RISK_SPREAD_SPACING_WIDTH=0.1  # Position spread width
FLUXOR_BOT_LP_RANGE_WIDTH=10              # Liquidity range width
FLUXOR_BOT_REBALANCE_DEVIATION=5          # Rebalance threshold (tick spacings)

# 📢 Optional - Discord Notifications
DISCORD_BOT_TOKEN=your_discord_bot_token
DISCORD_CHANNEL_ID=your_discord_channel_id

# 🐦 Optional - X (Twitter) Integration
FLUXOR_BOT_X_API_KEY=your_x_api_key
FLUXOR_BOT_X_API_SECRET=your_x_api_secret
FLUXOR_BOT_X_ACCESS_TOKEN=your_x_access_token
FLUXOR_BOT_X_ACCESS_TOKEN_SECRET=your_x_access_token_secret
FLUXOR_BOT_X_BEARER_TOKEN=your_x_bearer_token
```

### 3. Run the Bot

```bash
# Single run
poetry run fluxor-bot

# Continuous (cron every 10 minutes)
*/10 * * * * cd /path/to/fluxor_bot && poetry run fluxor-bot >> bot.log 2>&1
```

## 🧠 How AI Predictions Work

FluxorBot sends market questions to OpenAI's GPT-4o-mini model with this workflow:

```python
# Example: Market question analysis
Question: "Will BTC reach $100,000 by end of 2024?"

# FluxorBot sends to OpenAI:
"Analyze this prediction market question and estimate the likelihood
(0-100%) that it will resolve to 'Yes/True/1'..."

# OpenAI Response:
"Based on current BTC trends and historical data: 25% likelihood"

# FluxorBot Action:
Creates liquidity positions with 25% confidence:
- Low position: Below 25% price range
- High position: Above 25% price range
```

## 🐦 X (Twitter) Integration

FluxorBot can automatically post AI-generated summaries to X after each trading run:

### X API Setup

1. **Create X Developer Account**: Visit [developer.x.com](https://developer.x.com)
2. **Create App**: Get API credentials for your bot account
3. **Configure Environment**: Add X API credentials to your `.env` file
4. **Enable Integration**: FluxorBot will automatically detect and use X credentials

### What Gets Posted

**Daily Comprehensive Reports** (since bot runs once per day):

- **Detailed Market Analysis**: Specific prediction questions analyzed with AI confidence levels
- **Strategy Explanation**: How liquidity is positioned AROUND predictions, not at them
- **Performance Metrics**: Markets analyzed, positions created/rebalanced, execution time
- **Market Insights**: Analysis of prediction confidence changes and market movements
- **Fluxor Personality**: Statistical humor, nerdy analytics, sigma symbols

### Example X Posts

**Single Tweet** (if content fits):

```
🤖 DAILY FLUXOR REPORT 📊 Analyzed 8 prediction markets including "BTC $100k by 2025?" (35% confidence). Deployed LP positions AROUND predictions to capture volatility. Smart positioning = alpha generation σ
```

**Tweet Thread** (for detailed daily reports):

```
🤖 DAILY FLUXOR REPORT 📊 (1/3)

High-Frequency Liquidity Oracle analyzed 12 prediction markets today. Key highlights: "Will BTC reach $100k?" - 35% AI confidence, "Trump 2024 election?" - 78% confidence.

(2/3) Strategy: Deployed 8 new LP positions AROUND these predictions (not AT them). Created liquidity bands above & below confidence levels to capture volatility and earn fees while providing market efficiency.

(3/3) Performance: 12 markets analyzed in 15.2s, 4 rebalanced based on AI updates. Crunching p-values like it's 2025! Volatility's my playground σ
```

## ⚖️ Auto-Rebalancing Logic

The bot continuously monitors AI prediction changes and rebalances when deviation exceeds threshold:

```python
# Rebalancing trigger example:
Original AI Prediction: 25% → New AI Prediction: 65%
Position Deviation: > 5 tick spacings from optimal range
Action: Close all positions → Create new positions around 65% confidence
```

## 🏗 Architecture (For Developers)

### Core Components

```
├── 🎯 strategy.py          # Main trading logic - CUSTOMIZE HERE
├── 🤖 llm_post_generator.py # OpenAI integration for social posts
├── 📊 position_manager.py   # Position creation/closing logic
├── 🌐 market_manager.py     # Market discovery and coordination
├── 📡 foil.py              # Smart contract interactions
└── ⚙️ config.py            # Configuration management
```

### Key Extension Points

**1. Custom Trading Strategy** (`strategy.py`):

```python
async def _create_positions(self, prediction_percentage: float):
    # 🎯 CUSTOMIZE: Your position creation logic here
    # Current: Creates positions around AI prediction
    # Fork ideas: Add technical analysis, sentiment, volume data
```

**2. AI Prediction Enhancement** (`llm_post_generator.py`):

```python
async def generate_summary_post(self, run_data):
    # 🧠 CUSTOMIZE: Your AI prompt engineering here
    # Current: Generates quirky trading summaries
    # Fork ideas: Add market analysis, performance metrics
```

**3. Position Management** (`position_manager.py`):

```python
async def close_position(self, position_data, foil_contract, market_id):
    # ⚖️ CUSTOMIZE: Your position management logic
    # Current: Simple close-all strategy
    # Fork ideas: Partial closes, profit-taking, stop-losses
```

## 📊 Monitoring & Debugging

### Log Analysis

```bash
# Real-time monitoring
tail -f bot.log | grep "FLUXOR LLM CONTEXT"

# Filter AI predictions
grep "AI Prediction:" bot.log

# Position creation tracking
grep "Position created successfully" bot.log
```

### Performance Metrics

The bot tracks and logs:

- ✅ Successful position creations per market
- ❌ Failed transactions and reasons
- 🔄 Rebalancing frequency and triggers
- 💰 Total collateral deployed
- 🧠 AI prediction accuracy over time

## 🚀 Deployment Options

### Local Development

```bash
poetry run fluxor-bot  # Single run for testing
```

### Production Cron

```bash
# /etc/crontab - Run every 10 minutes
*/10 * * * * cd /opt/fluxor_bot && poetry run fluxor-bot >> /var/log/fluxor.log 2>&1
```

### Cloud Deployment (Render/Railway)

```bash
# Build command
poetry install

# Start command
poetry run fluxor-bot

# Add environment variables via platform dashboard
```

### 1. Different AI Models

```python
# In llm_post_generator.py
response = self.client.chat.completions.create(
    model="gpt-4-turbo",  # Upgrade for better analysis
    # or "claude-3-opus" with Anthropic client
)
```
