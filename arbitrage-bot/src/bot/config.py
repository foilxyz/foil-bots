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

    # Trading parameters
    min_profit_threshold: float  # Minimum profit to execute a trade (in token units)
    gas_price_multiplier: float  # Multiplier for gas price estimation (buffer)
    max_slippage: float  # Maximum allowed slippage percentage
    max_position_size: float  # Maximum position size in ETH
    trade_interval: int  # Time between trades in seconds

    # Foil contract address
    foil_address: str  # Address of the Foil contract

    # Discord configuration
    discord_bot_token: Optional[str] = None
    discord_channel_id: Optional[str] = None

    @classmethod
    def from_env(cls) -> "ArbitrageConfig":
        """Load configuration from environment variables"""
        # Load environment variables
        ConfigManager.load_env()

        # Network and wallet
        rpc_url = ConfigManager.get_required_str("NETWORK_RPC_URL")
        wallet_pk = ConfigManager.get_required_str("WALLET_PK")

        # Trading parameters
        min_profit_threshold = ConfigManager.get_float("MIN_PROFIT_THRESHOLD", 0.01)
        gas_price_multiplier = ConfigManager.get_float("GAS_PRICE_MULTIPLIER", 1.2)
        max_slippage = ConfigManager.get_float("MAX_SLIPPAGE", 0.5)  # 0.5%
        max_position_size = ConfigManager.get_float("MAX_POSITION_SIZE", 1.0)  # 1 ETH
        trade_interval = ConfigManager.get_int("TRADE_INTERVAL", 60)  # 60 seconds

        # Foil contract address
        foil_address = Web3.to_checksum_address(ConfigManager.get_required_str("FOIL_ADDRESS"))

        # Discord configuration
        discord_bot_token = ConfigManager.get_optional_str("DISCORD_BOT_TOKEN")
        discord_channel_id = ConfigManager.get_optional_str("DISCORD_CHANNEL_ID")

        # Create and return config
        return cls(
            rpc_url=rpc_url,
            wallet_pk=wallet_pk,
            min_profit_threshold=min_profit_threshold,
            gas_price_multiplier=gas_price_multiplier,
            max_slippage=max_slippage,
            max_position_size=max_position_size,
            trade_interval=trade_interval,
            foil_address=foil_address,
            discord_bot_token=discord_bot_token,
            discord_channel_id=discord_channel_id,
        )

    @classmethod
    def get_config(cls) -> "ArbitrageConfig":
        """Get a singleton instance of the config"""
        if not hasattr(cls, "_instance"):
            cls._instance = cls.from_env()
        return cls._instance
