import logging
import time
from typing import Dict, Optional

from shared.utils.web3_utils import price_to_tick, tick_to_price

from .config import BotConfig
from .foil import Foil
from .position_manager import PositionManager


def truncate_question(question: str, max_length: int = 40) -> str:
    """Helper function to truncate market questions for display"""
    if not question or question == "Unknown":
        return "Unknown question"

    if len(question) <= max_length:
        return question

    return question[: max_length - 3] + "..."


class FluxorStrategy:
    def __init__(self, position_manager: PositionManager, foil: Foil, account_address: str):
        self.position_manager = position_manager
        self.foil = foil
        self.account_address = account_address
        self.logger = logging.getLogger("FluxorBot")
        self.config = BotConfig.get_config()

    async def run(self) -> Dict:
        """Execute the trading strategy"""
        market_id = self.foil.market_id
        market_question = self.foil.market_data.get("question", "Unknown")
        question_display = truncate_question(market_question, 40)

        self.logger.info(f"🔄 [{question_display}] Running Fluxor strategy...")

        # Initialize result data
        result = {
            "action_taken": "no_change",
            "positions_created": 0,
            "positions_closed": 0,
        }

        # Check if market is live
        if not self.foil.is_live():
            self.logger.warning(f"[{question_display}] Market epoch is not live, skipping strategy execution")
            return result

        # Get current price
        current_price_d18 = self.foil.get_current_price_d18()
        current_price = self.foil.w3.from_wei(current_price_d18, "ether")

        self.logger.info(f"[{question_display}] Current market price: {current_price}")

        # Log AI prediction if available
        if hasattr(self.foil, "ai_prediction") and self.foil.ai_prediction is not None:
            self.logger.info(
                f"🤖 [{question_display}] AI Prediction: {self.foil.ai_prediction}% likelihood of resolving to 1"
            )

        # Check existing positions
        existing_positions = self.position_manager.get_positions_for_market(market_id)
        if existing_positions:
            self.logger.info(f"[{question_display}] Found {len(existing_positions)} existing positions:")
            for pos in existing_positions:
                self.logger.info(
                    f"  - Position ID: {pos['position_id']}, Ticks: {pos['low_price_tick']}-{pos['high_price_tick']}, "
                    f"Base: {pos['lp_base_token']}, Quote: {pos['lp_quote_token']}"
                )

            # Check if positions need rebalancing
            if hasattr(self.foil, "ai_prediction") and self.foil.ai_prediction is not None:
                rebalance_result = await self._check_and_rebalance_positions(
                    existing_positions, self.foil.ai_prediction
                )
                result.update(rebalance_result)
            else:
                self.logger.warning(f"[{question_display}] No AI prediction available for rebalancing check")
        else:
            self.logger.info(f"[{question_display}] No existing positions found - checking with AI")

            # Create actual positions based on AI prediction
            if hasattr(self.foil, "ai_prediction") and self.foil.ai_prediction is not None:
                creation_result = await self._create_positions(self.foil.ai_prediction)
                result.update(creation_result)
            else:
                self.logger.warning(f"[{question_display}] No AI prediction available, skipping position creation")

        return result

    def _calculate_position_ticks(self, prediction_percentage: float):
        """
        Calculate position tick ranges based on prediction, respecting market bounds

        Returns:
            dict with 'low' and 'high' keys, each containing (min_tick, max_tick) tuples
            Returns None for positions that are entirely out of bounds
        """
        market_id = self.foil.market_id
        question_display = truncate_question(self.foil.market_data.get("question", "Unknown"), 40)

        # Convert percentage to prediction value (65% -> 0.65)
        prediction_value = prediction_percentage / 100.0

        # Convert prediction value to tick using shared utils
        tick_spacing = self.foil.market_params["tick_spacing"]
        prediction_tick = price_to_tick(prediction_value, tick_spacing)

        # Get market bounds
        base_min_tick = self.foil.epoch["base_asset_min_tick"]
        base_max_tick = self.foil.epoch["base_asset_max_tick"]

        self.logger.info(f"🎯 [{question_display}] Prediction value: {prediction_value:.3f} -> Tick: {prediction_tick}")
        self.logger.info(f"📏 [{question_display}] Market bounds: {base_min_tick} to {base_max_tick}")

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
            self.logger.info(f"⚠️ [{question_display}] Low position entirely below market bounds, skipping")
            positions["low"] = None
        elif low_min_tick > base_max_tick:
            # Entire low position is above market bounds
            self.logger.info(f"⚠️ [{question_display}] Low position entirely above market bounds, skipping")
            positions["low"] = None
        else:
            # Clamp low position to market bounds
            clamped_low_min = max(low_min_tick, base_min_tick)
            clamped_low_max = min(low_max_tick, base_max_tick)
            positions["low"] = (clamped_low_min, clamped_low_max)

            if clamped_low_min != low_min_tick or clamped_low_max != low_max_tick:
                self.logger.info(
                    f"📐 [{question_display}] Low position clamped: {low_min_tick}-{low_max_tick} -> {clamped_low_min}-{clamped_low_max}"
                )

        # Check high position bounds
        if high_min_tick > base_max_tick:
            # Entire high position is above market bounds
            self.logger.info(f"⚠️ [{question_display}] High position entirely above market bounds, skipping")
            positions["high"] = None
        elif high_max_tick < base_min_tick:
            # Entire high position is below market bounds
            self.logger.info(f"⚠️ [{question_display}] High position entirely below market bounds, skipping")
            positions["high"] = None
        else:
            # Clamp high position to market bounds
            clamped_high_min = max(high_min_tick, base_min_tick)
            clamped_high_max = min(high_max_tick, base_max_tick)
            positions["high"] = (clamped_high_min, clamped_high_max)

            if clamped_high_min != high_min_tick or clamped_high_max != high_max_tick:
                self.logger.info(
                    f"📐 [{question_display}] High position clamped: {high_min_tick}-{high_max_tick} -> {clamped_high_min}-{clamped_high_max}"
                )

        return positions

    async def _create_positions(self, prediction_percentage: float) -> Dict:
        """Create actual positions based on AI prediction percentage"""
        market_id = self.foil.market_id
        question_display = truncate_question(self.foil.market_data.get("question", "Unknown"), 40)

        self.logger.info(f"📊 [{question_display}] Creating positions for {prediction_percentage}% prediction")

        # Calculate valid position ticks
        positions = self._calculate_position_ticks(prediction_percentage)

        # Check if we have any valid positions to create
        valid_positions = [pos for pos in positions.values() if pos is not None]
        if not valid_positions:
            self.logger.warning(f"⚠️ [{question_display}] No valid positions within market bounds, skipping")
            return {"positions_created": 0}

        # Log the positions we're about to create
        self.logger.info(f"🏗️ [{question_display}] CREATING VALID POSITIONS:")

        try:
            created_count = 0

            # Create low position if valid
            if positions["low"] is not None:
                low_min_tick, low_max_tick = positions["low"]
                low_min_price = float(tick_to_price(low_min_tick))
                low_max_price = float(tick_to_price(low_max_tick))

                self.logger.info(f"📍 [{question_display}] Low Position (below prediction):")
                self.logger.info(f"   Tick Range: {low_min_tick} to {low_max_tick}")
                self.logger.info(f"   Price Range: {low_min_price:.4f} to {low_max_price:.4f}")

                self.logger.info(f"🚀 [{question_display}] Creating low position...")
                await self.position_manager.create_position(
                    self.foil.contract, self.foil.epoch, self.foil.market_params, low_min_tick, low_max_tick, market_id
                )
                self.logger.info(f"✅ [{question_display}] Low position created successfully")
                created_count += 1

            # Create high position if valid
            if positions["high"] is not None:
                high_min_tick, high_max_tick = positions["high"]
                high_min_price = float(tick_to_price(high_min_tick))
                high_max_price = float(tick_to_price(high_max_tick))

                self.logger.info(f"📍 [{question_display}] High Position (above prediction):")
                self.logger.info(f"   Tick Range: {high_min_tick} to {high_max_tick}")
                self.logger.info(f"   Price Range: {high_min_price:.4f} to {high_max_price:.4f}")

                self.logger.info(f"🚀 [{question_display}] Creating high position...")
                await self.position_manager.create_position(
                    self.foil.contract,
                    self.foil.epoch,
                    self.foil.market_params,
                    high_min_tick,
                    high_max_tick,
                    market_id,
                )
                self.logger.info(f"✅ [{question_display}] High position created successfully")
                created_count += 1

            self.logger.info(f"🎉 [{question_display}] {created_count} position(s) created successfully!")

            return {"action_taken": "created_positions", "positions_created": created_count}

        except Exception as e:
            self.logger.error(f"❌ [{question_display}] Failed to create positions: {str(e)}")
            raise

    async def _check_and_rebalance_positions(self, existing_positions, ai_prediction) -> Dict:
        """Check if positions need rebalancing and rebalance if necessary"""
        market_id = self.foil.market_id
        question_display = truncate_question(self.foil.market_data.get("question", "Unknown"), 40)

        self.logger.info(
            f"🔄 [{question_display}] Checking positions for rebalancing against {ai_prediction}% prediction"
        )

        # Calculate optimal position ticks for current prediction
        optimal_positions = self._calculate_position_ticks(ai_prediction)

        # Get tick spacing for distance calculations
        tick_spacing = self.foil.market_params["tick_spacing"]

        # Calculate rebalance threshold in ticks
        rebalance_deviation_ticks = int(self.config.rebalance_deviation * tick_spacing)

        self.logger.info(
            f"📏 [{question_display}] Rebalance deviation threshold: {rebalance_deviation_ticks} ticks ({self.config.rebalance_deviation} * {tick_spacing})"
        )

        # For simplicity, check the first position against both optimal positions
        # and rebalance if it's too far from both
        first_position = existing_positions[0]
        first_position_lower_tick = first_position["low_price_tick"]

        self.logger.info(
            f"🔍 [{question_display}] Checking first position {first_position['position_id']} lower tick: {first_position_lower_tick}"
        )

        # Calculate distance to optimal low position
        needs_rebalance = True
        if optimal_positions["low"] is not None:
            optimal_low_min, _ = optimal_positions["low"]
            low_distance = abs(first_position_lower_tick - optimal_low_min)
            self.logger.info(f"📐 [{question_display}] Distance from optimal low position: {low_distance} ticks")

            if low_distance <= rebalance_deviation_ticks:
                needs_rebalance = False

        # Calculate distance to optimal high position
        if optimal_positions["high"] is not None:
            optimal_high_min, _ = optimal_positions["high"]
            high_distance = abs(first_position_lower_tick - optimal_high_min)
            self.logger.info(f"📐 [{question_display}] Distance from optimal high position: {high_distance} ticks")

            if high_distance <= rebalance_deviation_ticks:
                needs_rebalance = False

        if needs_rebalance:
            self.logger.info(
                f"🔄 [{question_display}] Rebalancing needed - first position too far from both optimal positions"
            )

            # Close all existing positions
            self.logger.info(f"🔄 [{question_display}] Closing all {len(existing_positions)} positions for rebalancing")
            closed_count = 0

            for pos in existing_positions:
                try:
                    success = await self.position_manager.close_position(pos, self.foil.contract, market_id)
                    if success:
                        closed_count += 1
                except Exception as e:
                    self.logger.error(
                        f"❌ [{question_display}] Failed to close position {pos['position_id']}: {str(e)}"
                    )

            # Create new optimal positions
            self.logger.info(f"🏗️ [{question_display}] Creating new optimal positions after rebalancing")
            creation_result = await self._create_positions(ai_prediction)

            return {
                "action_taken": "rebalanced",
                "positions_closed": closed_count,
                "positions_created": creation_result.get("positions_created", 0),
            }
        else:
            self.logger.info(f"✅ [{question_display}] No rebalancing needed, keeping existing positions")
            return {"action_taken": "no_change"}
