import time
from decimal import Decimal
from typing import Optional, TypedDict

from gql import Client, gql
from gql.transport.requests import RequestsHTTPTransport


class TrailingCandle(TypedDict):
    timestamp: int
    close: str


class FoilAPIClient:
    def __init__(self, api_url: str):
        transport = RequestsHTTPTransport(url=f"{api_url.rstrip('/')}/graphql")
        self.client = Client(transport=transport, fetch_schema_from_transport=True)

    def get_trailing_average(self, resource_slug: str) -> Optional[float]:
        """Fetch the 28-day trailing average price"""
        query = gql(
            """
            query TrailingResourceCandles(
                $slug: String!,
                $from: Int!,
                $to: Int!,
                $interval: Int!,
                $trailingTime: Int!
            ) {
                resourceTrailingAverageCandles(
                    slug: $slug
                    from: $from
                    to: $to
                    interval: $interval
                    trailingTime: $trailingTime
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

        try:
            result = self.client.execute(query, variable_values=variables)
            candles = result["resourceTrailingAverageCandles"]

            if not candles:
                return None

            # Get the latest candle
            latest_candle = max(candles, key=lambda x: x["timestamp"])

            # Convert from 9 decimal fixed-point to float
            return float(Decimal(latest_candle["close"]) / Decimal(10**9))

        except Exception as e:
            raise Exception(f"Failed to fetch trailing average: {str(e)}")
