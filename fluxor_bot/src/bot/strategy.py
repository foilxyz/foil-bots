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
        self.logger = logging.getLogger("FluxorBot")
        self.config = BotConfig.get_config()

    def run(self) -> None:
        """Execute the trading strategy"""
        market_id = self.foil.market_id
        self.logger.info(f"🔄 [Market {market_id}] Running Fluxor strategy...")

        # Check if market is live
        if not self.foil.is_live():
            self.logger.warning(f"[Market {market_id}] Market epoch is not live, skipping strategy execution")
            return

        # Get current price
        current_price_d18 = self.foil.get_current_price_d18()
        current_price = self.foil.w3.from_wei(current_price_d18, "ether")

        self.logger.info(f"[Market {market_id}] Current market price: {current_price}")

        # Log AI prediction if available
        if hasattr(self.foil, "ai_prediction") and self.foil.ai_prediction is not None:
            self.logger.info(
                f"🤖 [Market {market_id}] AI Prediction: {self.foil.ai_prediction}% likelihood of resolving to 1"
            )

        # Example strategy placeholder:
        if self.position.has_current_position():
            self.logger.info(f"[Market {market_id}] Position already exists - TODO")
        else:
            self.logger.info(f"[Market {market_id}] No position found - checking with AI")

            # Create actual positions based on AI prediction
            if hasattr(self.foil, "ai_prediction") and self.foil.ai_prediction is not None:
                self._create_positions(self.foil.ai_prediction)
            else:
                self.logger.warning(f"[Market {market_id}] No AI prediction available, skipping position creation")

    def _calculate_position_ticks(self, prediction_percentage: float):
        """
        Calculate position tick ranges based on prediction, respecting market bounds

        Returns:
            dict with 'low' and 'high' keys, each containing (min_tick, max_tick) tuples
            Returns None for positions that are entirely out of bounds
        """
        market_id = self.foil.market_id

        # Convert percentage to prediction value (65% -> 0.65)
        prediction_value = prediction_percentage / 100.0

        # Convert prediction value to tick using shared utils
        tick_spacing = self.foil.market_params["tick_spacing"]
        prediction_tick = price_to_tick(prediction_value, tick_spacing)

        # Get market bounds
        base_min_tick = self.foil.epoch["base_asset_min_tick"]
        base_max_tick = self.foil.epoch["base_asset_max_tick"]

        self.logger.info(f"🎯 [Market {market_id}] Prediction value: {prediction_value:.3f} -> Tick: {prediction_tick}")
        self.logger.info(f"📏 [Market {market_id}] Market bounds: {base_min_tick} to {base_max_tick}")

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

        positions = {}

        # Check low position bounds
        if low_max_tick < base_min_tick:
            # Entire low position is below market bounds
            self.logger.info(f"⚠️ [Market {market_id}] Low position entirely below market bounds, skipping")
            positions["low"] = None
        elif low_min_tick > base_max_tick:
            # Entire low position is above market bounds
            self.logger.info(f"⚠️ [Market {market_id}] Low position entirely above market bounds, skipping")
            positions["low"] = None
        else:
            # Clamp low position to market bounds
            clamped_low_min = max(low_min_tick, base_min_tick)
            clamped_low_max = min(low_max_tick, base_max_tick)
            positions["low"] = (clamped_low_min, clamped_low_max)

            if clamped_low_min != low_min_tick or clamped_low_max != low_max_tick:
                self.logger.info(
                    f"📐 [Market {market_id}] Low position clamped: {low_min_tick}-{low_max_tick} -> {clamped_low_min}-{clamped_low_max}"
                )

        # Check high position bounds
        if high_min_tick > base_max_tick:
            # Entire high position is above market bounds
            self.logger.info(f"⚠️ [Market {market_id}] High position entirely above market bounds, skipping")
            positions["high"] = None
        elif high_max_tick < base_min_tick:
            # Entire high position is below market bounds
            self.logger.info(f"⚠️ [Market {market_id}] High position entirely below market bounds, skipping")
            positions["high"] = None
        else:
            # Clamp high position to market bounds
            clamped_high_min = max(high_min_tick, base_min_tick)
            clamped_high_max = min(high_max_tick, base_max_tick)
            positions["high"] = (clamped_high_min, clamped_high_max)

            if clamped_high_min != high_min_tick or clamped_high_max != high_max_tick:
                self.logger.info(
                    f"📐 [Market {market_id}] High position clamped: {high_min_tick}-{high_max_tick} -> {clamped_high_min}-{clamped_high_max}"
                )

        return positions

    def _create_positions(self, prediction_percentage: float) -> None:
        """Create actual positions based on AI prediction percentage"""
        market_id = self.foil.market_id
        self.logger.info(f"📊 [Market {market_id}] Creating positions for {prediction_percentage}% prediction")

        # Calculate valid position ticks
        positions = self._calculate_position_ticks(prediction_percentage)

        # Check if we have any valid positions to create
        valid_positions = [pos for pos in positions.values() if pos is not None]
        if not valid_positions:
            self.logger.warning(f"⚠️ [Market {market_id}] No valid positions within market bounds, skipping")
            return

        # Log the positions we're about to create
        self.logger.info(f"🏗️ [Market {market_id}] CREATING VALID POSITIONS:")

        try:
            # Create low position if valid
            if positions["low"] is not None:
                low_min_tick, low_max_tick = positions["low"]
                low_min_price = float(tick_to_price(low_min_tick))
                low_max_price = float(tick_to_price(low_max_tick))

                self.logger.info(f"📍 [Market {market_id}] Low Position (below prediction):")
                self.logger.info(f"   Tick Range: {low_min_tick} to {low_max_tick}")
                self.logger.info(f"   Price Range: {low_min_price:.4f} to {low_max_price:.4f}")

                self.logger.info(f"🚀 [Market {market_id}] Creating low position...")
                # TODO: Uncomment when ready to create actual positions
                # self.position.open_new_position(low_min_tick, low_max_tick)
                self.logger.info(f"✅ [Market {market_id}] Low position created successfully (SIMULATED)")

            # Create high position if valid
            if positions["high"] is not None:
                high_min_tick, high_max_tick = positions["high"]
                high_min_price = float(tick_to_price(high_min_tick))
                high_max_price = float(tick_to_price(high_max_tick))

                self.logger.info(f"📍 [Market {market_id}] High Position (above prediction):")
                self.logger.info(f"   Tick Range: {high_min_tick} to {high_max_tick}")
                self.logger.info(f"   Price Range: {high_min_price:.4f} to {high_max_price:.4f}")

                self.logger.info(f"🚀 [Market {market_id}] Creating high position...")
                # TODO: Uncomment when ready to create actual positions
                # self.position.open_new_position(high_min_tick, high_max_tick)
                self.logger.info(f"✅ [Market {market_id}] High position created successfully (SIMULATED)")

            created_count = len(valid_positions)
            self.logger.info(f"🎉 [Market {market_id}] {created_count} position(s) created successfully! (SIMULATED)")

        except Exception as e:
            self.logger.error(f"❌ [Market {market_id}] Failed to create positions: {str(e)}")
            raise
