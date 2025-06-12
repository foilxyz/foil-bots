import logging
from decimal import Decimal
from typing import Any, Callable, Dict, Union

from web3 import Web3
from web3.exceptions import TimeExhausted, TransactionNotFound
from web3.types import TxReceipt

BASE_CHAIN_ID = 8453


def price_to_tick(price: Union[float, Decimal], tick_spacing: int) -> int:
    """Convert a price to its corresponding tick value"""
    price = Decimal(price)
    log_price = Decimal.ln(price) / Decimal.ln(Decimal("1.0001"))
    tick = int(log_price / tick_spacing) * tick_spacing  # Floor and snap
    return tick


def tick_to_price(tick: int) -> Decimal:
    """Convert a tick value to its corresponding price"""
    return Decimal(1.0001) ** Decimal(tick)


def tick_to_sqrt_price_x96(tick: int) -> int:
    """Convert a Uniswap V3 tick to sqrtPriceX96."""
    Q96 = Decimal("2") ** 96
    price = tick_to_price(tick)
    return int(price.sqrt() * Q96)


def send_transaction(
    w3: Web3,
    contract_fn: Callable,
    account_address: str,
    private_key: str,
    logger: logging.Logger,
    tx_description: str,
    *args: Any,
    timeout: int = 600,
    poll_latency: int = 2,
    gas_multiplier: float = 1.2,
    **kwargs: Any,
) -> TxReceipt:
    """
    Helper function to send and wait for a transaction.

    Args:
        w3: Web3 instance
        contract_fn: Contract function to call
        account_address: Sender address
        private_key: Sender private key
        logger: Logger instance
        tx_description: Description for logging
        *args: Variable arguments for contract function
        timeout: Transaction timeout in seconds
        poll_latency: Time between receipt checks in seconds
        gas_multiplier: Gas multiplier for transaction (default 1.2 = 20% buffer)
        **kwargs: Additional transaction parameters

    Returns:
        Transaction receipt
    """
    try:
        # Gas estimation
        gas_estimate = contract_fn(*args).estimate_gas({"from": account_address})
        base_fee = w3.eth.get_block("latest")["baseFeePerGas"]
        priority_fee = w3.eth.max_priority_fee

        # Adjust gas pricing for different networks
        chain_id = w3.eth.chain_id
        if chain_id == BASE_CHAIN_ID:  # Base mainnet
            # Base mainnet often needs higher priority fees
            priority_fee = max(priority_fee, int(0.001 * 10**9))  # Minimum 0.001 gwei
            max_fee = base_fee + priority_fee * 3  # Larger buffer for Base
            logger.info(f"Base mainnet detected - Using higher gas: priority={priority_fee}, max={max_fee}")
        else:
            max_fee = base_fee + priority_fee * 2  # Standard buffer

        logger.info(f"Gas estimate: {gas_estimate}, Base fee: {base_fee}, Priority fee: {priority_fee}")

        # Build transaction
        tx = contract_fn(*args).build_transaction(
            {
                "from": account_address,
                "nonce": w3.eth.get_transaction_count(account_address, "pending"),
                "gas": int(gas_estimate * gas_multiplier),
                "maxFeePerGas": max_fee,
                "maxPriorityFeePerGas": priority_fee,
                **kwargs,
            }
        )

        # Sign and send
        signed_tx = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed_tx.rawTransaction)
        logger.info(f"Sent transaction: {tx_description} (tx: {tx_hash.hex()})")

        # Wait for receipt
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=timeout, poll_latency=poll_latency)
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


def simulate_transaction(
    w3: Web3,
    contract_fn: Callable,
    account_address: str,
    logger: logging.Logger,
    *args: Any,
    **kwargs: Any,
) -> Dict[str, Any]:
    """
    Simulate a transaction without sending it to the blockchain.

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
        # Try to estimate gas to check if transaction would succeed
        gas_estimate = contract_fn(*args).estimate_gas({"from": account_address})

        # If gas estimation succeeds, try to call the function
        try:
            # Simulate the call
            result = contract_fn(*args).call({"from": account_address})

            # Build a sample transaction (won't be sent)
            base_fee = w3.eth.get_block("latest")["baseFeePerGas"]
            priority_fee = w3.eth.max_priority_fee
            max_fee = base_fee + priority_fee * 2

            tx = contract_fn(*args).build_transaction(
                {
                    "from": account_address,
                    "nonce": w3.eth.get_transaction_count(account_address, "pending"),
                    "gas": int(gas_estimate * 1.2),  # 20% buffer
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


def create_web3_provider(rpc_url: str, logger: logging.Logger) -> Web3:
    """
    Create and initialize a Web3 provider

    Args:
        rpc_url: RPC URL to connect to
        logger: Logger instance

    Returns:
        Initialized Web3 instance
    """
    logger.info(f"Connecting to RPC: {rpc_url}")
    w3 = Web3(Web3.HTTPProvider(rpc_url))

    if not w3.is_connected():
        raise ConnectionError(f"Failed to connect to Web3 provider at {rpc_url}")

    chain_id = w3.eth.chain_id
    logger.info(f"Connected to network with chain ID: {chain_id}")

    return w3
