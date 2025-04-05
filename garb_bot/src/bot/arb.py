"""
Arbitrage logic module
"""

import logging
from decimal import Decimal
from typing import Any, Dict, Optional

from shared.clients.discord_client import DiscordNotifier

from .config import ArbitrageConfig
from .exceptions import ConditionNotMet
from .foil import Foil
from .position import Position


class ArbitrageLogic:
    def __init__(self, foil: Foil, position: Position, discord: DiscordNotifier):
        self.foil = foil
        self.position = position
        self.discord = discord
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
            await self.reconcile_price(avg_trailing_price, current_pool_price)

            # Create new position
            return await self.create_new_position(avg_trailing_price, current_pool_price)

        except ConditionNotMet as e:
            self.logger.info(f"Arbitrage condition not met: {str(e)}")
            return None
        except Exception as e:
            error_msg = f"❌ Oops! Something went wrong: {str(e)}"
            self.logger.error(error_msg)
            self.discord.send_message(error_msg)
            return None

    async def create_new_position(
        self, avg_trailing_price: Decimal, current_pool_price: Decimal
    ) -> Optional[Dict[str, Any]]:
        """
        Create a new position with the given parameters

        Args:
            avg_trailing_price: Average trailing price from oracle
            current_pool_price: Current price from Uniswap pool
        """
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
            initial_size, avg_trailing_price, collateral_amount
        )

        if max_viable_result is None:
            self.logger.error("Could not find a viable size for position")
            return None

        size = max_viable_result["size"]
        required_collateral = max_viable_result["required_collateral"]
        fill_price = max_viable_result["fill_price"]

        # Send fun Discord message about the opportunity
        self.discord.send_message(
            f"🎯 **ARBITRAGE OPPORTUNITY FOUND!** 🎯\n"
            f"Time to make some moves! 🚀\n\n"
            f"�� Position Details:\n"
            f"• Size: {size}\n"
            f"• Collateral: {required_collateral}\n"
            f"• Fill Price: {fill_price}\n"
            f"• Direction: {direction}\n\n"
            f"Let's get this bread! 🍞"
        )

        if self.config.execute_arbitrage:
            await self.position.create_trader_position(
                size=size, delta_collateral_limit=required_collateral, deadline=deadline
            )
            # Send confirmation message after position is created
            self.discord.send_message(
                f"✅ **Position Created Successfully!**\n"
                f"All systems go! 🚀\n\n"
                f"📊 Position Details:\n"
                f"• Size: {size}\n"
                f"• Collateral: {required_collateral}\n"
                f"• Fill Price: {fill_price}\n"
                f"• Direction: {direction}\n\n"
                f"Let's watch those profits roll in! 💰"
            )
        else:
            self.logger.info("Arbitrage execution disabled, skipping position creation")
            self.discord.send_message(
                f"⚠️ **Arbitrage Execution Disabled**\n"
                f"Found a juicy opportunity but execution is disabled!\n"
                f"Would have taken a {direction} position with size {size}.\n\n"
                f"Maybe next time! 😉"
            )

    async def check_prerequisites(self):
        """Check if the prerequisites for the arbitrage are met"""
        is_live = await self.foil.is_live()
        if not is_live:
            raise ConditionNotMet("Market is not live")

    async def reconcile_price(self, avg_trailing_price: Decimal, current_pool_price: Decimal):
        """Checks current position, if exists, with price difference ratio"""
        # Check if prices are within the configured price difference ratio
        # Calculate the price difference ratio
        if avg_trailing_price == 0 or current_pool_price == 0:
            raise ConditionNotMet("One of the prices is zero, cannot calculate ratio")

        # Calculate the ratio between the two prices
        price_difference = current_pool_price - avg_trailing_price
        current_price_difference_ratio = abs(price_difference) / current_pool_price

        price_within_bounds = current_price_difference_ratio < Decimal(self.config.price_difference_ratio)
        if self.position.is_trader_position():
            price_swung_against_position = (self.position.direction == "LONG" and price_difference > 0) or (
                self.position.direction == "SHORT" and price_difference < 0
            )
            if price_within_bounds or price_swung_against_position:
                self.logger.warning(
                    "⚠️ ALERT: Trailing price has moved within bounds or past threshold in the opposite direction...."
                )
                # Send fun Discord message about closing position
                self.discord.send_message(
                    f"🔄 **Time to Close Position!**\n"
                    f"Market conditions have changed, time to take profits! 💰\n\n"
                    f"• Price moved within bounds: {price_within_bounds}\n"
                    f"• Price swung against position: {price_swung_against_position}\n\n"
                    f"Closing position and getting ready for the next opportunity! 🎯"
                )
                await self.position.close_current_position()
                # Send confirmation message after position is closed
                self.discord.send_message(
                    f"✅ **Position Closed Successfully!**\n"
                    f"Profits secured! 🎉\n\n"
                    f"Time to find the next opportunity! 🔍"
                )

        if price_within_bounds:
            raise ConditionNotMet(
                f"Price difference ratio {current_price_difference_ratio} is lower than the configured threshold {self.config.price_difference_ratio}"
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
