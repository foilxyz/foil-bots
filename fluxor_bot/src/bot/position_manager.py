"""
Position Manager for handling multiple positions via API queries
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional, TypedDict

from web3 import Web3

from shared.clients.async_api_client import AsyncFoilAPIClient
from shared.clients.discord_client import DiscordNotifier
from shared.utils.web3_utils import send_transaction, simulate_transaction, tick_to_sqrt_price_x96

from .config import BotConfig


class PositionData(TypedDict):
    market_id: int
    position_id: int
    is_lp: bool
    collateral: int
    is_settled: bool
    low_price_tick: int
    high_price_tick: int
    lp_base_token: int
    lp_quote_token: int
    liquidity: int
    pnl: Optional[int]  # PnL in wei, None if failed to fetch


class MarketPnlData(TypedDict):
    market_id: int
    total_pnl: int
    position_count: int
    positions_with_pnl: List[Dict[str, Any]]


class PositionManager:
    """Manages multiple positions for a market using API queries"""

    def __init__(self, w3: Web3, account_address: str, api_client: AsyncFoilAPIClient):
        self.w3 = w3
        self.account_address = account_address
        self.api_client = api_client
        self.logger = logging.getLogger("FluxorBot")

        # Initialize Discord notifier
        self.discord = DiscordNotifier.get_instance("FluxorBot", BotConfig.get_config())

        # Will store positions by market_id
        self.positions_by_market: Dict[int, List[PositionData]] = {}

        # Add a lock to prevent concurrent API calls
        self._api_lock = asyncio.Lock()

    async def load_positions_for_market(
        self, market_address: str, market_id: int, chain_id: int, foil_contract, market_params: Dict
    ) -> List[PositionData]:
        """
        Load all positions for a specific market using GraphQL query and get tick data from Uniswap position manager

        Args:
            market_address: The market contract address
            market_id: The specific market ID to filter by
            chain_id: The blockchain chain ID
            foil_contract: The Foil contract instance
            market_params: Market parameters including uniswap position manager

        Returns:
            List of active LP positions for the specified market with correct tick data from Uniswap
        """
        query = """
        query GetUserPositions($marketAddress: String, $owner: String, $chainId: Int) {
          positions(marketAddress: $marketAddress, owner: $owner, chainId: $chainId)  {
            market {
              marketId
            }
            isLP
            collateral
            positionId
            isSettled
            lpBaseToken
            lpQuoteToken
          }
        }
        """

        variables = {"marketAddress": market_address, "owner": self.account_address, "chainId": chain_id}

        # Use lock to prevent concurrent API access
        async with self._api_lock:
            try:
                self.logger.info(f"[Market {market_id}] Loading positions from API...")
                self.logger.info(
                    f"Query variables: marketAddress={market_address}, owner={self.account_address}, chainId={chain_id}"
                )

                # Execute GraphQL query with retry logic
                max_retries = 3
                for attempt in range(max_retries):
                    try:
                        result = await self.api_client.query_async(query, variables)
                        break
                    except Exception as e:
                        if "Transport is already connected" in str(e) and attempt < max_retries - 1:
                            self.logger.warning(
                                f"[Market {market_id}] Transport connection issue, retrying... (attempt {attempt + 1}/{max_retries})"
                            )
                            await asyncio.sleep(0.5)  # Short delay before retry
                            continue
                        else:
                            raise

                raw_positions = result.get("positions", [])

                self.logger.info(f"[Market {market_id}] Found {len(raw_positions)} total positions from API")

                # Filter and convert positions
                filtered_positions = []

                for pos in raw_positions:
                    # Filter by market ID
                    if pos["market"]["marketId"] != market_id:
                        continue

                    # Filter to only LP positions
                    if not pos["isLP"]:
                        continue

                    # Filter to only active positions (both tokens > 0 means position is active)
                    if pos["lpBaseToken"] == 0 and pos["lpQuoteToken"] == 0:
                        self.logger.debug(f"[Market {market_id}] Skipping closed position {pos['positionId']}")
                        continue

                    # Filter out settled positions
                    if pos["isSettled"]:
                        self.logger.debug(f"[Market {market_id}] Skipping settled position {pos['positionId']}")
                        continue

                    # Get position details from Foil contract to get uniswap position ID
                    try:
                        position_id = pos["positionId"]
                        (_, kind, _, collateral_amount, _, _, _, _, uniswap_position_id, _) = (
                            foil_contract.functions.getPosition(position_id).call()
                        )

                        # Get tick information from Uniswap position manager
                        if kind == 1 and uniswap_position_id > 0:  # LP position
                            position_data = (
                                market_params["uniswap_position_manager"]
                                .functions.positions(uniswap_position_id)
                                .call()
                            )
                            (_, _, _, _, _, tick_lower, tick_upper, liquidity, _, _, _, _) = position_data
                        else:
                            # Not an LP position or invalid uniswap position ID
                            self.logger.debug(
                                f"[Market {market_id}] Skipping non-LP position {position_id} (kind={kind})"
                            )
                            continue

                        # Convert to our PositionData format
                        position_data: PositionData = {
                            "market_id": pos["market"]["marketId"],
                            "position_id": position_id,
                            "is_lp": pos["isLP"],
                            "collateral": pos["collateral"],
                            "is_settled": pos["isSettled"],
                            "low_price_tick": tick_lower,
                            "high_price_tick": tick_upper,
                            "lp_base_token": pos["lpBaseToken"],
                            "lp_quote_token": pos["lpQuoteToken"],
                            "liquidity": liquidity,
                        }

                        filtered_positions.append(position_data)
                        self.logger.info(
                            f"[Market {market_id}] Active LP position found: ID={position_id}, "
                            f"Ticks={tick_lower}-{tick_upper} (from Uniswap), "
                            f"Base={pos['lpBaseToken']}, Quote={pos['lpQuoteToken']}"
                        )

                    except Exception as e:
                        self.logger.warning(
                            f"[Market {market_id}] Failed to get tick data for position {pos['positionId']}: {str(e)}"
                        )
                        continue

                # Store positions for this market
                self.positions_by_market[market_id] = filtered_positions

                self.logger.info(f"[Market {market_id}] Loaded {len(filtered_positions)} active LP positions")
                return filtered_positions

            except Exception as e:
                self.logger.error(f"[Market {market_id}] Failed to load positions: {str(e)}")
                raise

    def get_positions_for_market(self, market_id: int) -> List[PositionData]:
        """Get loaded positions for a specific market"""
        return self.positions_by_market.get(market_id, [])

    def has_positions_for_market(self, market_id: int) -> bool:
        """Check if there are any active positions for a market"""
        positions = self.get_positions_for_market(market_id)
        return len(positions) > 0

    def get_position_count_for_market(self, market_id: int) -> int:
        """Get the number of active positions for a market"""
        return len(self.get_positions_for_market(market_id))

    async def collect_pnl_for_market(self, market_id: int, foil_contract) -> MarketPnlData:
        """
        Collect PnL data for all positions in a market

        Args:
            market_id: The market ID to collect PnL for
            foil_contract: The Foil contract instance

        Returns:
            MarketPnlData with aggregated PnL information
        """
        positions = self.get_positions_for_market(market_id)

        market_pnl_data: MarketPnlData = {
            "market_id": market_id,
            "total_pnl": 0,
            "position_count": len(positions),
            "positions_with_pnl": [],
        }

        if not positions:
            self.logger.info(f"[Market {market_id}] No positions to collect PnL for")
            return market_pnl_data

        self.logger.info(f"[Market {market_id}] Collecting PnL for {len(positions)} positions...")

        for position_data in positions:
            position_id = position_data["position_id"]
            try:
                # Call getPositionPnl on the Foil contract
                pnl_wei = foil_contract.functions.getPositionPnl(position_id).call()
                pnl_susds = self.w3.from_wei(pnl_wei, "ether")  # sUSDS has 18 decimals like ETH

                # Update position data with PnL
                position_data["pnl"] = pnl_wei

                # Add to market totals
                market_pnl_data["total_pnl"] += pnl_wei
                market_pnl_data["positions_with_pnl"].append(
                    {
                        "position_id": position_id,
                        "pnl_wei": pnl_wei,
                        "pnl_susds": float(pnl_susds),
                    }
                )

                self.logger.info(f"[Market {market_id}] Position {position_id} PnL: {pnl_susds:.6f} sUSDS")

            except Exception as e:
                self.logger.warning(f"[Market {market_id}] Failed to get PnL for position {position_id}: {str(e)}")
                position_data["pnl"] = None

        total_pnl_susds = self.w3.from_wei(market_pnl_data["total_pnl"], "ether")
        self.logger.info(
            f"[Market {market_id}] Total PnL: {total_pnl_susds:.6f} sUSDS across {len(positions)} positions"
        )

        return market_pnl_data

    async def collect_all_pnl(self) -> Dict[int, MarketPnlData]:
        """
        Collect PnL data for all markets with positions

        Returns:
            Dictionary mapping market_id to MarketPnlData
        """
        all_pnl_data = {}

        for market_id in self.positions_by_market.keys():
            # Note: We need the foil_contract for each market, but we don't have access here
            # This method will be called from MarketManager where contracts are available
            self.logger.info(f"Market {market_id} has positions, PnL collection will be handled by MarketManager")

        return all_pnl_data

    async def create_position(
        self, foil_contract, epoch_data: Dict, market_params: Dict, new_lower: int, new_upper: int, market_id: int
    ) -> None:
        """
        Create a new liquidity position

        Args:
            foil_contract: The Foil contract instance
            epoch_data: Current epoch data
            market_params: Market parameters including collateral asset
            new_lower: Lower tick for the position
            new_upper: Upper tick for the position
            market_id: Market ID for logging
        """
        sqrt_price_x96_lower = tick_to_sqrt_price_x96(new_lower)
        sqrt_price_x96_upper = tick_to_sqrt_price_x96(new_upper)

        # Get current price from the contract
        sqrt_price_x96_current = foil_contract.functions.getSqrtPriceX96(market_id).call()

        # Get user's collateral balance
        collateral_balance = market_params["collateral_asset"].functions.balanceOf(self.account_address).call()

        # Use configured position size (convert to wei)
        config = BotConfig.get_config()
        deposit_amount = int(config.collateral_size * 10**18)

        # Check if we have sufficient balance
        if collateral_balance < deposit_amount:
            raise ValueError(f"Insufficient balance. Required: {deposit_amount}, Available: {collateral_balance}")

        # Quote required token amounts for liquidity (use slightly less amount for quote precision)
        quote_amount = deposit_amount - int(1e6)  # Subtract 1 million wei for quote
        (token0_amount, token1_amount, _) = foil_contract.functions.quoteLiquidityPositionTokens(
            int(epoch_data["epoch_id"]),
            int(quote_amount),
            int(sqrt_price_x96_current),
            int(sqrt_price_x96_lower),
            int(sqrt_price_x96_upper),
        ).call()

        self.logger.info(
            f"[Market {market_id}] Quoted LP Position - Quote Amount: {quote_amount}, Deposit Amount: {deposit_amount}, "
            f"Token0: {token0_amount}, Token1: {token1_amount}"
        )

        # Check current allowance before approving
        current_allowance = (
            market_params["collateral_asset"].functions.allowance(self.account_address, foil_contract.address).call()
        )

        self.logger.info(f"[Market {market_id}] Current allowance: {current_allowance}, Required: {deposit_amount}")

        # Only approve if current allowance is insufficient
        if current_allowance < deposit_amount:
            self.logger.info(f"[Market {market_id}] Insufficient allowance, approving collateral spending...")
            send_transaction(
                self.w3,
                market_params["collateral_asset"].functions.approve,
                self.account_address,
                BotConfig.get_config().wallet_pk,
                self.logger,
                "FluxorBot: Approve Collateral",
                foil_contract.address,
                int(deposit_amount),
            )
        else:
            self.logger.info(f"[Market {market_id}] Sufficient allowance already exists, skipping approval")

        # Get current timestamp and add 30 minutes for deadline
        current_block = self.w3.eth.get_block("latest")
        deadline = current_block.timestamp + (30 * 60)

        # Create position parameters struct as tuple
        position_params = (
            int(epoch_data["epoch_id"]),  # epochId: uint256
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
            self.logger.info(f"[Market {market_id}] Simulating liquidity position creation...")
            simulation = simulate_transaction(
                self.w3,
                foil_contract.functions.createLiquidityPosition,
                self.account_address,
                self.logger,
                position_params,
            )

            if not simulation["success"]:
                raise ValueError(f"Transaction simulation failed: {simulation['error']}")

            self.logger.info(f"[Market {market_id}] Simulation successful. Estimated gas: {simulation['gas_estimate']}")

            # Send transaction with higher gas and shorter timeout for Base mainnet
            self.logger.info(f"[Market {market_id}] Sending liquidity position creation transaction...")
            send_transaction(
                self.w3,
                foil_contract.functions.createLiquidityPosition,
                self.account_address,
                BotConfig.get_config().wallet_pk,
                self.logger,
                "FluxorBot: Create Liquidity Position",
                position_params,
                gas_multiplier=1.5,  # Use 150% of estimated gas instead of 120%
                timeout=60,  # Reduce timeout to 1 minute to avoid hanging
                poll_latency=3,  # Check every 3 seconds
            )

            self.logger.info(f"✅ [Market {market_id}] Position created successfully!")

        except Exception as e:
            self.logger.error(f"[Market {market_id}] Failed to create liquidity position: {str(e)}")
            raise

    async def close_lp_position(self, position_id: int, liquidity: int, foil_contract, market_id: int) -> bool:
        """
        Decrease liquidity to 0 and return whether position transitioned to trader

        Args:
            position_id: The position ID to close
            liquidity: The liquidity amount to decrease
            foil_contract: The Foil contract instance
            market_id: Market ID for logging

        Returns:
            True if position transitioned to trader, False if fully closed
        """
        current_time = self.w3.eth.get_block("latest").timestamp
        deadline = current_time + (30 * 60)  # 30 minutes from now

        # Create decrease liquidity params struct as tuple
        decrease_params = (
            position_id,  # positionId
            liquidity,  # liquidity
            0,  # minGasAmount
            0,  # minEthAmount
            deadline,  # deadline
        )

        # First simulate the transaction to check the result
        self.logger.info(
            f"[Market {market_id}] Simulating decrease liquidity transaction for position {position_id}..."
        )
        simulation_result = simulate_transaction(
            self.w3,
            foil_contract.functions.decreaseLiquidityPosition,
            self.account_address,
            self.logger,
            decrease_params,
        )

        if not simulation_result["success"]:
            raise ValueError(f"Decrease liquidity simulation failed: {simulation_result['error']}")

        # The function returns (decreasedAmount0, decreasedAmount1, collateralAmount)
        decreased_amount0, decreased_amount1, collateral_amount = simulation_result["result"]

        self.logger.info(
            f"[Market {market_id}] Simulation result: decreased_amount0={decreased_amount0}, "
            f"decreased_amount1={decreased_amount1}, collateral_amount={collateral_amount}"
        )

        # Send the actual transaction
        send_transaction(
            self.w3,
            foil_contract.functions.decreaseLiquidityPosition,
            self.account_address,
            BotConfig.get_config().wallet_pk,
            self.logger,
            "FluxorBot: Decrease Liquidity",
            decrease_params,
        )

        self.logger.info(f"[Market {market_id}] LP Position {position_id} successfully closed")

        # Return whether position transitioned to trader (collateral_amount > 0)
        return collateral_amount > 0

    async def close_trader_position(self, position_id: int, foil_contract, market_id: int):
        """
        Close out trader position by setting size to 0

        Args:
            position_id: The position ID to close
            foil_contract: The Foil contract instance
            market_id: Market ID for logging
        """
        current_time = self.w3.eth.get_block("latest").timestamp
        deadline = current_time + (30 * 60)

        # Send modify trader position transaction
        send_transaction(
            self.w3,
            foil_contract.functions.modifyTraderPosition,
            self.account_address,
            BotConfig.get_config().wallet_pk,
            self.logger,
            "FluxorBot: Close Trader Position",
            position_id,  # positionId
            0,  # size
            0,  # deltaCollateralLimit
            deadline,  # deadline
        )

        self.logger.info(f"[Market {market_id}] Trader Position {position_id} successfully closed")

    async def close_position(self, position_data: PositionData, foil_contract, market_id: int) -> bool:
        """
        Close an LP position completely, handling transition to trader position if needed

        Args:
            position_data: The position data to close
            foil_contract: The Foil contract instance
            market_id: Market ID for logging

        Returns:
            True if position was successfully closed, False otherwise
        """
        position_id = position_data["position_id"]

        try:
            self.logger.info(f"[Market {market_id}] Closing LP position {position_id}")

            # Since we already know it's an LP position, close it and check if it transitions
            transitioned_to_trader = await self.close_lp_position(
                position_id, position_data["liquidity"], foil_contract, market_id
            )

            # If position transitioned to trader, close the trader position too
            if transitioned_to_trader:
                self.logger.info(
                    f"[Market {market_id}] LP Position {position_id} transitioned to Trader Position, closing trader position..."
                )
                await self.close_trader_position(position_id, foil_contract, market_id)

            self.logger.info(f"✅ [Market {market_id}] Position {position_id} successfully closed")
            return True

        except Exception as e:
            self.logger.error(f"❌ [Market {market_id}] Failed to close position {position_id}: {str(e)}")
            return False

    async def close_all_positions_for_market(self, market_id: int, foil_contract):
        """
        Close all positions for a specific market

        Args:
            market_id: The market ID to close positions for
            foil_contract: The Foil contract instance
        """
        positions = self.get_positions_for_market(market_id)

        if not positions:
            self.logger.info(f"[Market {market_id}] No positions to close")
            return

        total_positions = len(positions)
        successful_closes = 0

        self.logger.info(f"[Market {market_id}] Closing {total_positions} positions")

        for position_data in positions:
            success = await self.close_position(position_data, foil_contract, market_id)
            if success:
                successful_closes += 1

        failed_closes = total_positions - successful_closes

        if failed_closes > 0:
            self.logger.warning(
                f"[Market {market_id}] Finished closing positions - "
                f"Success: {successful_closes}/{total_positions}, Failed: {failed_closes}"
            )
        else:
            self.logger.info(f"✅ [Market {market_id}] Successfully closed all {successful_closes} positions")
