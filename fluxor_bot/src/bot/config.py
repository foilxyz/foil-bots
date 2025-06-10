import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from web3 import Web3

from shared.config.config_manager import BaseConfig, ConfigManager


@dataclass
class BotConfig(BaseConfig):
    """Configuration for the Fluxor Bot"""

    # API configuration
    foil_api_url: str
    chain_id: int
    base_token_name: str

    # Network and wallet
    rpc_url: str
    wallet_pk: str

    # Bot parameters
    collateral_size: float
    risk_spread_spacing_width: float
    lp_range_width: float
    rebalance_deviation: float
    openai_api_key: str

    # Discord configuration
    discord_bot_token: Optional[str] = None
    discord_channel_id: Optional[str] = None

    # X (Twitter) configuration
    x_api_key: Optional[str] = None
    x_api_secret: Optional[str] = None
    x_access_token: Optional[str] = None
    x_access_token_secret: Optional[str] = None
    x_bearer_token: Optional[str] = None

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Load configuration from environment variables"""
        # Load environment from top-level .env file
        from pathlib import Path

        # Get the absolute path to the top-level .env file
        current_file = Path(__file__)  # This file is in fluxor_bot/src/bot/config.py
        project_root = current_file.parent.parent.parent.parent  # Go up to foil-bots/
        env_file = project_root / ".env"

        if env_file.exists():
            ConfigManager.load_env(str(env_file))
        else:
            # Fallback to default behavior if .env not found
            ConfigManager.load_env()

        # API configuration
        foil_api_url = ConfigManager.get_required_str("FOIL_API_URL")
        chain_id = ConfigManager.get_int("FLUXOR_BOT_CHAIN_ID", 8453)
        base_token_name = ConfigManager.get_required_str("FLUXOR_BOT_BASE_TOKEN_NAME")

        # OpenAI configuration
        openai_api_key = ConfigManager.get_required_str("FLUXOR_BOT_OPENAI_API_KEY")

        # Load other configuration
        rpc_url = ConfigManager.get_required_str("NETWORK_RPC_URL")
        wallet_pk = ConfigManager.get_required_str("FLUXOR_BOT_WALLET_PK")
        collateral_size = ConfigManager.get_float("FLUXOR_BOT_COLLATERAL_SIZE", 1.0)
        risk_spread_spacing_width = ConfigManager.get_float("FLUXOR_BOT_RISK_SPREAD_SPACING_WIDTH", 0.1)
        lp_range_width = ConfigManager.get_float("FLUXOR_BOT_LP_RANGE_WIDTH", 0.2)
        rebalance_deviation = ConfigManager.get_float("FLUXOR_BOT_REBALANCE_DEVIATION", 5)

        # Discord configuration
        discord_bot_token = ConfigManager.get_optional_str("DISCORD_BOT_TOKEN")
        discord_channel_id = ConfigManager.get_optional_str("DISCORD_CHANNEL_ID")

        # X (Twitter) configuration
        x_api_key = ConfigManager.get_optional_str("FLUXOR_BOT_X_API_KEY")
        x_api_secret = ConfigManager.get_optional_str("FLUXOR_BOT_X_API_SECRET")
        x_access_token = ConfigManager.get_optional_str("FLUXOR_BOT_X_ACCESS_TOKEN")
        x_access_token_secret = ConfigManager.get_optional_str("FLUXOR_BOT_X_ACCESS_TOKEN_SECRET")
        x_bearer_token = ConfigManager.get_optional_str("FLUXOR_BOT_X_BEARER_TOKEN")

        # Create and return the config
        return cls(
            foil_api_url=foil_api_url,
            chain_id=chain_id,
            base_token_name=base_token_name,
            rpc_url=rpc_url,
            wallet_pk=wallet_pk,
            collateral_size=collateral_size,
            risk_spread_spacing_width=risk_spread_spacing_width,
            lp_range_width=lp_range_width,
            rebalance_deviation=rebalance_deviation,
            openai_api_key=openai_api_key,
            discord_bot_token=discord_bot_token,
            discord_channel_id=discord_channel_id,
            x_api_key=x_api_key,
            x_api_secret=x_api_secret,
            x_access_token=x_access_token,
            x_access_token_secret=x_access_token_secret,
            x_bearer_token=x_bearer_token,
        )
