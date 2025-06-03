import logging

from shared.utils.web3_utils import price_to_tick, tick_to_price

from .config import BotConfig
from .foil import Foil
from .position import Position


class FluxorStrategy:
    def __init__(self, position: Position, foil: Foil, account_address: str):
        self.position = position
        self.foil = foil
        self.account_address = account_address
        self.logger = logging.getLogger(f"FluxorBot-{foil.market_config.market_id}")
        self.config = BotConfig.get_config()

    def run(self) -> None:
        """Execute the trading strategy"""
        self.logger.info("🔄 Running Fluxor strategy...")

        # Check if market is live
        if not self.foil.is_live():
            self.logger.warning("Market epoch is not live, skipping strategy execution")
            return

        # Get current price
        current_price_d18 = self.foil.get_current_price_d18()
        current_price = self.foil.w3.from_wei(current_price_d18, "ether")

        self.logger.info(f"Current market price: {current_price}")

        # Log AI prediction if available
        if hasattr(self.foil, "ai_prediction") and self.foil.ai_prediction is not None:
            self.logger.info(f"🤖 AI Prediction: {self.foil.ai_prediction}% likelihood of resolving to 1")

        # Example strategy placeholder:
        if self.position.has_current_position():
            self.logger.info("Position already exists - TODO")
        else:
            self.logger.info("No position found - lets go")

            # Create theoretical positions based on AI prediction
            if hasattr(self.foil, "ai_prediction") and self.foil.ai_prediction is not None:
                self._create_theoretical_positions(self.foil.ai_prediction)
            else:
                self.logger.warning("No AI prediction available, skipping position creation")

    def _create_theoretical_positions(self, prediction_percentage: float) -> None:
        """Create theoretical positions based on AI prediction percentage"""
        self.logger.info(f"📊 Creating theoretical positions for {prediction_percentage}% prediction")

        # Convert percentage to prediction value (65% -> 0.65)
        prediction_value = prediction_percentage / 100.0

        # Convert prediction value to tick using shared utils
        tick_spacing = self.foil.market_params["tick_spacing"]
        prediction_tick = price_to_tick(prediction_value, tick_spacing)
        self.logger.info(f"🎯 Prediction value: {prediction_value:.3f} -> Tick: {prediction_tick}")

        # Get configuration values and convert to ticks
        risk_spread = int(self.config.risk_spread_spacing_width * tick_spacing)
        lp_range = int(self.config.lp_range_width * tick_spacing)

        # Left side position (below prediction)
        left_max_tick = prediction_tick - risk_spread
        left_min_tick = left_max_tick - lp_range

        # Right side position (above prediction)
        right_min_tick = prediction_tick + risk_spread
        right_max_tick = right_min_tick + lp_range

        # Convert ticks back to prices for display using shared utils
        left_min_price = float(tick_to_price(left_min_tick))
        left_max_price = float(tick_to_price(left_max_tick))
        right_min_price = float(tick_to_price(right_min_tick))
        right_max_price = float(tick_to_price(right_max_tick))

        # Log theoretical positions
        self.logger.info("🏗️ THEORETICAL POSITIONS:")
        self.logger.info("📍 Left Position:")
        self.logger.info(f"   Tick Range: {left_min_tick} to {left_max_tick}")
        self.logger.info(f"   Price Range: {left_min_price:.4f} to {left_max_price:.4f}")

        self.logger.info("📍 Right Position:")
        self.logger.info(f"   Tick Range: {right_min_tick} to {right_max_tick}")
        self.logger.info(f"   Price Range: {right_min_price:.4f} to {right_max_price:.4f}")

    def calculate_position_size(self) -> float:
        """Calculate appropriate position size based on risk management"""
        return self.config.position_size

    def get_tick_range(self, current_price: float) -> tuple[int, int]:
        """Calculate optimal tick range for liquidity position"""
        # This is now handled by _create_theoretical_positions
        tick_spacing = self.foil.market_params["tick_spacing"]
        current_tick = price_to_tick(current_price, tick_spacing)
        return (current_tick - 100, current_tick + 100)  # Default range
