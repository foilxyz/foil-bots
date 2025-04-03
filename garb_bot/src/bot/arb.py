"""
Arbitrage logic module
"""

import logging
from decimal import Decimal

from .config import ArbitrageConfig
from .exceptions import ConditionNotMet
from .foil import Foil
from .position import Position


class ArbitrageLogic:
    def __init__(self, foil: Foil, position: Position):
        self.foil = foil
        self.position = position
        self.logger = logging.getLogger("ArbitrageBot")
        self.config = ArbitrageConfig.get_config()

    async def run(self, avg_trailing_price: Decimal, current_pool_price: Decimal):
        """
        Run the arbitrage logic with the average trailing price and current pool price

        Args:
            avg_trailing_price: The average trailing price from the oracle
            current_pool_price: The current price from the Uniswap pool

        Returns:
            Dict with arbitrage results
        """
        self.logger.info(f"Running arbitrage with prices: avg={avg_trailing_price}, pool={current_pool_price}")

        try:
            await self.check_prerequisites()
            self.check_price_difference(avg_trailing_price, current_pool_price)

            # Determine position direction (long or short)
            is_long = avg_trailing_price > current_pool_price
            direction = "LONG" if is_long else "SHORT"
            self.logger.info(
                f"Taking {direction} position (avg_price={avg_trailing_price}, pool_price={current_pool_price})"
            )

            # Get wallet balance for collateral
            wallet_balance = await self.get_wallet_balance()

            # Determine collateral amount based on min/max config and wallet balance
            collateral_amount = self.determine_collateral_amount(wallet_balance)
            self.logger.info(f"Using collateral amount: {collateral_amount} (wallet balance: {wallet_balance})")

            # Calculate initial size based on collateral and current price
            # Size is positive for long positions, negative for short positions
            size_multiplier = 1 if is_long else -1

            collateral_decimal = Decimal(collateral_amount)

            # Calculate size - use a reasonable scale
            initial_size = collateral_decimal / current_pool_price
            self.logger.info(f"Initial Size: {initial_size} with direction multiplier: {size_multiplier}")

            # Convert to wei and apply direction
            initial_size = int(initial_size * size_multiplier)

            # Get deadline
            block = await self.position.w3.eth.get_block("latest")
            current_time = block["timestamp"]
            deadline = current_time + (30 * 60)  # 30 minutes

            # Find the maximum viable size that satisfies the price ratio constraint
            self.logger.info("Finding maximum viable size that satisfies price ratio constraint...")
            max_viable_result = await self.position.find_maximum_viable_size(
                initial_size, avg_trailing_price, wallet_balance
            )

            if max_viable_result is None:
                self.logger.error("Could not find a viable size for position")
                return None

            size = max_viable_result["size"]
            required_collateral = max_viable_result["required_collateral"]
            fill_price = max_viable_result["fill_price"]

            self.logger.info(
                f"Found optimal position parameters:"
                f"\nSize: {size}"
                f"\nRequired Collateral: {required_collateral}"
                f"\nFill Price: {fill_price}"
                f"\nDirection: {direction}"
            )

            # Simulate the creation to get position details
            simulation_result = await self.position.create_trader_position(
                size=size, delta_collateral_limit=required_collateral, deadline=deadline, simulate=True
            )

            if simulation_result:
                self.logger.info(
                    f"Simulated position details:"
                    f"\nPosition VETH Amount: {simulation_result.get('position_veth_amount', 'N/A')}"
                    f"\nPosition VGAS Amount: {simulation_result.get('position_vgas_amount', 'N/A')}"
                    f"\nBorrowed VETH: {simulation_result.get('position_borrowed_veth', 'N/A')}"
                    f"\nBorrowed VGAS: {simulation_result.get('position_borrowed_vgas', 'N/A')}"
                )

            return {
                "size": size,
                "required_collateral": required_collateral,
                "fill_price": fill_price,
                "direction": direction,
                "simulation_result": simulation_result,
            }

        except ConditionNotMet as e:
            self.logger.info(f"Arbitrage condition not met: {str(e)}")
            return None
        except Exception as e:
            self.logger.error(f"Error in arbitrage logic: {str(e)}")
            return None

    async def check_prerequisites(self):
        """Check if the prerequisites for the arbitrage are met"""
        is_live = await self.foil.is_live()
        if not is_live:
            raise ConditionNotMet("Market is not live")

    def check_price_difference(self, avg_trailing_price: Decimal, current_pool_price: Decimal):
        """Check if the price difference is within the configured price difference ratio"""
        # Check if prices are within the configured price difference ratio
        # Calculate the price difference ratio
        if avg_trailing_price == 0 or current_pool_price == 0:
            raise ConditionNotMet("One of the prices is zero, cannot calculate ratio")

        # Calculate the ratio between the two prices
        if avg_trailing_price > current_pool_price:
            price_ratio = Decimal(avg_trailing_price) / Decimal(current_pool_price)
        else:
            price_ratio = Decimal(current_pool_price) / Decimal(avg_trailing_price)

        # Check if the ratio exceeds the configured threshold
        if price_ratio < Decimal(self.config.price_difference_ratio):
            raise ConditionNotMet(
                f"Price difference ratio {price_ratio} is within threshold {self.config.price_difference_ratio}"
            )

    async def get_wallet_balance(self) -> int:
        """Get the wallet balance for collateral"""

        """
        Get the wallet balance for the collateral asset
        
        Returns:
            Current wallet balance in wei
        """
        collateral_asset = self.foil.market_params["collateral_asset"]
        balance = await collateral_asset.functions.balanceOf(self.position.account_address).call()
        return balance

    def determine_collateral_amount(self, wallet_balance: int) -> int:
        """
        Determine collateral amount based on min/max config and wallet balance

        Args:
            wallet_balance: Current wallet balance

        Returns:
            Collateral amount to use
        """
        if wallet_balance < self.config.min_collateral:
            raise ConditionNotMet("Wallet balance is less than the minimum collateral")
        elif wallet_balance >= self.config.max_collateral:
            return self.config.max_collateral
        else:
            return wallet_balance
