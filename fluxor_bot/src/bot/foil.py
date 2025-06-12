import logging
from typing import Any, Dict, TypedDict

from web3 import Web3
from web3.contract import Contract

from shared.abis import POSITION_MANAGER_ABI, abi_loader
from shared.utils.openai_client import OpenAIPredictor

from .config import BotConfig


class Epoch(TypedDict):
    epoch_id: int
    end_time: int
    base_asset_min_tick: int
    base_asset_max_tick: int
    claim_statement: str


class Market(TypedDict):
    uniswap_position_manager: Contract
    collateral_asset: Contract
    tick_spacing: int


class Foil:
    def __init__(
        self,
        w3: Web3,
        market_data: Dict[str, Any],
        market_group_address: str,
        collateral_asset: str,
        uniswap_position_manager_address: str,
    ):
        self.w3 = w3
        self.market_data = market_data
        self.market_group_address = market_group_address
        self.collateral_asset_address = collateral_asset  # Already checksummed from API
        self.market_id = market_data["marketId"]
        self.logger = logging.getLogger("FluxorBot")

        # Still need contract for price data and other operations
        self.contract = w3.eth.contract(address=market_group_address, abi=abi_loader.get_abi("foil"))
        self.logger.info(f"Loaded foil contract at {market_group_address}")

        # Initialize market and epoch from API data
        self._hydrate_market_and_epoch_from_api(uniswap_position_manager_address)

        # Log market connection with claim statement
        self.logger.info(
            f"🧠 Foil Market Connected ({self.market_id}) - "
            f"Contract: {market_group_address}, Market: {self.market_data['question'][:50]}..."
        )
        self.logger.info(f"📝 Market Question: {self.market_data['question']}")
        self.logger.info(f"💰 Collateral Asset: {self.collateral_asset_address}")

        # Get AI prediction for the market question
        self._get_ai_prediction()

    def _get_ai_prediction(self):
        """Get AI prediction likelihood for the market question"""
        try:
            config = BotConfig.get_config()

            predictor = OpenAIPredictor(config.openai_api_key)
            likelihood = predictor.get_prediction_likelihood(self.market_data["question"])

            if likelihood is not None:
                self.logger.info(f"🤖 AI Prediction: {likelihood}% likelihood of resolving to 1")
                # Store the prediction for later use in strategy
                self.ai_prediction = likelihood
            else:
                self.logger.warning("Failed to get AI prediction")
                self.ai_prediction = None

        except Exception as e:
            self.logger.error(f"Error getting AI prediction: {str(e)}")
            self.ai_prediction = None

    def is_live(self) -> bool:
        """Check if the current epoch is live"""
        current_time = self.w3.eth.get_block("latest").timestamp
        return current_time < self.epoch["end_time"]

    def _hydrate_market_and_epoch_from_api(self, uniswap_position_manager_address: str):
        """Initialize market and epoch data from API response"""
        # Extract market data from API response
        market_id = self.market_data["marketId"]
        end_timestamp = self.market_data["endTimestamp"]
        base_asset_min_tick = self.market_data["baseAssetMinPriceTick"]
        base_asset_max_tick = self.market_data["baseAssetMaxPriceTick"]
        question = self.market_data["question"]

        # Use collateral asset from API (already checksummed) instead of contract call
        collateral_token = self.collateral_asset_address

        # Create contract instances
        position_manager = self.w3.eth.contract(address=uniswap_position_manager_address, abi=POSITION_MANAGER_ABI)
        collateral_asset = self.w3.eth.contract(address=collateral_token, abi=abi_loader.get_abi("erc20"))

        # Create epoch data structure
        self.epoch = Epoch(
            epoch_id=market_id,  # Using market_id as epoch_id
            end_time=end_timestamp,
            base_asset_min_tick=base_asset_min_tick,
            base_asset_max_tick=base_asset_max_tick,
            claim_statement=question,
        )

        # Create market params with hardcoded tick spacing
        self.market_params: Market = {
            "uniswap_position_manager": position_manager,
            "collateral_asset": collateral_asset,
            "tick_spacing": 200,  # Hardcoded as requested
        }

    def get_current_price_d18(self) -> int:
        """Get the current price in D18 format"""
        price = self.contract.functions.getReferencePrice(self.epoch["epoch_id"]).call()
        return price

    def get_current_price_sqrt_x96(self) -> int:
        """Get the current price in sqrtPriceX96. Returns a large integer that may exceed int bounds."""
        price = self.contract.functions.getSqrtPriceX96(self.epoch["epoch_id"]).call()
        return price
