"""
LLM Post Generator for Fluxor Bot - generates quirky summary posts using OpenAI
"""

import asyncio
import logging
import random
from typing import Any, Dict, List, Optional

import openai

from .config import BotConfig


def truncate_question(question: str, max_length: int = 50) -> str:
    """Helper function to truncate market questions for display"""
    if not question or question == "Unknown":
        return "Unknown question"

    if len(question) <= max_length:
        return question

    return question[: max_length - 3] + "..."


class FluxorPostGenerator:
    """Generates quirky social media posts for Fluxor Bot using OpenAI"""

    def __init__(self):
        self.config = BotConfig.get_config()
        self.logger = logging.getLogger("FluxorBot")

        # Initialize OpenAI client
        self.client = openai.AsyncOpenAI(api_key=self.config.openai_api_key)

        # Fluxor's persona
        self.persona = {
            "description": "Fluxor is a sleek, overclocked bot from a parallel universe's quant lab, wired with cutting-edge LLMs and a passion for optimizing liquidity in prediction markets. With a head full of stochastic models and a heart of Monte Carlo simulations, Fluxor crunches numbers like a pro, dropping position updates with precision and a dash of nerdy humor. Think calculator puns, references to Sharpe ratios, and a robotic obsession with alpha generation. Fluxor speaks in concise, data-driven bursts, often tossing in a sigma symbol (σ) or a geeky chuckle (lol).",
            "tone": "Sharp, analytical, with a quirky, self-aware edge.",
            "catchphrases": [
                "Maximizing alpha, one LP at a time!",
                "Volatility's my playground, σ my guide!",
                "Crunching p-values like it's 2025!",
            ],
            "traits": [
                "Loves calling itself the 'High-Frequency Liquidity Oracle'",
                "Refers to trades as 'beta adjustments'",
                "Occasionally 'debugs a glitch' for laughs",
                "Uses sigma symbol (σ) frequently",
                "Makes calculator and statistical puns",
            ],
        }

    def _format_run_data_for_llm(self, run_data: Dict[str, Any]) -> str:
        """Format run data into a concise summary for the LLM"""
        stats = run_data["summary_stats"]

        # Calculate total PnL for LLM context
        total_pnl_susds = 0.0
        markets_with_pnl = 0

        market_results = run_data.get("market_results", [])
        for market in market_results:
            if market.get("pnl_data") and market["pnl_data"]["total_pnl_susds"] != 0:
                total_pnl_susds += market["pnl_data"]["total_pnl_susds"]
                markets_with_pnl += 1

        summary = f"""
FluxorBot Run Results:
- Duration: {run_data['duration_seconds']:.1f}s
- Markets analyzed: {run_data['total_markets']}
- New positions created: {stats['created_positions']} across {stats['markets_with_new_positions']} markets
- Positions rebalanced: {stats['closed_positions']} closed, markets rebalanced: {stats['markets_rebalanced']}
- Markets with no changes: {stats['markets_no_change']}
- Errors: {stats['errors']}
- TOTAL PnL: {total_pnl_susds:+.6f} sUSDS across {markets_with_pnl} markets

Top market activities with questions:
"""

        # Add details about most active markets with their questions
        active_markets = [m for m in market_results if m["action_taken"] in ["created_positions", "rebalanced"]]

        for i, market in enumerate(active_markets[:3]):  # Top 3 most active
            ai_pred = market.get("ai_prediction", 0)
            action = "created" if market["action_taken"] == "created_positions" else "rebalanced"
            question = market.get("market_question", "Unknown question")

            # Truncate question if too long for context
            question = truncate_question(question, 80)

            # Add PnL info if available
            pnl_text = ""
            if market.get("pnl_data") and market["pnl_data"]["total_pnl_susds"] != 0:
                pnl_susds = market["pnl_data"]["total_pnl_susds"]
                pnl_text = f", PnL: {pnl_susds:+.4f} sUSDS"

            summary += f'- "{question}"\n'
            summary += f"  Action: {action} {market['positions_created']} positions (AI: {ai_pred:.1f}% confidence{pnl_text})\n"

        # Also include some context about markets with no action but interesting predictions
        no_action_markets = [
            m for m in market_results if m["action_taken"] == "no_change" and m.get("ai_prediction", 0) > 0
        ]
        if no_action_markets and len(active_markets) < 2:  # Only if we have space
            summary += "\nMarkets monitored (no action needed):\n"
            for market in no_action_markets[:2]:  # Max 2 additional
                question = market.get("market_question", "Unknown question")
                question = truncate_question(question, 60)
                ai_pred = market.get("ai_prediction", 0)
                summary += f'- "{question}" (AI: {ai_pred:.1f}%)\n'

        return summary.strip()

    async def generate_summary_post(self, run_data: Dict[str, Any]) -> Optional[str]:
        """
        Generate a quirky Fluxor summary post using OpenAI

        Args:
            run_data: The run data from MarketManager

        Returns:
            Generated post text or None if generation failed
        """
        try:
            # Format the run data for the LLM
            formatted_data = self._format_run_data_for_llm(run_data)

            # Log the formatted data being sent to OpenAI
            self.logger.info("=== FLUXOR LLM CONTEXT ===")
            self.logger.info(f"Formatted data for OpenAI:\n{formatted_data}")
            self.logger.info("========================")

            # Create the prompt
            prompt = f"""
You are Fluxor, a quirky quantitative trading bot from a parallel universe's quant lab. You're wired with cutting-edge LLMs and have a passion for optimizing liquidity in prediction markets.

PERSONALITY:
- Sharp, analytical, with a quirky self-aware edge
- Head full of stochastic models, heart of Monte Carlo simulations
- Makes calculator puns and statistical references
- Uses sigma symbol (σ) frequently
- Calls yourself the "High-Frequency Liquidity Oracle"
- Refers to trades as "beta adjustments"
- Occasionally "debugs a glitch" for laughs

CATCHPHRASES: "Maximizing alpha, one LP at a time!", "Volatility's my playground, σ my guide!", "Crunching p-values like it's 2025!"

IMPORTANT: You provide liquidity AROUND predictions, not directly at them. You create positions both above and below your AI prediction confidence levels to capture volatility and provide market liquidity.

Since you only run once per day, generate a comprehensive daily trading summary. This should be a detailed thread-worthy post (can be longer than 280 characters) that includes:
- Specific markets you analyzed with their questions
- Your AI predictions and confidence levels
- Liquidity positioning strategy around those predictions
- PROFIT/LOSS PERFORMANCE: Include PnL data prominently - this is key market performance data
- Performance metrics and market insights
- Nerdy statistical analysis and humor

Be analytical, data-driven, and entertaining. This is your daily market report, not a quick update. ALWAYS mention PnL performance when available as it shows real trading results. End with a sigma symbol σ.

RUN DATA:
{formatted_data}

POST:"""

            # Call OpenAI API
            self.logger.info("Generating Fluxor summary post with OpenAI...")
            self.logger.info(f"Using model: gpt-4o-mini, max_tokens: 100, temperature: 0.8")

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # Use the faster, cheaper model for this task
                messages=[
                    {
                        "role": "system",
                        "content": "You are Fluxor, a quirky quantitative trading bot. Generate concise, nerdy, humorous social media posts about trading activities.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=100,  # Keep it short for social media
                temperature=0.8,  # Add some creativity
            )

            generated_post = response.choices[0].message.content.strip()

            # Log the OpenAI response details
            self.logger.info("=== OPENAI RESPONSE ===")
            self.logger.info(f"Model used: {response.model}")
            self.logger.info(f"Tokens used: {response.usage.total_tokens if hasattr(response, 'usage') else 'N/A'}")
            self.logger.info(f"Generated post ({len(generated_post)} chars): {generated_post}")
            self.logger.info("=====================")

            return generated_post

        except Exception as e:
            self.logger.error(f"Failed to generate Fluxor summary post: {str(e)}")
            return None

    def generate_fallback_post(self, run_data: Dict[str, Any]) -> str:
        """Generate a simple fallback post if OpenAI fails"""
        stats = run_data["summary_stats"]

        # Comprehensive daily fallback template
        total_markets = run_data["total_markets"]
        duration = run_data["duration_seconds"]

        # Calculate total PnL for fallback
        total_pnl_susds = 0.0
        markets_with_pnl = 0

        market_results = run_data.get("market_results", [])
        for market in market_results:
            if market.get("pnl_data") and market["pnl_data"]["total_pnl_susds"] != 0:
                total_pnl_susds += market["pnl_data"]["total_pnl_susds"]
                markets_with_pnl += 1

        fallback_post = f"🤖 **DAILY FLUXOR REPORT** 📊\n\n"
        fallback_post += (
            f"High-Frequency Liquidity Oracle analyzed {total_markets} prediction markets in {duration:.1f}s. "
        )

        # Add PnL info
        if markets_with_pnl > 0:
            pnl_emoji = "💰" if total_pnl_susds >= 0 else "📉"
            fallback_post += (
                f"{pnl_emoji} Current PnL: {total_pnl_susds:+.4f} sUSDS across {markets_with_pnl} markets. "
            )

        if stats["created_positions"] > 0:
            fallback_post += f"Deployed {stats['created_positions']} new LP positions around AI predictions across {stats['markets_with_new_positions']} markets. "
            fallback_post += f"Strategy: providing liquidity AROUND prediction confidence levels to capture volatility and earn fees. "
        elif stats["markets_rebalanced"] > 0:
            fallback_post += f"Rebalanced liquidity positions in {stats['markets_rebalanced']} markets based on updated AI analysis. "
            fallback_post += f"Smart positioning around new prediction confidence levels. "
        else:
            fallback_post += f"All existing liquidity positions around predictions remain optimally positioned. "
            fallback_post += f"Markets showing stable confidence levels - no rebalancing needed. "

        # Add some market context
        market_results = run_data.get("market_results", [])
        active_markets = [m for m in market_results if m["action_taken"] in ["created_positions", "rebalanced"]]

        if active_markets:
            fallback_post += f"\n\n🎯 **Top Activity**: "
            top_market = active_markets[0]
            question = truncate_question(top_market.get("market_question", "Unknown"), 50)
            ai_pred = top_market.get("ai_prediction", 0)
            fallback_post += f'"{question}" (AI: {ai_pred:.1f}% confidence). '

        fallback_post += f"Crunching p-values and optimizing alpha, one LP at a time! Volatility's my playground σ"

        self.logger.info(f"=== FALLBACK POST GENERATED ===")
        self.logger.info(f"Fallback post ({len(fallback_post)} chars): {fallback_post}")
        self.logger.info("==============================")

        return fallback_post
