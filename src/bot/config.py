import os
from dataclasses import dataclass
from typing import ClassVar, Optional

from dotenv import find_dotenv, load_dotenv
from web3 import Web3


@dataclass
class BotConfig:
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

    # Class variable for singleton instance
    _instance: ClassVar[Optional["BotConfig"]] = None

    @classmethod
    def get_config(cls) -> "BotConfig":
        """Get or create singleton config instance"""
        if cls._instance is None:
            cls._instance = cls.from_env()
        return cls._instance

    @classmethod
    def from_env(cls) -> "BotConfig":
        """Load configuration from environment variables"""
        # Force reload of .env file
        load_dotenv(find_dotenv(), override=True)

        # Required environment variables
        rpc_url = os.getenv("NETWORK_RPC_URL")
        foil_api_url = os.getenv("FOIL_API_URL")
        wallet_pk = os.getenv("WALLET_PK")
        foil_address = os.getenv("FOIL_ADDRESS")

        # Trading parameters
        risk_spread_spacing_width = int(os.getenv("RISK_SPREAD_SPACING_WIDTH", "10"))
        lp_range_width = int(os.getenv("LP_RANGE_WIDTH", "20"))
        min_position_size = float(os.getenv("MIN_POSITION_SIZE", "0.1"))
        max_position_size = float(os.getenv("MAX_POSITION_SIZE", "10"))
        trailing_average_days = int(os.getenv("TRAILING_AVERAGE_DAYS", "28"))
        bot_run_interval = int(os.getenv("BOT_RUN_INTERVAL", "600"))

        # Validate required variables
        if not all([rpc_url, foil_api_url, wallet_pk, foil_address]):
            missing = [
                name
                for name, value in {
                    "NETWORK_RPC_URL": rpc_url,
                    "FOIL_API_URL": foil_api_url,
                    "WALLET_PK": wallet_pk,
                    "FOIL_ADDRESS": foil_address,
                    "RISK_SPREAD_SPACING_WIDTH": risk_spread_spacing_width,
                    "LP_RANGE_WIDTH": lp_range_width,
                    "MIN_POSITION_SIZE": min_position_size,
                    "MAX_POSITION_SIZE": max_position_size,
                    "TRAILING_AVERAGE_DAYS": trailing_average_days,
                    "BOT_RUN_INTERVAL": bot_run_interval,
                }.items()
                if not value
            ]
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

        # Convert address to checksum format
        foil_address = Web3.to_checksum_address(foil_address)

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
        )
