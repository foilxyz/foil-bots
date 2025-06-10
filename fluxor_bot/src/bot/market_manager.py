import asyncio
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, TypedDict

from web3 import Web3

from shared.clients.async_api_client import AsyncFoilAPIClient
from shared.clients.discord_client import DiscordNotifier

from .config import BotConfig
from .foil import Foil
from .llm_post_generator import FluxorPostGenerator
from .position_manager import PositionManager
from .strategy import FluxorStrategy


class MarketTaskResult(TypedDict):
    market_id: int
    market_question: str
    ai_prediction: float
    action_taken: str  # "created_positions", "rebalanced", "no_change", "error"
    positions_created: int
    positions_closed: int
    error_message: str
    execution_time_seconds: float


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
        position_manager: PositionManager,
        chain_id: int,
    ):
        self.market_data = market_data
        self.market_group_address = market_group_address
        self.collateral_asset = collateral_asset
        self.uniswap_position_manager = uniswap_position_manager
        self.market_id = market_data["marketId"]
        self.w3 = w3
        self.account_address = account_address
        self.position_manager = position_manager
        self.chain_id = chain_id
        self.logger = logging.getLogger("FluxorBot")

        # Initialize market components with API data
        self.foil = Foil(w3, market_data, market_group_address, collateral_asset, uniswap_position_manager)
        self.strategy = FluxorStrategy(self.position_manager, self.foil, account_address)

    async def run_strategy(self) -> MarketTaskResult:
        """Run the strategy for this market and return results"""
        start_time = datetime.now()
        self.logger.info(f"🚀 [Market {self.market_id}] Starting strategy run at {start_time.strftime('%H:%M:%S')}")

        # Initialize result structure
        result: MarketTaskResult = {
            "market_id": self.market_id,
            "market_question": self.market_data.get("question", "Unknown"),
            "ai_prediction": 0.0,
            "action_taken": "error",
            "positions_created": 0,
            "positions_closed": 0,
            "error_message": "",
            "execution_time_seconds": 0.0,
        }

        try:
            # Load positions for this market first
            await self.position_manager.load_positions_for_market(
                self.market_group_address, self.market_id, self.chain_id, self.foil.contract, self.foil.market_params
            )

            # Get AI prediction if available
            if hasattr(self.foil, "ai_prediction") and self.foil.ai_prediction is not None:
                result["ai_prediction"] = self.foil.ai_prediction

            # Run strategy with loaded positions and collect results
            strategy_result = await self.strategy.run()
            if strategy_result:
                result.update(strategy_result)

            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            result["execution_time_seconds"] = duration

            self.logger.info(f"✅ [Market {self.market_id}] Strategy completed in {duration:.2f}s")

            return result

        except Exception as e:
            end_time = datetime.now()
            duration = (end_time - start_time).total_seconds()
            result["execution_time_seconds"] = duration
            result["error_message"] = str(e)
            result["action_taken"] = "error"

            self.logger.error(f"❌ [Market {self.market_id}] Strategy execution failed: {str(e)}")
            return result


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

        # Initialize position manager (shared across all markets)
        self.position_manager = PositionManager(w3, account_address, self.api_client)

        # Initialize LLM post generator
        self.post_generator = FluxorPostGenerator()

        # Market tasks will be populated when run_all_markets is called
        self.market_tasks: List[MarketTask] = []

        self.logger.info(
            "MarketManager initialized with shared PositionManager - market tasks will be created dynamically from API"
        )

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
                            position_manager=self.position_manager,
                            chain_id=self.config.chain_id,
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

        # Create async tasks for all markets
        tasks = []
        for market_task in self.market_tasks:
            task = asyncio.create_task(market_task.run_strategy(), name=f"{market_task.market_id}")
            tasks.append(task)

        # Wait for all tasks to complete and collect results
        results = await asyncio.gather(*tasks, return_exceptions=False)

        # Process results and build summary
        successful = 0
        failed = 0
        errors = []
        market_summaries = []

        for i, result in enumerate(results):
            if isinstance(result, Exception):
                failed += 1
                market_task = self.market_tasks[i]
                error_msg = f"{market_task.market_id}: {str(result)}"
                errors.append(error_msg)
                self.logger.error(f"❌ Market task failed: {error_msg}")
            else:
                # Process MarketTaskResult
                if result["action_taken"] == "error":
                    failed += 1
                    errors.append(f"{result['market_id']}: {result['error_message']}")
                else:
                    successful += 1

                # Add to market summaries for Discord
                market_summaries.append(result)

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        # Build comprehensive summary
        summary_text = self._build_discord_summary(successful, failed, duration, market_summaries, errors)

        # Log summary (without Discord formatting)
        log_summary = f"Run Summary - Successful: {successful}, Failed: {failed}, Duration: {duration:.2f}s"
        self.logger.info(log_summary)

        # Send to Discord
        if self.discord:
            self.discord.send_message(summary_text)

            # Generate and send Fluxor's quirky summary post
            await self._generate_and_send_fluxor_post(market_summaries, duration)

    def _build_discord_summary(
        self, successful: int, failed: int, duration: float, market_summaries: List[MarketTaskResult], errors: List[str]
    ) -> str:
        """Build a comprehensive Discord summary of the market run"""

        # Header
        summary = f"📊 **FluxorBot Run Summary**\n"
        summary += f"✅ Successful: {successful} | ❌ Failed: {failed} | ⏱️ Duration: {duration:.2f}s\n\n"

        # Group markets by action taken
        created_markets = [m for m in market_summaries if m["action_taken"] == "created_positions"]
        rebalanced_markets = [m for m in market_summaries if m["action_taken"] == "rebalanced"]
        no_change_markets = [m for m in market_summaries if m["action_taken"] == "no_change"]

        # Position creation summary
        if created_markets:
            total_created = sum(m["positions_created"] for m in created_markets)
            summary += f"🆕 **New Positions Created** ({len(created_markets)} markets, {total_created} positions)\n"
            for market in created_markets[:3]:  # Show first 3
                summary += f"• Market {market['market_id']}: {market['positions_created']} pos, {market['ai_prediction']:.1f}% prediction\n"
            if len(created_markets) > 3:
                summary += f"... and {len(created_markets) - 3} more\n"
            summary += "\n"

        # Rebalancing summary
        if rebalanced_markets:
            total_closed = sum(m["positions_closed"] for m in rebalanced_markets)
            total_created = sum(m["positions_created"] for m in rebalanced_markets)
            summary += f"🔄 **Rebalanced** ({len(rebalanced_markets)} markets, {total_closed} closed, {total_created} created)\n"
            for market in rebalanced_markets[:3]:  # Show first 3
                summary += f"• Market {market['market_id']}: {market['positions_closed']}→{market['positions_created']}, {market['ai_prediction']:.1f}% prediction\n"
            if len(rebalanced_markets) > 3:
                summary += f"... and {len(rebalanced_markets) - 3} more\n"
            summary += "\n"

        # No change summary
        if no_change_markets:
            summary += f"✅ **No Changes** ({len(no_change_markets)} markets kept existing positions)\n\n"

        # Error summary
        if errors:
            summary += f"❌ **Errors** ({len(errors)})\n"
            for error in errors[:3]:  # Show first 3 errors
                summary += f"• {error}\n"
            if len(errors) > 3:
                summary += f"... and {len(errors) - 3} more errors\n"

        # Store detailed results for future LLM processing
        self._store_run_data(market_summaries, duration)

        return summary

    def _store_run_data(self, market_summaries: List[MarketTaskResult], duration: float) -> None:
        """Store run data for future LLM tweet generation"""
        run_data = {
            "timestamp": datetime.now().isoformat(),
            "duration_seconds": duration,
            "total_markets": len(market_summaries),
            "market_results": market_summaries,
            "summary_stats": {
                "created_positions": sum(m["positions_created"] for m in market_summaries),
                "closed_positions": sum(m["positions_closed"] for m in market_summaries),
                "markets_with_new_positions": len(
                    [m for m in market_summaries if m["action_taken"] == "created_positions"]
                ),
                "markets_rebalanced": len([m for m in market_summaries if m["action_taken"] == "rebalanced"]),
                "markets_no_change": len([m for m in market_summaries if m["action_taken"] == "no_change"]),
                "errors": len([m for m in market_summaries if m["action_taken"] == "error"]),
            },
        }

        # Store in instance variable for now (could be saved to file/DB later)
        if not hasattr(self, "run_history"):
            self.run_history = []
        self.run_history.append(run_data)

        # Keep only last 100 runs to avoid memory issues
        if len(self.run_history) > 100:
            self.run_history = self.run_history[-100:]

        self.logger.info(f"Stored run data: {len(market_summaries)} markets, {run_data['summary_stats']}")

    async def _generate_and_send_fluxor_post(self, market_summaries: List[MarketTaskResult], duration: float) -> None:
        """Generate and send Fluxor's quirky summary post to Discord"""
        try:
            # Get the latest run data
            run_data = self.get_latest_run_data()
            if not run_data:
                self.logger.warning("No run data available for Fluxor post generation")
                return

            # Generate the post
            fluxor_post = await self.post_generator.generate_summary_post(run_data)

            # Fallback to template-based post if LLM fails
            if not fluxor_post:
                self.logger.info("OpenAI generation failed, using fallback post")
                fluxor_post = self.post_generator.generate_fallback_post(run_data)

            # Send to Discord with special formatting
            fluxor_message = f"🤖 **Fluxor's Summary Post**\n\n{fluxor_post}"
            self.discord.send_message(fluxor_message)

            self.logger.info("Fluxor summary post sent to Discord")

        except Exception as e:
            self.logger.error(f"Failed to generate/send Fluxor post: {str(e)}")

    def get_latest_run_data(self) -> Optional[Dict]:
        """Get the latest run data for LLM processing"""
        if hasattr(self, "run_history") and self.run_history:
            return self.run_history[-1]
        return None

    def get_run_history(self, limit: int = 10) -> List[Dict]:
        """Get recent run history for LLM processing"""
        if not hasattr(self, "run_history"):
            return []
        return self.run_history[-limit:] if limit > 0 else self.run_history

    def get_market_count(self) -> int:
        """Get total number of markets being managed"""
        return len(self.market_tasks)

    def get_markets_summary(self) -> List[int]:
        """Get list of market IDs"""
        return [task.market_id for task in self.market_tasks]
