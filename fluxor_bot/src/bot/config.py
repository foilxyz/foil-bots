import json
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from web3 import Web3

from shared.config.config_manager import BaseConfig, ConfigManager


class MarketGroupConfig:
    """Configuration for a market group"""

    def __init__(self, market_group_address: str, market_ids: List[int]):
        self.market_group_address = Web3.to_checksum_address(market_group_address)
        self.market_ids = market_ids

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MarketGroupConfig":
        return cls(
            market_group_address=data["marketGroupAddress"],
            market_ids=[int(mid) for mid in data["marketIds"]],  # Convert to integers
        )

    def __repr__(self) -> str:
        return f"MarketGroupConfig(address={self.market_group_address}, market_ids={self.market_ids})"


@dataclass
class BotConfig(BaseConfig):
    """Configuration for the Fluxor Bot"""

    market_groups: List[MarketGroupConfig]
    rpc_url: str
    wallet_pk: str
    bot_run_interval: int
    position_size: float
    risk_spread_spacing_width: float
    lp_range_width: float
    openai_api_key: str
    discord_bot_token: Optional[str] = None
    discord_channel_id: Optional[str] = None

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

        # Load market groups from environment
        market_groups_json = ConfigManager.get_required_str("FLUXOR_BOT_MARKET_GROUPS")
        market_groups_data = json.loads(market_groups_json)
        market_groups = [MarketGroupConfig.from_dict(group) for group in market_groups_data]

        # OpenAI configuration
        openai_api_key = ConfigManager.get_required_str("FLUXOR_BOT_OPENAI_API_KEY")

        # Load other configuration
        rpc_url = ConfigManager.get_required_str("NETWORK_RPC_URL")
        wallet_pk = ConfigManager.get_required_str("FLUXOR_BOT_WALLET_PK")
        bot_run_interval = ConfigManager.get_int("FLUXOR_BOT_RUN_INTERVAL", 600)
        position_size = ConfigManager.get_float("FLUXOR_BOT_POSITION_SIZE", 1.0)
        risk_spread_spacing_width = ConfigManager.get_float("FLUXOR_BOT_RISK_SPREAD_SPACING_WIDTH", 0.1)
        lp_range_width = ConfigManager.get_float("FLUXOR_BOT_LP_RANGE_WIDTH", 0.2)

        # Discord configuration
        discord_bot_token = ConfigManager.get_optional_str("DISCORD_BOT_TOKEN")
        discord_channel_id = ConfigManager.get_optional_str("DISCORD_CHANNEL_ID")

        # Create and return the config
        return cls(
            market_groups=market_groups,
            rpc_url=rpc_url,
            wallet_pk=wallet_pk,
            bot_run_interval=bot_run_interval,
            position_size=position_size,
            risk_spread_spacing_width=risk_spread_spacing_width,
            lp_range_width=lp_range_width,
            openai_api_key=openai_api_key,
            discord_bot_token=discord_bot_token,
            discord_channel_id=discord_channel_id,
        )
