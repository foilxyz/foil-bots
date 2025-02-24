import logging
import math
from decimal import Decimal
from typing import Any, Callable, Union

from web3 import Web3
from web3.exceptions import TimeExhausted, TransactionNotFound
from web3.types import TxReceipt


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
        **kwargs: Additional transaction parameters

    Returns:
        Transaction receipt
    """
    try:
        # Gas estimation
        gas_estimate = contract_fn(*args).estimate_gas({"from": account_address})
        base_fee = w3.eth.get_block("latest")["baseFeePerGas"]
        priority_fee = w3.eth.max_priority_fee
        max_fee = base_fee + priority_fee * 2  # Dynamic buffer

        # Build transaction
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
