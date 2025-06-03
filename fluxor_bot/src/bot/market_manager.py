import asyncio
import logging
from datetime import datetime
from typing import List

from web3 import Web3

from shared.clients.discord_client import DiscordNotifier

from .config import BotConfig
from .foil import Foil
from .position import Position
from .strategy import FluxorStrategy


class MarketTask:
    """Represents a single market trading task"""

    def __init__(self, market_group_address: str, market_id: int, w3: Web3, account_address: str):
        self.market_group_address = market_group_address
        self.market_id = market_id
        self.w3 = w3
        self.account_address = account_address
        self.logger = logging.getLogger(f"FluxorBot-{market_id}")

        # Create a simple market config object for the components
        self.market_config = type(
            "MarketConfig", (), {"market_id": market_id, "market_group_address": market_group_address}
        )()

        # Initialize market components
        self.foil = Foil(w3, self.market_config)
        self.position = Position(account_address, self.foil, w3)
        self.strategy = FluxorStrategy(self.position, self.foil, account_address)

    async def run_strategy(self) -> None:
        """Run the strategy for this market"""
        try:
            start_time = datetime.now()
            self.logger.info(f"🚀 Starting strategy run at {start_time.strftime('%H:%M:%S')}")

            # Run strategy (no longer needs market data from API client)
            self.strategy.run()

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            self.logger.info(f"✅ Strategy completed in {duration:.2f}s")

        except Exception as e:
            self.logger.error(f"❌ Strategy execution failed: {str(e)}")
            raise


class MarketManager:
    """Manages multiple markets and coordinates async strategy execution"""

    def __init__(self, config: BotConfig, w3: Web3, account_address: str):
        self.config = config
        self.w3 = w3
        self.account_address = account_address
        self.logger = logging.getLogger("FluxorBot")

        # Initialize Discord notifier
        self.discord = DiscordNotifier.get_instance("FluxorBot", config)

        # Create market tasks
        self.market_tasks: List[MarketTask] = []
        self._initialize_market_tasks()

        self.logger.info(f"Initialized {len(self.market_tasks)} market tasks")

    def _initialize_market_tasks(self) -> None:
        """Initialize market tasks from configuration"""
        for market_group in self.config.market_groups:
            for market_id in market_group.market_ids:
                try:
                    task = MarketTask(market_group.market_group_address, market_id, self.w3, self.account_address)
                    self.market_tasks.append(task)
                    self.logger.info(
                        f"✅ Initialized market task: {market_id} (Group: {market_group.market_group_address})"
                    )
                except Exception as e:
                    self.logger.error(f"❌ Failed to initialize market {market_id}: {str(e)}")

    async def run_all_markets(self) -> None:
        """Run strategies for all markets concurrently"""
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
