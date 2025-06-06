import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List

from web3 import Web3

from shared.clients.async_api_client import AsyncFoilAPIClient
from shared.clients.discord_client import DiscordNotifier

from .config import BotConfig
from .foil import Foil
from .position import Position
from .strategy import FluxorStrategy


class MarketTask:
    """Represents a single market trading task"""

    def __init__(
        self,
        market_data: Dict[str, Any],
        market_group_address: str,
        collateral_asset: str,
        uniswap_position_manager: str,
        w3: Web3,
        account_address: str,
    ):
        self.market_data = market_data
        self.market_group_address = market_group_address
        self.collateral_asset = collateral_asset
        self.uniswap_position_manager = uniswap_position_manager
        self.market_id = market_data["marketId"]
        self.w3 = w3
        self.account_address = account_address
        self.logger = logging.getLogger("FluxorBot")

        # Initialize market components with API data
        self.foil = Foil(w3, market_data, market_group_address, collateral_asset, uniswap_position_manager)
        self.position = Position(account_address, self.foil, w3)
        self.strategy = FluxorStrategy(self.position, self.foil, account_address)

    async def run_strategy(self) -> None:
        """Run the strategy for this market"""
        try:
            start_time = datetime.now()
            self.logger.info(f"🚀 [Market {self.market_id}] Starting strategy run at {start_time.strftime('%H:%M:%S')}")

            # Run strategy (no longer needs market data from API client)
            self.strategy.run()

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            self.logger.info(f"✅ [Market {self.market_id}] Strategy completed in {duration:.2f}s")

        except Exception as e:
            self.logger.error(f"❌ [Market {self.market_id}] Strategy execution failed: {str(e)}")
            raise


class MarketManager:
    """Manages multiple markets and coordinates async strategy execution"""

    def __init__(self, config: BotConfig, w3: Web3, account_address: str):
        self.config = config
        self.w3 = w3
        self.account_address = account_address
        self.logger = logging.getLogger("FluxorBot")

        # Initialize API client
        self.api_client = AsyncFoilAPIClient(config.foil_api_url)

        # Initialize Discord notifier
        self.discord = DiscordNotifier.get_instance("FluxorBot", config)

        # Market tasks will be populated when run_all_markets is called
        self.market_tasks: List[MarketTask] = []

        self.logger.info("MarketManager initialized - market tasks will be created dynamically from API")

    async def _fetch_and_initialize_market_tasks(self) -> None:
        """Fetch market groups from API and initialize market tasks"""
        try:
            # Get current timestamp for filtering live markets
            current_time = str(int(time.time()))

            self.logger.info("Fetching market groups from API with parameters:")
            self.logger.info(f"- Chain ID: {self.config.chain_id}")
            self.logger.info(f"- Base Token: {self.config.base_token_name}")
            self.logger.info(f"- Current Time: {current_time}")

            # Fetch market groups from API
            result = await self.api_client.get_market_groups(
                chain_id=self.config.chain_id, current_time=current_time, base_token_name=self.config.base_token_name
            )

            market_groups = result.get("marketGroups", [])
            self.logger.info(f"Found {len(market_groups)} market groups from API")

            # Clear existing tasks
            self.market_tasks.clear()

            # Create market tasks from API data
            total_markets = 0
            for market_group in market_groups:
                group_address = market_group["address"]
                collateral_asset = market_group["collateralAsset"]
                uniswap_position_manager = market_group["marketParams"]["uniswapPositionManager"]
                markets = market_group.get("markets", [])

                self.logger.info(f"Processing market group {group_address} with {len(markets)} markets")
                self.logger.info(f"- Collateral Asset: {collateral_asset}")

                for market_data in markets:
                    try:
                        task = MarketTask(
                            market_data=market_data,
                            market_group_address=group_address,
                            collateral_asset=collateral_asset,
                            uniswap_position_manager=uniswap_position_manager,
                            w3=self.w3,
                            account_address=self.account_address,
                        )
                        self.market_tasks.append(task)
                        total_markets += 1

                        self.logger.info(
                            f"✅ Initialized market task: {market_data['marketId']} - {market_data['question'][:50]}..."
                        )
                    except Exception as e:
                        self.logger.error(
                            f"❌ Failed to initialize market {market_data.get('marketId', 'unknown')}: {str(e)}"
                        )

            self.logger.info(f"Successfully initialized {total_markets} market tasks from API")

        except Exception as e:
            self.logger.error(f"❌ Failed to fetch market groups from API: {str(e)}")
            raise

    async def run_all_markets(self) -> None:
        """Fetch markets from API and run strategies for all markets concurrently"""
        # First, fetch and initialize market tasks from API
        await self._fetch_and_initialize_market_tasks()

        if not self.market_tasks:
            self.logger.warning("No market tasks to run")
            return

        start_time = datetime.now()
        self.logger.info(f"🌐 Running strategies for {len(self.market_tasks)} markets")

        if self.discord:
            self.discord.send_message(f"🌐 Running strategies for {len(self.market_tasks)} markets")

        # Create async tasks for all markets
        tasks = []
        for market_task in self.market_tasks:
            task = asyncio.create_task(market_task.run_strategy(), name=f"{market_task.market_id}")
            tasks.append(task)

        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        successful = 0
        failed = 0
        errors = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed += 1
                market_task = self.market_tasks[i]
                error_msg = f"{market_task.market_id}: {str(result)}"
                errors.append(error_msg)
                self.logger.error(f"❌ Market task failed: {error_msg}")
            else:
                successful += 1

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Summary
        summary = f"📊 **Run Summary**\n✅ Successful: {successful}\n❌ Failed: {failed}\n⏱️ Duration: {duration:.2f}s"
        self.logger.info(
            summary.replace("**", "").replace("📊", "").replace("✅", "").replace("❌", "").replace("⏱️", "")
        )

        if self.discord:
            if errors:
                error_summary = "\n".join(errors[:5])  # Limit to first 5 errors
                if len(errors) > 5:
                    error_summary += f"\n... and {len(errors) - 5} more errors"
                summary += f"\n\n**Errors:**\n```{error_summary}```"

            self.discord.send_message(summary)

    def get_market_count(self) -> int:
        """Get total number of markets being managed"""
        return len(self.market_tasks)

    def get_markets_summary(self) -> List[int]:
        """Get list of market IDs"""
        return [task.market_id for task in self.market_tasks]
