"""
Arbitrage logic module
"""

import logging
from typing import Any, Dict

from .foil import Foil
from .position import Position


class ArbitrageLogic:
    def __init__(self, foil: Foil, position: Position):
        self.foil = foil
        self.position = position
        self.logger = logging.getLogger("ArbitrageBot")

    async def run(self, avg_trailing_price: int, current_pool_price: int) -> Dict[str, Any]:
        """
        Run the arbitrage logic with the average trailing price and current pool price

        Args:
            avg_trailing_price: The average trailing price from the oracle
            current_pool_price: The current price from the Uniswap pool

        Returns:
            Dict with arbitrage results
        """
        self.logger.info(f"Running arbitrage with prices: avg={avg_trailing_price}, pool={current_pool_price}")

        # Check if market is live
        is_live = await self.foil.is_live()
        if not is_live:
            return {
                "avg_trailing_price": avg_trailing_price,
                "current_pool_price": current_pool_price,
                "price_difference": avg_trailing_price - current_pool_price,
                "performed_arb": False,
                "reason": "Market is not live",
            }

        # This will be filled in later with actual arbitrage logic
        # For now, we just calculate the difference and return the result
        return {
            "avg_trailing_price": avg_trailing_price,
            "current_pool_price": current_pool_price,
            "price_difference": avg_trailing_price - current_pool_price,
            "performed_arb": False,
            "reason": "Arbitrage logic not yet implemented",
        }
