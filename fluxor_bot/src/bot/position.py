import logging
from typing import TypedDict

from web3 import Web3

from shared.clients.discord_client import DiscordNotifier
from shared.utils.web3_utils import send_transaction, simulate_transaction, tick_to_sqrt_price_x96

from .config import BotConfig
from .foil import Foil


class CurrentPosition(TypedDict):
    kind: int
    uniswap_position_id: int
    liquidity: int
    tick_lower: int
    tick_upper: int
    collateral_amount: int


class Position:
    def __init__(self, account_address: str, foil: Foil, w3: Web3):
        self.logger = logging.getLogger("FluxorBot")
        self.account_address = account_address
        self.w3 = w3
        self.pk = BotConfig.get_config().wallet_pk
        self.foil = foil

        # Initialize Discord notifier
        self.discord = DiscordNotifier.get_instance("FluxorBot", BotConfig.get_config())

        self.hydrate_current_position()

    def hydrate_current_position(self):
        """Load current position information from the blockchain"""
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
            self.position_id = 0
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
            f"Position Details - ID: {self.position_id}, Kind: {kind}, "
            f"Liquidity: {liquidity}, Ticks: {tick_lower}-{tick_upper}, "
            f"Collateral: {collateral_amount}"
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
        """Check if account has an active position"""
        return self.current["kind"] != 0 and self.current["collateral_amount"] != 0

    def open_new_position(self, new_lower: int, new_upper: int):
        """Open a new liquidity position with the given lower and upper ticks"""
        sqrt_price_x96_lower = tick_to_sqrt_price_x96(new_lower)
        sqrt_price_x96_upper = tick_to_sqrt_price_x96(new_upper)
        sqrt_price_x96_current = self.foil.get_current_price_sqrt_x96()

        # Calculate token amounts
        # Get user's collateral balance
        collateral_balance = (
            self.foil.market_params["collateral_asset"].functions.balanceOf(self.account_address).call()
        )

        # Use configured position size (convert to wei)
        config = BotConfig.get_config()
        deposit_amount = int(config.position_size * 10**18)

        # Check if we have sufficient balance
        if collateral_balance < deposit_amount:
            raise ValueError(f"Insufficient balance. Required: {deposit_amount}, Available: {collateral_balance}")

        # Quote required token amounts for liquidity (use slightly less amount for quote precision)
        quote_amount = deposit_amount - int(1e6)  # Subtract 1 million wei for quote
        (token0_amount, token1_amount, _) = self.foil.contract.functions.quoteLiquidityPositionTokens(
            int(self.foil.epoch["epoch_id"]),
            int(quote_amount),
            int(sqrt_price_x96_current),
            int(sqrt_price_x96_lower),
            int(sqrt_price_x96_upper),
        ).call()

        self.logger.info(
            f"Quoted LP Position - Quote Amount: {quote_amount}, Deposit Amount: {deposit_amount}, "
            f"Token0: {token0_amount}, Token1: {token1_amount}"
        )

        # Check current allowance before approving
        current_allowance = (
            self.foil.market_params["collateral_asset"]
            .functions.allowance(self.account_address, self.foil.contract.address)
            .call()
        )

        self.logger.info(f"Current allowance: {current_allowance}, Required: {deposit_amount}")

        # Only approve if current allowance is insufficient
        if current_allowance < deposit_amount:
            self.logger.info("Insufficient allowance, approving collateral spending...")
            send_transaction(
                self.w3,
                self.foil.market_params["collateral_asset"].functions.approve,
                self.account_address,
                self.pk,
                self.logger,
                "FluxorBot: Approve Collateral",
                self.foil.contract.address,
                int(deposit_amount),
            )
        else:
            self.logger.info("Sufficient allowance already exists, skipping approval")

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
            # Simulate the transaction first to catch any issues
            self.logger.info("Simulating liquidity position creation...")
            simulation = simulate_transaction(
                self.w3,
                self.foil.contract.functions.createLiquidityPosition,
                self.account_address,
                self.logger,
                position_params,
            )

            if not simulation["success"]:
                raise ValueError(f"Transaction simulation failed: {simulation['error']}")

            self.logger.info(f"Simulation successful. Estimated gas: {simulation['gas_estimate']}")

            # Send transaction with higher gas and shorter timeout for Base mainnet
            self.logger.info("Sending liquidity position creation transaction...")
            send_transaction(
                self.w3,
                self.foil.contract.functions.createLiquidityPosition,
                self.account_address,
                self.pk,
                self.logger,
                "FluxorBot: Create Liquidity Position",
                position_params,
                gas_multiplier=1.5,  # Use 150% of estimated gas instead of 120%
                timeout=60,  # Reduce timeout to 1 minute to avoid hanging
                poll_latency=3,  # Check every 3 seconds
            )

            # Get new position details
            self.hydrate_current_position()

            # Format message with position details
            if self.discord:
                message = (
                    f"🆕 **New Position Created** ({self.foil.market_id})\n"
                    f"- Position ID: {self.position_id}\n"
                    f"- Tick Range: {self.current['tick_lower']} to {self.current['tick_upper']}\n"
                    f"- Liquidity: {self.current['liquidity']}\n"
                    f"- Collateral Amount: {self.current['collateral_amount']}"
                )
                self.discord.send_message(message)

        except Exception as e:
            self.logger.error(f"Failed to create liquidity position: {str(e)}")
            raise
