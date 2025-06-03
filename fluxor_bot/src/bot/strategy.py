import logging
import time

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
            self.logger.info("No position found - checking with AI")

            # Create actual positions based on AI prediction
            if hasattr(self.foil, "ai_prediction") and self.foil.ai_prediction is not None:
                self._create_positions(self.foil.ai_prediction)
            else:
                self.logger.warning("No AI prediction available, skipping position creation")

    def _create_positions(self, prediction_percentage: float) -> None:
        """Create actual positions based on AI prediction percentage"""
        self.logger.info(f"📊 Creating both high and low positions for {prediction_percentage}% prediction")

        # Convert percentage to prediction value (65% -> 0.65)
        prediction_value = prediction_percentage / 100.0

        # Convert prediction value to tick using shared utils
        tick_spacing = self.foil.market_params["tick_spacing"]
        prediction_tick = price_to_tick(prediction_value, tick_spacing)
        self.logger.info(f"🎯 Prediction value: {prediction_value:.3f} -> Tick: {prediction_tick}")

        # Get configuration values and convert to ticks
        risk_spread = int(self.config.risk_spread_spacing_width * tick_spacing)
        lp_range = int(self.config.lp_range_width * tick_spacing)

        # Calculate both positions around the prediction
        # Low position (below prediction)
        low_max_tick = prediction_tick - risk_spread
        low_min_tick = low_max_tick - lp_range

        # High position (above prediction)
        high_min_tick = prediction_tick + risk_spread
        high_max_tick = high_min_tick + lp_range

        # Convert ticks back to prices for display
        low_min_price = float(tick_to_price(low_min_tick))
        low_max_price = float(tick_to_price(low_max_tick))
        high_min_price = float(tick_to_price(high_min_tick))
        high_max_price = float(tick_to_price(high_max_tick))

        # Log the positions we're about to create
        self.logger.info("🏗️ CREATING BOTH POSITIONS:")
        self.logger.info("📍 Low Position (below prediction):")
        self.logger.info(f"   Tick Range: {low_min_tick} to {low_max_tick}")
        self.logger.info(f"   Price Range: {low_min_price:.4f} to {low_max_price:.4f}")

        self.logger.info("📍 High Position (above prediction):")
        self.logger.info(f"   Tick Range: {high_min_tick} to {high_max_tick}")
        self.logger.info(f"   Price Range: {high_min_price:.4f} to {high_max_price:.4f}")

        try:
            # Create the low position first
            self.logger.info("🚀 Creating low position (below prediction)...")
            self.position.open_new_position(low_min_tick, low_max_tick)
            self.logger.info("✅ Low position created successfully")

            # Wait a moment and refresh position state
            time.sleep(2)
            self.position.hydrate_current_position()

            # Create the high position
            self.logger.info("🚀 Creating high position (above prediction)...")
            self.position.open_new_position(high_min_tick, high_max_tick)
            self.logger.info("✅ High position created successfully")

            self.logger.info("🎉 Both positions created successfully!")

        except Exception as e:
            self.logger.error(f"❌ Failed to create positions: {str(e)}")
            raise
