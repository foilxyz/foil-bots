import os
from pathlib import Path
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
    def reload_config(cls: Type[T]) -> T:
        """Force reload the configuration from environment"""
        cls._instance = None
        return cls.get_config()

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
        if env_path:
            # If a specific path is provided, use it
            load_dotenv(env_path, override=True)
            return

        # Get the caller's module path
        import inspect

        caller_frame = inspect.stack()[1]
        caller_module = inspect.getmodule(caller_frame[0])
        if caller_module:
            module_path = Path(caller_module.__file__)

            # Extract the package name from the module path
            # Module path will be like ".../foil-bots/loom_bot/src/bot/config.py"
            # We want to find "loom_bot" or "garb_bot"
            parts = module_path.parts
            for i, part in enumerate(parts):
                if part in ["loom_bot", "garb_bot"]:
                    package_root = Path(*parts[: i + 1])
                    env_file = package_root / ".env"
                    if env_file.exists():
                        load_dotenv(str(env_file), override=True)
                        return

        # Fallback to finding any .env file in the project
        load_dotenv(find_dotenv(), override=True)

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
