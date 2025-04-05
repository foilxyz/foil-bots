from dataclasses import dataclass
from typing import Optional

from web3 import Web3

from shared.config.config_manager import BaseConfig, ConfigManager


@dataclass
class ArbitrageConfig(BaseConfig):
    """
    Configuration for the Arbitrage Bot
    """

    # Network and wallet
    rpc_url: str
    wallet_pk: str
    foil_api_url: str  # API URL for Foil

    # Trading parameters
    price_difference_ratio: float  # Price difference ratio
    min_collateral: int  # Minimum collateral
    max_collateral: int  # Maximum collateral
    trade_interval: int  # Trading interval in seconds

    # Foil contract address
    foil_address: str  # Address of the Foil contract
    epoch_id: int  # Epoch ID

    # Discord configuration
    discord_bot_token: Optional[str] = None
    discord_channel_id: Optional[str] = None

    execute_arbitrage: bool = False

    @classmethod
    def from_env(cls) -> "ArbitrageConfig":
        """Load configuration from environment variables"""
        # Load environment variables
        ConfigManager.load_env()

        # Network and wallet
        rpc_url = ConfigManager.get_required_str("GARB_BOT_NETWORK_RPC_URL")
        wallet_pk = ConfigManager.get_required_str("GARB_BOT_WALLET_PK")
        foil_api_url = ConfigManager.get_required_str("GARB_BOT_FOIL_API_URL")

        # Foil contract address
        foil_address = ConfigManager.get_checksum_address("GARB_BOT_FOIL_ADDRESS")
        epoch_id = ConfigManager.get_int("GARB_BOT_EPOCH_ID", 1)
        # Trading parameters
        price_difference_ratio = ConfigManager.get_float("GARB_BOT_PRICE_DIFFERENCE_RATIO", 0.2)
        min_collateral = ConfigManager.get_int("GARB_BOT_MIN_COLLATERAL", 100000000000000000)  # 0.1 ETH default
        max_collateral = ConfigManager.get_int("GARB_BOT_MAX_COLLATERAL", 1000000000000000000)  # 1 ETH default
        trade_interval = ConfigManager.get_int("GARB_BOT_BOT_RUN_INTERVAL", 300)  # Default to 5 minutes

        # Discord configuration
        discord_bot_token = ConfigManager.get_optional_str("GARB_BOT_DISCORD_BOT_TOKEN")
        discord_channel_id = ConfigManager.get_optional_str("GARB_BOT_DISCORD_CHANNEL_ID")

        execute_arbitrage = ConfigManager.get_bool("GARB_BOT_EXECUTE_ARBITRAGE", False)

        # Create and return config
        return cls(
            rpc_url=rpc_url,
            wallet_pk=wallet_pk,
            foil_api_url=foil_api_url,
            price_difference_ratio=price_difference_ratio,
            min_collateral=min_collateral,
            max_collateral=max_collateral,
            trade_interval=trade_interval,
            foil_address=foil_address,
            epoch_id=epoch_id,
            discord_bot_token=discord_bot_token,
            discord_channel_id=discord_channel_id,
            execute_arbitrage=execute_arbitrage,
        )
