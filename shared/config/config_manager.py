import os
from typing import Any, ClassVar, Dict, Optional, Type, TypeVar

from dotenv import find_dotenv, load_dotenv
from web3 import Web3

T = TypeVar("T", bound="BaseConfig")


class BaseConfig:
    """Base configuration class for all bots in the monorepo"""

    # Class variable for singleton instance
    _instance: ClassVar[Optional["BaseConfig"]] = None

    @classmethod
    def get_config(cls: Type[T]) -> T:
        """Get or create singleton config instance"""
        if cls._instance is None:
            cls._instance = cls.from_env()
        return cls._instance

    @classmethod
    def from_env(cls: Type[T]) -> T:
        """Load configuration from environment variables.
        To be implemented by subclasses."""
        raise NotImplementedError("Subclasses must implement from_env")


class ConfigManager:
    """Utility for loading and validating config values from environment"""

    @staticmethod
    def load_env(env_path: Optional[str] = None) -> None:
        """Load environment variables from .env file"""
        # If no specific path is provided, check for a local .env file
        if not env_path and os.path.exists(".env"):
            env_path = ".env"

        load_dotenv(env_path or find_dotenv(), override=True)

    @staticmethod
    def get_required_str(key: str, error_msg: Optional[str] = None) -> str:
        """Get a required string environment variable"""
        value = os.getenv(key)
        if not value:
            raise ValueError(error_msg or f"Missing required environment variable: {key}")
        return value

    @staticmethod
    def get_optional_str(key: str, default: str = "") -> str:
        """Get an optional string environment variable with default"""
        return os.getenv(key, default)

    @staticmethod
    def get_int(key: str, default: int) -> int:
        """Get an integer environment variable with default"""
        value = os.getenv(key)
        return int(value) if value else default

    @staticmethod
    def get_float(key: str, default: float) -> float:
        """Get a float environment variable with default"""
        value = os.getenv(key)
        return float(value) if value else default

    @staticmethod
    def get_bool(key: str, default: bool = False) -> bool:
        """Get a boolean environment variable with default"""
        value = os.getenv(key, "").lower()
        if not value:
            return default
        return value in ("1", "true", "yes", "on", "y")

    @staticmethod
    def get_checksum_address(key: str) -> str:
        """Get an Ethereum address and convert to checksum format"""
        address = ConfigManager.get_required_str(key)
        return Web3.to_checksum_address(address)

    @staticmethod
    def validate_required(values: Dict[str, Any]) -> None:
        """Validate that all required values are present"""
        missing = [key for key, value in values.items() if value is None]
        if missing:
            raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
