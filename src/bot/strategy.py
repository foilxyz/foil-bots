import logging

from .config import BotConfig
from .exceptions import SkipBotRun
from .utils import price_to_tick


class BotStrategy:
    def __init__(self, position, foil, account_address: str):
        self.position = position
        self.foil = foil
        self.logger = logging.getLogger("LoomBot")
        self.account_address = account_address
        self.config = BotConfig.get_config()

    def check_conditions(self, current_price: float, trailing_avg: float) -> tuple[int, int]:
        """Determine if position needs rebalancing based on price data"""
        # if epoch is not live, raise error
        if not self.foil.is_live():
            raise ValueError("Epoch is not live")

        (_, current_tick, trailing_avg_tick, is_current_price_higher) = self.get_max_tick(current_price, trailing_avg)

        # if position is not active, raise error
        if not self.position.has_current_position():
            (has_minimum_balance, account_collateral_balance, min_position_size) = self.has_minimum_balance()
            if not has_minimum_balance:
                self.logger.info(
                    f"""
                    ----------------------
                    | Balance Details   |
                    ----------------------
                    Account Balance:    {account_collateral_balance}
                    Min Position Size:  {min_position_size}"""
                )
                raise ValueError("Insufficient balance to open position")

            if trailing_avg_tick + self.config.risk_spread_spacing_width > self.foil.epoch["base_asset_max_tick"]:
                raise ValueError("Trailing average too high to open position (Out of Range)")

        tick_spacing = self.foil.market_params["tick_spacing"]
        current_position_tick_lower = self.position.current["tick_lower"]

        self.logger.info(
            f"""
            ----------------------
            | Tick Information  |
            ----------------------
            Current Tick:          {current_tick}
            Trailing Avg Tick:     {trailing_avg_tick} 
            Tick Spacing:          {tick_spacing}
            Position Lower Tick:   {current_position_tick_lower}
            Is Market Price Higher:{is_current_price_higher}"""
        )

        if is_current_price_higher and current_position_tick_lower == current_tick + tick_spacing:
            raise SkipBotRun(
                f"Position is optimized to 1 tick space away from current price tick: {current_tick}, Skipping..."
            )

        risk_adjusted_lower_tick = trailing_avg_tick + (tick_spacing * self.config.risk_spread_spacing_width)

        if not is_current_price_higher and current_position_tick_lower == risk_adjusted_lower_tick:
            raise SkipBotRun(
                f"Position is optimized to risk adjusted tick spacing away from average trailing price tick: "
                f"{risk_adjusted_lower_tick}, Skipping..."
            )

        self.logger.info("!!!---Conditions met for rebalancing---!!!")

        return (current_tick, trailing_avg_tick)

    def get_max_tick(self, current_price: float, trailing_avg: float) -> tuple[int, int, int, bool]:
        """Returns the larger tick between current price and trailing average"""
        current_tick = price_to_tick(current_price, self.foil.market_params["tick_spacing"])
        trailing_avg_tick = price_to_tick(trailing_avg, self.foil.market_params["tick_spacing"])
        return max(current_tick, trailing_avg_tick), current_tick, trailing_avg_tick, current_tick > trailing_avg_tick

    def has_minimum_balance(self) -> tuple[bool, int, int]:
        """Check if the account has a minimum balance"""
        account_collateral_balance = (
            self.foil.market_params["collateral_asset"].functions.balanceOf(self.account_address).call()
        )
        return (
            account_collateral_balance >= self.config.min_position_size,
            account_collateral_balance,
            self.config.min_position_size,
        )

    def calculate_new_range(self, current_price_tick: int, trailing_avg_tick: int) -> tuple[int, int]:
        """Calculate new tick range based on trailing average"""
        tick_spacing = self.foil.market_params["tick_spacing"]
        max_market_tick = self.foil.epoch["base_asset_max_tick"]
        if current_price_tick > trailing_avg_tick:
            low_tick = current_price_tick + tick_spacing
            high_tick = min(max_market_tick, low_tick + (tick_spacing * self.config.lp_range_width))
            return (low_tick, high_tick)
        else:
            low_tick = trailing_avg_tick + (tick_spacing * self.config.risk_spread_spacing_width)
            high_tick = min(max_market_tick, low_tick + (tick_spacing * self.config.lp_range_width))
            return (low_tick, high_tick)

    def run(self, current_market_price: float, trailing_avg_price: float):
        """Execute the rebalancing transaction"""

        (current_tick, trailing_avg_tick) = self.check_conditions(current_market_price, trailing_avg_price)

        # Your rebalancing execution here
        if self.position.has_current_position():
            self.position.close_current_position()

        (new_lower, new_upper) = self.calculate_new_range(current_tick, trailing_avg_tick)
        self.logger.info(
            f"""
                ----------------------
                | New Range Details |
                ----------------------
                New Lower Tick:     {new_lower}
                New Upper Tick:     {new_upper}"""
        )

        self.position.open_new_position(new_lower, new_upper)
