"""
Position management module
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional, TypedDict

from web3 import Web3

from shared.clients.discord_client import DiscordNotifier
from shared.utils.async_web3_utils import send_async_transaction, simulate_async_transaction

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

    def is_trader_position(self) -> bool:
        """Check if the current position is a trader position"""
        return self.current["kind"] == 2

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

    async def quote_create_trader_position(self, size: int) -> tuple[int, int]:
        """
        Get a quote for creating a trader position

        Args:
            size: The size of the position to create

        Returns:
            Tuple of (requiredCollateral, fillPrice)
        """
        epoch_id = self.foil.epoch["epoch_id"]
        quote = await self.foil.contract.functions.quoteCreateTraderPosition(epoch_id, size).call()

        required_collateral, fill_price = quote
        return required_collateral, fill_price

    async def create_trader_position(
        self, size: int, delta_collateral_limit: int, deadline: int, simulate: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new trader position with optional simulation

        Args:
            size: The size of the position to create
            delta_collateral_limit: The limit for collateral changes
            deadline: The deadline for the transaction
            simulate: Whether to simulate the transaction instead of executing it

        Returns:
            If simulate is True, returns a dict with position details from the event
            If simulate is False, returns None after executing the transaction
        """
        epoch_id = self.foil.epoch["epoch_id"]
        collateral_asset = self.foil.market_params["collateral_asset"]

        # Get the current allowance
        current_allowance = await collateral_asset.functions.allowance(
            self.account_address, self.foil.contract.address
        ).call()

        # If allowance is less than the required collateral, simulate/execute approval
        if current_allowance < delta_collateral_limit:
            self.logger.info(f"Approving {delta_collateral_limit} collateral to Foil contract")

            await send_async_transaction(
                self.w3,
                collateral_asset.functions.approve,
                self.account_address,
                self.pk,
                self.logger,
                "ARBITRAGE: Approve Collateral",
                self.foil.contract.address,
                delta_collateral_limit,
            )

        else:
            self.logger.info(f"Sufficient allowance already exists: {current_allowance}")

        if simulate:
            # Simulate the position creation
            result = await simulate_async_transaction(
                self.w3,
                self.foil.contract.functions.createTraderPosition,
                self.account_address,
                self.logger,
                epoch_id,
                size,
                delta_collateral_limit,
                deadline,
            )

            # Extract and log position details from simulation result
            if result and "events" in result:
                for event in result["events"]:
                    if event.get("event") == "PositionCreated":
                        position_details = event.get("args", {})
                        self.logger.info(
                            f"""
                            ----------------------
                            | Simulated Position |
                            ----------------------
                            Position ID:        {position_details.get('positionId')}
                            Epoch ID:           {position_details.get('epochId')}
                            Size:               {position_details.get('size')}
                            Collateral:         {position_details.get('collateralAmount')}
                            Fill Price:         {position_details.get('fillPrice')}
                            """
                        )

            return result
        else:
            # Execute the position creation
            await send_async_transaction(
                self.w3,
                self.foil.contract.functions.createTraderPosition,
                self.account_address,
                self.pk,
                self.logger,
                "ARBITRAGE: Create Trader Position",
                epoch_id,
                size,
                delta_collateral_limit,
                deadline,
            )
            return None

    async def find_maximum_viable_size(
        self, initial_size: int, avg_trailing_price: Decimal, available_collateral: int
    ) -> Optional[Dict[str, Any]]:
        """
        Find the maximum viable size for a trader position using binary search

        Args:
            initial_size: The initial size to start with
            avg_trailing_price: The average trailing price from the oracle
            available_collateral: The maximum collateral available to use

        Returns:
            Dict with position details or None if no viable size is found
        """
        config = ArbitrageConfig.get_config()

        # Use binary search to find maximum viable size
        max_size = initial_size
        min_size = 0 if initial_size > 0 else 0  # Start from zero
        viable_size = None
        viable_collateral = None
        viable_fill_price = None

        # Binary search for maximum viable size
        for attempt in range(10):  # Limit search attempts
            # Try the midpoint between min and max
            if max_size * min_size < 0:  # Different signs
                # Special handling for negative/positive ranges
                test_size = (abs(max_size) + abs(min_size)) // 2
                test_size = test_size if max_size > 0 else -test_size
            else:
                test_size = (max_size + min_size) // 2

            self.logger.info(f"Binary search iteration {attempt}: Testing size {test_size}")

            try:
                # Test this size
                required_collateral, fill_price = await self.quote_create_trader_position(test_size)

                # Check if required collateral exceeds available
                if required_collateral > available_collateral:
                    self.logger.info(
                        f"Size {test_size} REJECTED (collateral {required_collateral} exceeds available {available_collateral})"
                    )
                    max_size = test_size
                    continue

                fill_price_decimal = Decimal(self.w3.from_wei(fill_price, "ether"))

                # Calculate price difference ratio
                price_diff = abs(fill_price_decimal - avg_trailing_price)
                price_ratio = price_diff / avg_trailing_price

                self.logger.info(
                    f"Size {test_size} gives price difference ratio {price_ratio} vs threshold {config.price_difference_ratio}"
                )

                # If ratio is good (difference is larger than configured ratio), this size works, try larger
                if price_ratio > Decimal(str(config.price_difference_ratio)):
                    viable_size = test_size
                    viable_collateral = required_collateral
                    viable_fill_price = fill_price

                    # Try a larger size next
                    min_size = test_size

                    self.logger.info(f"Size {test_size} ACCEPTED, new min={min_size}, max={max_size}")
                else:
                    # Price difference too high, try smaller size
                    max_size = test_size
                    self.logger.info(
                        f"Size {test_size} REJECTED (price diff too high), new min={min_size}, max={max_size}"
                    )

            except Exception as e:
                # If error, this size is too large
                self.logger.info(f"Size {test_size} REJECTED (error): {str(e)}")
                max_size = test_size

            # Check if we've converged - only check the size difference
            if abs(max_size - min_size) < 10:
                self.logger.info(f"Binary search converged to size {viable_size}")
                break

        # Use the viable size we found, or log error if none found
        if viable_size is not None:
            self.logger.info(
                f"Found maximum viable position size: {viable_size} "
                f"with required collateral: {viable_collateral} "
                f"and fill price: {viable_fill_price}"
            )
            # Return the results
            return {"size": viable_size, "required_collateral": viable_collateral, "fill_price": viable_fill_price}
        else:
            self.logger.error("Failed to find any viable position size")
            return None
