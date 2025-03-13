"""
Foil contract interaction module (async version)
"""

import logging
from typing import TypedDict

from web3 import Web3
from web3.contract import Contract

from shared.abis import POSITION_MANAGER_ABI, abi_loader
from shared.clients.discord_client import DiscordNotifier

from .config import ArbitrageConfig


class Epoch(TypedDict):
    epoch_id: int
    end_time: int
    base_asset_min_tick: int
    base_asset_max_tick: int


class Market(TypedDict):
    uniswap_position_manager: Contract
    collateral_token: Contract
    tick_spacing: int


class Foil:
    def __init__(self, w3: Web3):
        self.w3 = w3
        self.logger = logging.getLogger("ArbitrageBot")

        foil_address = ArbitrageConfig.get_config().foil_address
        self.contract = w3.eth.contract(address=foil_address, abi=abi_loader.get_abi("foil"))
        self.logger.info(f"Loaded foil contract at {foil_address}")

        # Synchronously initialize market and epoch (this only happens once on startup)
        # In a fully async codebase, this would be awaitable, but it's acceptable to do once at startup
        self._hydrate_market_and_epoch()

        # Initialize Discord notifier
        self.discord = DiscordNotifier.get_instance("ArbitrageBot", ArbitrageConfig.get_config())
        self.discord.send_message(
            f"🧠 **Foil Market Connected**\n- Contract: {foil_address}\n- Epoch ID: {self.epoch['epoch_id']}"
        )

    async def is_live(self) -> bool:
        """Check if the epoch is still live"""
        current_time = (await self.w3.eth.get_block("latest"))["timestamp"]
        return current_time < self.epoch["end_time"]

    def _hydrate_market_and_epoch(self):
        """Get the current epoch - synchronous since it's only called once at init"""
        (
            (epoch_id, _, end_time, _, _, _, _, _, base_asset_min_tick, base_asset_max_tick, *_),
            (_, _, _, _, uniswap_position_manager, *_),
        ) = self.contract.functions.getLatestEpoch().call()

        (_, collateral_token, *_) = self.contract.functions.getMarket().call()
        tick_spacing = self.contract.functions.getMarketTickSpacing().call()

        position_manager = self.w3.eth.contract(address=uniswap_position_manager, abi=POSITION_MANAGER_ABI)
        collateral_asset = self.w3.eth.contract(address=collateral_token, abi=abi_loader.get_abi("erc20"))

        self.epoch = Epoch(
            epoch_id=epoch_id,
            end_time=end_time,
            base_asset_min_tick=base_asset_min_tick,
            base_asset_max_tick=base_asset_max_tick,
        )
        self.market_params: Market = {
            "uniswap_position_manager": position_manager,
            "collateral_asset": collateral_asset,
            "tick_spacing": tick_spacing,
        }

    async def get_current_price_d18(self) -> int:
        """Get the current price asynchronously"""
        price = await self.contract.functions.getReferencePrice(self.epoch["epoch_id"]).call()
        return price

    async def get_current_pool_price(self) -> int:
        """Get the current price in sqrtPriceX96 asynchronously"""
        pool_price = await self.contract.functions.getSqrtPriceX96(self.epoch["epoch_id"]).call()
        return pool_price
