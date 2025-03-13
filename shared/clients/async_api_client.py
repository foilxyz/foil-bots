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
            ) {
                resourceTrailingAverageCandles(
                  slug: $slug
                  from: $from
                  to: $to
                  interval: $interval
                ) {
                  timestamp
                  close
                }
            }
        """
        )

        now = int(time.time())
        trailing_time = 5 * 60  # 5 minutes in seconds

        variables = {
            "slug": resource_slug,
            "from": now - trailing_time,
            "to": now,
            "interval": trailing_time,
        }

        self.logger.info(f"Fetching trailing average for {resource_slug}")
        self.logger.info(
            f"Query variables: from={variables['from']}, to={variables['to']}, interval={variables['interval']}"
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
