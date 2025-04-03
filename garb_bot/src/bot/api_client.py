"""
Async API client for the Garb Bot
"""

import logging
from typing import Optional

from shared.clients.async_api_client import AsyncFoilAPIClient


class GarbApiClient(AsyncFoilAPIClient):
    """
    Async API client for the Garb Bot that extends the shared AsyncFoilAPIClient
    """

    def __init__(self, api_url: str):
        """Initialize the API client with the API URL"""
        super().__init__(api_url)

        # Configure logger with propagation disabled to prevent duplicate logs
        self.logger = logging.getLogger("ArbitrageBot.API")
        if not self.logger.handlers and self.logger.level == logging.NOTSET:
            self.logger.setLevel(logging.INFO)
            self.logger.propagate = False
