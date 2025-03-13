from dataclasses import dataclass
from typing import Optional

from web3 import Web3

from shared.config.config_manager import BaseConfig, ConfigManager


@dataclass
class BotConfig(BaseConfig):
    """Bot configuration loaded from environment variables"""

    rpc_url: str
    foil_api_url: str
    wallet_pk: str
    foil_address: str
    risk_spread_spacing_width: int
    lp_range_width: int
    min_position_size: float
    max_position_size: float
    trailing_average_days: int
    bot_run_interval: int
    discord_bot_token: Optional[str] = None
    discord_channel_id: Optional[str] = None

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Load configuration from environment variables"""
        # Load environment variables
        ConfigManager.load_env()

        # Required environment variables
        rpc_url = ConfigManager.get_required_str("NETWORK_RPC_URL")
        foil_api_url = ConfigManager.get_required_str("FOIL_API_URL")
        wallet_pk = ConfigManager.get_required_str("WALLET_PK")
        foil_address = ConfigManager.get_checksum_address("FOIL_ADDRESS")

        # Trading parameters
        risk_spread_spacing_width = ConfigManager.get_int("RISK_SPREAD_SPACING_WIDTH", 10)
        lp_range_width = ConfigManager.get_int("LP_RANGE_WIDTH", 20)
        min_position_size = ConfigManager.get_float("MIN_POSITION_SIZE", 0.1)
        max_position_size = ConfigManager.get_float("MAX_POSITION_SIZE", 10.0)
        trailing_average_days = ConfigManager.get_int("TRAILING_AVERAGE_DAYS", 28)
        bot_run_interval = ConfigManager.get_int("BOT_RUN_INTERVAL", 600)

        # Discord configuration
        discord_bot_token = ConfigManager.get_optional_str("DISCORD_BOT_TOKEN")
        discord_channel_id = ConfigManager.get_optional_str("DISCORD_CHANNEL_ID")

        # Create and return the config
        return cls(
            rpc_url=rpc_url,
            foil_api_url=foil_api_url,
            wallet_pk=wallet_pk,
            foil_address=foil_address,
            risk_spread_spacing_width=risk_spread_spacing_width,
            lp_range_width=lp_range_width,
            min_position_size=min_position_size,
            max_position_size=max_position_size,
            trailing_average_days=trailing_average_days,
            bot_run_interval=bot_run_interval,
            discord_bot_token=discord_bot_token,
            discord_channel_id=discord_channel_id,
        )
