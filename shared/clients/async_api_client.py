"""
Async GraphQL API client for Foil
"""

import logging
import time
from decimal import Decimal
from typing import Any, Dict, Optional, TypedDict

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError
from web3 import Web3


class TrailingCandle(TypedDict):
    timestamp: int
    close: str


class AsyncFoilAPIClient:
    """Async GraphQL client for the Foil API"""

    def __init__(self, api_url: str):
        """Initialize the async GraphQL client"""
        transport = AIOHTTPTransport(url=f"{api_url.rstrip('/')}/graphql")
        self.client = Client(transport=transport, fetch_schema_from_transport=True)
        self.logger = logging.getLogger("FoilBot.API")

    async def get_trailing_average(self, resource_slug: str) -> Optional[float]:
        """
        Asynchronously fetch the trailing average price

        Args:
            resource_slug: The resource identifier

        Returns:
            The trailing average price as a float or None if not available
        """
        query = gql(
            """
            query TrailingResourceCandles(
                $slug: String!
                $from: Int!
                $to: Int!
                $interval: Int!
                $trailingAvgTime: Int!
            ) {
                resourceTrailingAverageCandles(
                  slug: $slug
                  from: $from
                  to: $to
                  interval: $interval
                  trailingAvgTime: $trailingAvgTime
                ) {
                  timestamp
                  close
                }
            }
        """
        )

        now = int(time.time())
        trailing_time = 5 * 60  # 5 minutes in seconds
        trailing_avg_time = 28 * 24 * 60 * 60  # 28 days in seconds

        variables = {
            "slug": resource_slug,
            "from": now - trailing_time,
            "to": now,
            "interval": trailing_time,
            "trailingAvgTime": trailing_avg_time,
        }

        self.logger.info(f"Fetching trailing average for {resource_slug}")
        self.logger.info(
            f"Query variables: from={variables['from']}, to={variables['to']}, "
            f"interval={variables['interval']}, trailingAvgTime={variables['trailingAvgTime']}"
        )

        try:
            # Execute the query asynchronously
            result = await self.client.execute_async(query, variable_values=variables)
            candles = result["resourceTrailingAverageCandles"]

            if not candles:
                return None

            # Get the latest candle
            latest_candle = max(candles, key=lambda x: x["timestamp"])

            # Convert from 9 decimal fixed-point to float
            return float(Decimal(latest_candle["close"]) / Decimal(10**9))

        except TransportQueryError as e:
            error_message = str(e)
            self.logger.error(f"GraphQL query error: {error_message}")
            if hasattr(e, "errors") and e.errors:
                for err in e.errors:
                    self.logger.error(f"GraphQL error details: {err}")
            raise Exception(f"Failed to fetch trailing average: {error_message}")
        except Exception as e:
            self.logger.error(f"API client error: {str(e)}")
            raise Exception(f"Failed to fetch trailing average: {str(e)}")

    async def get_market_groups(self, chain_id: int, current_time: str, base_token_name: str) -> Dict[str, Any]:
        """
        Asynchronously fetch market groups

        Args:
            chain_id: The blockchain chain ID
            current_time: Current timestamp to filter markets
            base_token_name: The base token name

        Returns:
            The market groups data as a dictionary with checksummed addresses
        """
        query = gql(
            """
            query GetMarketGroups($chainId: Int!, $currentTime: String!, $baseTokenName: String!) {
              marketGroups(
                chainId: $chainId,
                baseTokenName: $baseTokenName
              ) {
                address
                question
                collateralAsset
                marketParams {
                  uniswapPositionManager
                }
                markets(
                  filter: { 
                    endTimestamp_gt: $currentTime, # Market ends in the future
                  }
                ) {
                  question
                  marketId
                  endTimestamp
                  public
                  baseAssetMaxPriceTick
                  baseAssetMinPriceTick
                }
              }
            }
            """
        )

        variables = {
            "chainId": chain_id,
            "currentTime": current_time,
            "baseTokenName": base_token_name,
        }

        self.logger.info(
            f"Query variables: "
            f"chainId={variables['chainId']}, currentTime={variables['currentTime']}, "
            f"baseTokenName={variables['baseTokenName']}"
        )

        try:
            # Execute the query asynchronously
            result = await self.client.execute_async(query, variable_values=variables)

            # Checksum all addresses in the result
            self._checksum_addresses_in_result(result)

            return result

        except TransportQueryError as e:
            error_message = str(e)
            self.logger.error(f"GraphQL query error: {error_message}")
            if hasattr(e, "errors") and e.errors:
                for err in e.errors:
                    self.logger.error(f"GraphQL error details: {err}")
            raise Exception(f"Failed to fetch market groups: {error_message}")
        except Exception as e:
            self.logger.error(f"API client error: {str(e)}")
            raise Exception(f"Failed to fetch market groups: {str(e)}")

    def _checksum_addresses_in_result(self, result: Dict[str, Any]) -> None:
        """
        Checksum all address fields in the API result in-place

        Args:
            result: The API result dictionary to modify
        """
        if "marketGroups" in result:
            for market_group in result["marketGroups"]:
                # Checksum market group address
                if market_group.get("address"):
                    market_group["address"] = Web3.to_checksum_address(market_group["address"])

                # Checksum collateral asset address
                if "collateralAsset" in market_group and market_group["collateralAsset"]:
                    market_group["collateralAsset"] = Web3.to_checksum_address(market_group["collateralAsset"])

                # Checksum uniswap position manager address
                if "marketParams" in market_group and market_group["marketParams"]:
                    if (
                        "uniswapPositionManager" in market_group["marketParams"]
                        and market_group["marketParams"]["uniswapPositionManager"]
                    ):
                        market_group["marketParams"]["uniswapPositionManager"] = Web3.to_checksum_address(
                            market_group["marketParams"]["uniswapPositionManager"]
                        )

    async def query_async(self, query_string: str, variables: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Execute a custom GraphQL query asynchronously

        Args:
            query_string: The GraphQL query string
            variables: Optional query variables

        Returns:
            The query result as a dictionary
        """
        if variables is None:
            variables = {}

        try:
            query = gql(query_string)
            result = await self.client.execute_async(query, variable_values=variables)
            return result
        except Exception as e:
            self.logger.error(f"Failed to execute GraphQL query: {str(e)}")
            raise
