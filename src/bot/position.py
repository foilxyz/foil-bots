import logging
from typing import TypedDict

from web3 import Web3

from .config import BotConfig
from .foil import Foil
from .utils import send_transaction, tick_to_sqrt_price_x96


class CurrentPosition(TypedDict):
    kind: int
    uniswap_position_id: int
    liquidity: int
    tick_lower: int
    tick_upper: int
    collateral_amount: int


class Position:
    def __init__(self, account_address: str, foil: Foil, w3: Web3):
        self.logger = logging.getLogger("LoomBot")
        self.account_address = account_address
        self.w3 = w3
        self.pk = BotConfig.get_config().wallet_pk
        self.foil = foil

        self.hydrate_current_position()

    def hydrate_current_position(self):
        position_count = self.foil.contract.functions.balanceOf(self.account_address).call()

        if position_count == 0:
            self.logger.info("No positions found")
            self.current = {
                "kind": 0,
                "uniswap_position_id": 0,
                "liquidity": 0,
                "tick_lower": 0,
                "tick_upper": 0,
                "collateral_amount": 0,
            }
            return

        # get latest position
        self.position_id = self.foil.contract.functions.tokenOfOwnerByIndex(
            self.account_address, position_count - 1
        ).call()

        (_, kind, _, collateral_amount, _, _, _, _, uniswap_position_id, _) = self.foil.contract.functions.getPosition(
            self.position_id
        ).call()

        if kind == 1:
            position_data = (
                self.foil.market_params["uniswap_position_manager"].functions.positions(uniswap_position_id).call()
            )
            (_, _, _, _, _, tick_lower, tick_upper, liquidity, _, _, _, _) = position_data
        else:
            tick_lower = 0
            tick_upper = 0
            liquidity = 0

        self.logger.info(
            f"""
                ----------------------
                | Position Details   |
                ----------------------
                ID:                {self.position_id}
                Kind:              {kind}
                Uniswap Position:  {uniswap_position_id}
                Liquidity:         {liquidity}
                Tick Lower:        {tick_lower}
                Tick Upper:        {tick_upper}
                Collateral Amount: {collateral_amount}"""
        )

        self.current = {
            "kind": kind,
            "uniswap_position_id": uniswap_position_id,
            "liquidity": liquidity,
            "tick_lower": tick_lower,
            "tick_upper": tick_upper,
            "collateral_amount": collateral_amount,
        }

    def has_current_position(self) -> bool:
        return self.current["kind"] != 0 and self.current["collateral_amount"] != 0

    def close_lp_position(self) -> int:
        """
        Decrease liquidity to 0 and return the new position kind
        """
        current_time = self.w3.eth.get_block("latest").timestamp
        deadline = current_time + (30 * 60)  # 30 minutes from now

        # Create decrease liquidity params struct as tuple
        decrease_params = (
            self.position_id,  # positionId
            self.current["liquidity"],  # liquidity
            0,  # minGasAmount
            0,  # minEthAmount
            deadline,  # deadline
        )

        # Send decrease liquidity transaction
        send_transaction(
            self.foil.w3,
            self.foil.contract.functions.decreaseLiquidityPosition,
            self.account_address,
            self.pk,
            self.logger,
            "LOOM: Decrease Liquidity",
            decrease_params,
        )

        # Check position after decrease
        position = self.foil.contract.functions.getPosition(self.position_id).call()
        return position[1]  # Return new kind

    def close_trader_position(self):
        """
        Close out trader position by setting size to 0
        """
        current_time = self.w3.eth.get_block("latest").timestamp
        deadline = current_time + (30 * 60)

        # Send modify trader position transaction
        send_transaction(
            self.w3,
            self.foil.contract.functions.modifyTraderPosition,
            self.account_address,
            self.pk,
            self.logger,
            "LOOM: Close Trader Position",
            self.position_id,  # positionId
            0,  # size
            0,  # deltaCollateralLimit
            deadline,  # deadline
        )

    def close_current_position(self):
        """Close current position fully"""
        try:
            if self.current["kind"] == 1:
                self.logger.info("Closing LP Position")
                kind = self.close_lp_position()
                self.hydrate_current_position()

                if kind == 0:
                    self.logger.info("LP Position successfully closed")
                elif kind == 1:
                    raise ValueError("Could not close position, something went wrong")
                elif kind == 2:
                    self.logger.info("LP Position transitioned to Trader Position")
                    self.close_trader_position()
                    self.hydrate_current_position()
                else:
                    raise ValueError("Invalid position kind after decrease")

            # Handle trader position first if it exists
            if self.current["kind"] == 2:
                self.logger.info("Closing Trader Position")
                self.close_trader_position()
                self.hydrate_current_position()

            # Final verification
            if self.current["kind"] != 0:
                raise ValueError(f"Failed to fully close position. Final kind: {self.current['kind']}")

        except Exception as e:
            self.logger.error(f"Error closing position {self.position_id}: {str(e)}")
            raise e

    def open_new_position(self, new_lower: int, new_upper: int):
        """Open a new position with the given lower and upper ticks"""
        sqrt_price_x96_lower = tick_to_sqrt_price_x96(new_lower)
        sqrt_price_x96_upper = tick_to_sqrt_price_x96(new_upper)
        sqrt_price_x96_current = self.foil.get_current_price_sqrt_x96()

        # Calculate token amounts
        # Get user's collateral balance
        collateral_balance = (
            self.foil.market_params["collateral_asset"].functions.balanceOf(self.account_address).call()
        )

        # Use minimum of balance and configured max amount
        config = BotConfig.get_config()
        deposit_amount = min(collateral_balance, config.max_position_size)

        # Quote required token amounts for liquidity
        (token0_amount, token1_amount, _) = self.foil.contract.functions.quoteLiquidityPositionTokens(
            int(self.foil.epoch["epoch_id"]),
            int(deposit_amount),
            int(sqrt_price_x96_current),
            int(sqrt_price_x96_lower),
            int(sqrt_price_x96_upper),
        ).call()

        self.logger.info(
            f"""
            ----------------------
            | Quoted LP Position |
            ----------------------
            Deposit Amount:     {deposit_amount}
            Token0 Amount:      {token0_amount}
            Token1 Amount:      {token1_amount}"""
        )

        # Approve collateral spending
        send_transaction(
            self.w3,
            self.foil.market_params["collateral_asset"].functions.approve,
            self.account_address,
            self.pk,
            self.logger,
            "LOOM: Approve Collateral",
            self.foil.contract.address,
            int(deposit_amount),
        )

        # Get current timestamp and add 30 minutes for deadline
        current_block = self.w3.eth.get_block("latest")
        deadline = current_block.timestamp + (30 * 60)

        # Create position parameters struct as tuple
        position_params = (
            int(self.foil.epoch["epoch_id"]),  # epochId: uint256
            int(token0_amount),  # amountTokenA: uint256
            int(token1_amount),  # amountTokenB: uint256
            int(deposit_amount),  # collateralAmount: uint256
            int(new_lower),  # lowerTick: int24
            int(new_upper),  # upperTick: int24
            0,  # minAmountTokenA: uint256
            0,  # minAmountTokenB: uint256
            int(deadline),  # deadline: uint256
        )

        try:
            # Send transaction
            send_transaction(
                self.w3,
                self.foil.contract.functions.createLiquidityPosition,
                self.account_address,
                self.pk,
                self.logger,
                "LOOM: Create Liquidity Position",
                position_params,
            )

            # Get new position details
            self.hydrate_current_position()

        except Exception as e:
            self.logger.error(f"Failed to create liquidity position: {str(e)}")
            raise
