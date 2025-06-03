import logging
from typing import TypedDict

from web3 import Web3
from web3.contract import Contract

from shared.abis import POSITION_MANAGER_ABI, abi_loader
from shared.utils.openai_client import OpenAIPredictor

from .config import BotConfig

# Remove Discord import for now to fix the error
# from shared.clients.discord_client import DiscordNotifier


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
    def __init__(self, w3: Web3, market_config):
        self.w3 = w3
        self.market_config = market_config
        self.logger = logging.getLogger(f"FluxorBot-{market_config.market_id}")

        market_group_address = market_config.market_group_address
        self.contract = w3.eth.contract(address=market_group_address, abi=abi_loader.get_abi("foil"))
        self.logger.info(f"Loaded foil contract at {market_group_address}")

        self._hydrate_market_and_epoch()

        # Log market connection with claim statement
        self.logger.info(
            f"🧠 Foil Market Connected ({market_config.market_id}) - "
            f"Contract: {market_group_address}, Epoch ID: {self.epoch['epoch_id']}"
        )
        self.logger.info(f"📝 Claim Statement: {self.epoch['claim_statement']}")

        # Get AI prediction for the claim statement
        self._get_ai_prediction()

    def _get_ai_prediction(self):
        """Get AI prediction likelihood for the claim statement"""
        try:
            config = BotConfig.get_config()

            predictor = OpenAIPredictor(config.openai_api_key)
            likelihood = predictor.get_prediction_likelihood(self.epoch["claim_statement"])

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

    def _hydrate_market_and_epoch(self):
        """Get the current epoch and market parameters"""
        # Fix the contract call - getEpoch returns two named tuples
        result = self.contract.functions.getEpoch(self.market_config.market_id).call()
        epoch_data, market_params = result

        # Extract from epoch_data tuple (EpochData struct)
        epoch_id = epoch_data[0]  # epochId
        end_time = epoch_data[2]  # endTime
        base_asset_min_tick = epoch_data[8]  # baseAssetMinPriceTick
        base_asset_max_tick = epoch_data[9]  # baseAssetMaxPriceTick
        claim_statement_bytes = epoch_data[13]  # claimStatement (bytes)

        # Extract from market_params tuple (MarketParams struct)
        uniswap_position_manager = market_params[4]  # uniswapPositionManager
        # Convert bytes to string
        claim_statement = claim_statement_bytes.decode("utf-8") if claim_statement_bytes else ""

        (_, collateral_token, *_) = self.contract.functions.getMarket().call()
        tick_spacing = self.contract.functions.getMarketTickSpacing().call()

        position_manager = self.w3.eth.contract(address=uniswap_position_manager, abi=POSITION_MANAGER_ABI)
        collateral_asset = self.w3.eth.contract(address=collateral_token, abi=abi_loader.get_abi("erc20"))

        self.epoch = Epoch(
            epoch_id=epoch_id,
            end_time=end_time,
            base_asset_min_tick=base_asset_min_tick,
            base_asset_max_tick=base_asset_max_tick,
            claim_statement=claim_statement,
        )
        self.market_params: Market = {
            "uniswap_position_manager": position_manager,
            "collateral_asset": collateral_asset,
            "tick_spacing": tick_spacing,
        }

    def get_current_price_d18(self) -> int:
        """Get the current price in D18 format"""
        price = self.contract.functions.getReferencePrice(self.epoch["epoch_id"]).call()
        return price

    def get_current_price_sqrt_x96(self) -> int:
        """Get the current price in sqrtPriceX96. Returns a large integer that may exceed int bounds."""
        price = self.contract.functions.getSqrtPriceX96(self.epoch["epoch_id"]).call()
        return price
