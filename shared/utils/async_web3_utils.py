"""
Async Web3 utilities for interacting with the blockchain
"""

import logging
from decimal import Decimal
from typing import Any, Callable, Dict, List, Optional, Tuple, TypedDict, Union

from web3 import Web3
from web3.eth import AsyncEth
from web3.exceptions import TimeExhausted, TransactionNotFound
from web3.net import AsyncNet
from web3.providers.async_base import AsyncBaseProvider
from web3.providers.async_rpc import AsyncHTTPProvider
from web3.types import TxReceipt, Wei


class TransactionConfig(TypedDict, total=False):
    from_address: str
    gas_limit_multiplier: float
    nonce: Optional[int]
    max_fee_per_gas_multiplier: float
    priority_fee_multiplier: float
    value: Wei
    custom_transaction_params: Dict[str, Any]


def price_to_tick(price: Union[float, Decimal], tick_spacing: int) -> int:
    """Convert a price to its corresponding tick value"""
    price = Decimal(price)
    log_price = Decimal.ln(price) / Decimal.ln(Decimal("1.0001"))
    tick = int(log_price / tick_spacing) * tick_spacing  # Floor and snap
    return tick


def tick_to_sqrt_price_x96(tick: int) -> int:
    """Convert a tick to its corresponding sqrtPriceX96 value"""
    import math

    # Based on the UniswapV3 math for tick to sqrtPriceX96
    absTick = abs(tick)
    ratio = Decimal(1.0001) ** Decimal(absTick)
    if tick < 0:
        ratio = Decimal(1) / ratio

    sqrt_ratio = ratio.sqrt()
    sqrt_price_x96 = int(sqrt_ratio * (2**96))
    return sqrt_price_x96


async def create_async_web3_provider(rpc_url: str, logger: logging.Logger) -> Web3:
    """
    Create and initialize an async Web3 provider.

    Args:
        rpc_url: RPC URL to connect to
        logger: Logger instance

    Returns:
        Initialized async Web3 instance
    """
    logger.info(f"Connecting to RPC (async): {rpc_url}")
    # Create an async provider
    async_provider = AsyncHTTPProvider(rpc_url)

    # Create a Web3 instance with async capabilities
    w3 = Web3(async_provider, modules={"eth": (AsyncEth,), "net": (AsyncNet,)})

    # Check connection
    connected = await w3.is_connected()
    if not connected:
        raise ConnectionError(f"Failed to connect to Web3 provider at {rpc_url}")

    chain_id = await w3.eth.chain_id
    logger.info(f"Connected to network with chain ID: {chain_id}")

    return w3


async def estimate_gas(contract_function: Callable, w3: Web3, from_address: str, *args: Any, **kwargs: Any) -> int:
    """
    Estimate the gas required for a contract function call.

    Args:
        contract_function: The contract function
        w3: Web3 instance
        from_address: The sender address
        *args: Arguments for the contract function
        **kwargs: Keyword arguments for the transaction

    Returns:
        Gas estimate with buffer
    """
    built_function = contract_function(*args)
    gas_estimate = await built_function.estimate_gas({"from": from_address, **kwargs})
    # Add 20% buffer to gas estimate
    return int(gas_estimate * 1.2)


async def send_async_transaction(
    w3: Web3,
    contract_fn: Callable,
    account_address: str,
    private_key: str,
    logger: logging.Logger,
    tx_description: str,
    *args: Any,
    tx_config: Optional[TransactionConfig] = None,
    timeout: int = 600,
) -> TxReceipt:
    """
    Helper function to asynchronously send and wait for a transaction.

    Args:
        w3: Web3 instance
        contract_fn: Contract function to call
        account_address: Sender address
        private_key: Sender private key
        logger: Logger instance
        tx_description: Description for logging
        *args: Variable arguments for contract function
        tx_config: Optional transaction configuration
        timeout: Transaction timeout in seconds

    Returns:
        Transaction receipt
    """
    if tx_config is None:
        tx_config = {}

    gas_limit_multiplier = tx_config.get("gas_limit_multiplier", 1.2)
    max_fee_multiplier = tx_config.get("max_fee_per_gas_multiplier", 2)
    priority_fee_multiplier = tx_config.get("priority_fee_multiplier", 1)
    custom_tx_params = tx_config.get("custom_transaction_params", {})

    try:
        # Get latest block for gas calculation
        latest_block = await w3.eth.get_block("latest")
        base_fee = latest_block["baseFeePerGas"]

        # Get priority fee
        priority_fee = await w3.eth.max_priority_fee

        # Calculate max fee
        max_fee = base_fee + int(priority_fee * max_fee_multiplier)

        # Gas estimation
        built_function = contract_fn(*args)
        gas_estimate = await built_function.estimate_gas({"from": account_address})
        gas_with_buffer = int(gas_estimate * gas_limit_multiplier)

        # Get nonce - either provided or fetched
        nonce = tx_config.get("nonce")
        if nonce is None:
            nonce = await w3.eth.get_transaction_count(account_address, "pending")

        # Build transaction parameters
        tx_params = {
            "from": account_address,
            "nonce": nonce,
            "gas": gas_with_buffer,
            "maxFeePerGas": max_fee,
            "maxPriorityFeePerGas": int(priority_fee * priority_fee_multiplier),
            **custom_tx_params,
        }

        # Add value if specified
        if "value" in tx_config:
            tx_params["value"] = tx_config["value"]

        # Build transaction
        tx = await built_function.build_transaction(tx_params)

        # Sign and send
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = await w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        logger.info(f"Sent transaction: {tx_description} (tx: {tx_hash.hex()})")

        # Wait for receipt
        receipt = await w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout)
        if receipt["status"] != 1:
            raise ValueError(f"Transaction failed: {tx_description}")

        logger.info(f"Confirmed: {tx_description} (block: {receipt.blockNumber})")
        return receipt

    except (TimeExhausted, TransactionNotFound) as e:
        logger.error(f"Transaction timed out: {tx_description} - {str(e)}")
        raise ValueError(f"Transaction failed or timed out: {str(e)}")
    except Exception as e:
        logger.error(f"Error in transaction {tx_description}: {str(e)}")
        raise


async def simulate_async_transaction(
    w3: Web3, contract_fn: Callable, account_address: str, logger: logging.Logger, *args: Any, **kwargs: Any
) -> Dict[str, Any]:
    """
    Asynchronously simulate a transaction without sending it to the blockchain.

    Args:
        w3: Web3 instance
        contract_fn: Contract function to call
        account_address: Sender address
        logger: Logger instance
        *args: Variable arguments for contract function
        **kwargs: Additional transaction parameters

    Returns:
        dict: Simulation results containing success status, gas estimate, and call result
    """
    try:
        # Built function
        built_function = contract_fn(*args)

        # Try to estimate gas to check if transaction would succeed
        gas_estimate = await built_function.estimate_gas({"from": account_address})

        # If gas estimation succeeds, try to call the function
        try:
            # Simulate the call
            result = await built_function.call({"from": account_address})

            # Build sample transaction parameters (for informational purposes)
            latest_block = await w3.eth.get_block("latest")
            base_fee = latest_block["baseFeePerGas"]
            priority_fee = await w3.eth.max_priority_fee
            max_fee = base_fee + priority_fee * 2

            nonce = await w3.eth.get_transaction_count(account_address, "pending")

            # Create a sample transaction (won't be sent)
            tx = await built_function.build_transaction(
                {
                    "from": account_address,
                    "nonce": nonce,
                    "gas": int(gas_estimate * 1.2),
                    "maxFeePerGas": max_fee,
                    "maxPriorityFeePerGas": priority_fee,
                    **kwargs,
                }
            )

            logger.info(f"Estimated gas: {gas_estimate}")

            return {"success": True, "gas_estimate": gas_estimate, "result": result, "transaction": tx}

        except Exception as call_error:
            return {
                "success": False,
                "gas_estimate": gas_estimate,
                "error": str(call_error),
                "error_type": "call_error",
            }

    except Exception as gas_error:
        logger.error(f"Transaction would fail: {str(gas_error)}")
        return {"success": False, "error": str(gas_error), "error_type": "gas_estimation_error"}
