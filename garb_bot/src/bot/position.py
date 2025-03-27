"""
Position management module
"""

import logging
from typing import TypedDict

from web3 import Web3

from shared.clients.discord_client import DiscordNotifier
from shared.utils.async_web3_utils import send_async_transaction

from .config import ArbitrageConfig
from .foil import Foil


class CurrentPosition(TypedDict):
    kind: int
    collateral_amount: int


class Position:
    def __init__(self, account_address: str, foil: Foil, w3: Web3):
        self.logger = logging.getLogger("ArbitrageBot")
        self.account_address = account_address
        self.w3 = w3
        self.pk = ArbitrageConfig.get_config().wallet_pk
        self.foil = foil

        # Initialize Discord notifier
        self.discord = DiscordNotifier.get_instance("ArbitrageBot", ArbitrageConfig.get_config())

        # Position state will be initialized when hydrated
        self.current = None
        self.position_id = None

    async def initialize(self):
        """Asynchronously initialize the position"""
        await self.hydrate_current_position()
        return self

    async def hydrate_current_position(self):
        """Get the current position details asynchronously"""
        # Get position count
        position_count = await self.foil.contract.functions.balanceOf(self.account_address).call()

        if position_count == 0:
            self.logger.info("No positions found")
            self.current = {
                "kind": 0,
                "collateral_amount": 0,
            }
            return

        # Get latest position
        self.position_id = await self.foil.contract.functions.tokenOfOwnerByIndex(
            self.account_address, position_count - 1
        ).call()

        # Get position details
        position_data = await self.foil.contract.functions.getPosition(self.position_id).call()
        (_, kind, _, collateral_amount, _, _, _, _, _, _) = position_data

        self.logger.info(
            f"""
                ----------------------
                | Position Details   |
                ----------------------
                ID:                {self.position_id}
                Kind:              {kind}
                Collateral Amount: {collateral_amount}"""
        )

        self.current = {
            "kind": kind,
            "collateral_amount": collateral_amount,
        }

    def has_current_position(self) -> bool:
        """Check if there is a current position"""
        if self.current is None:
            return False
        return self.current["kind"] != 0 and self.current["collateral_amount"] != 0

    async def close_current_position(self):
        """Close current position if any"""
        if not self.has_current_position():
            self.logger.info("No position to close")
            return

        try:
            # Handle trader position
            if self.current["kind"] == 2:
                self.logger.info("Closing Trader Position")
                await self.close_trader_position()
                await self.hydrate_current_position()

            # Final verification
            if self.current["kind"] != 0:
                raise ValueError(f"Failed to fully close position. Final kind: {self.current['kind']}")

        except Exception as e:
            self.logger.error(f"Error closing position {self.position_id}: {str(e)}")
            raise e

    async def close_trader_position(self):
        """Close out trader position by setting size to 0"""
        # Get current block timestamp
        block = await self.w3.eth.get_block("latest")
        current_time = block["timestamp"]
        deadline = current_time + (30 * 60)

        # Send modify trader position transaction
        await send_async_transaction(
            self.w3,
            self.foil.contract.functions.modifyTraderPosition,
            self.account_address,
            self.pk,
            self.logger,
            "ARBITRAGE: Close Trader Position",
            self.position_id,  # positionId
            0,  # size
            0,  # deltaCollateralLimit
            deadline,  # deadline
        )
