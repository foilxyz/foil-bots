"""
LLM Post Generator for Fluxor Bot - generates quirky summary posts using OpenAI
"""

import json
import logging
from typing import Any, Dict, List, Optional

from openai import OpenAI

from .config import BotConfig


class FluxorPostGenerator:
    """Generates quirky social media posts for Fluxor Bot using OpenAI"""

    def __init__(self):
        self.config = BotConfig.get_config()
        self.logger = logging.getLogger("FluxorBot")

        # Initialize OpenAI client
        self.client = OpenAI(api_key=self.config.openai_api_key)

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

        summary = f"""
FluxorBot Run Results:
- Duration: {run_data['duration_seconds']:.1f}s
- Markets analyzed: {run_data['total_markets']}
- New positions created: {stats['created_positions']} across {stats['markets_with_new_positions']} markets
- Positions rebalanced: {stats['closed_positions']} closed, markets rebalanced: {stats['markets_rebalanced']}
- Markets with no changes: {stats['markets_no_change']}
- Errors: {stats['errors']}

Top market activities with questions:
"""

        # Add details about most active markets with their questions
        market_results = run_data.get("market_results", [])
        active_markets = [m for m in market_results if m["action_taken"] in ["created_positions", "rebalanced"]]

        for i, market in enumerate(active_markets[:3]):  # Top 3 most active
            ai_pred = market.get("ai_prediction", 0)
            action = "created" if market["action_taken"] == "created_positions" else "rebalanced"
            question = market.get("market_question", "Unknown question")

            # Truncate question if too long for context
            if len(question) > 80:
                question = question[:77] + "..."

            summary += f"- Market {market['market_id']}: \"{question}\"\n"
            summary += f"  Action: {action} {market['positions_created']} positions (AI: {ai_pred:.1f}% confidence)\n"

        # Also include some context about markets with no action but interesting predictions
        no_action_markets = [
            m for m in market_results if m["action_taken"] == "no_change" and m.get("ai_prediction", 0) > 0
        ]
        if no_action_markets and len(active_markets) < 2:  # Only if we have space
            summary += "\nMarkets monitored (no action needed):\n"
            for market in no_action_markets[:2]:  # Max 2 additional
                question = market.get("market_question", "Unknown question")
                if len(question) > 60:
                    question = question[:57] + "..."
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

Generate a quirky social media post (under 280 characters) summarizing your latest trading run. Be concise, data-driven, and include some nerdy humor. End with a sigma symbol σ.

RUN DATA:
{formatted_data}

POST:"""

            # Call OpenAI API
            self.logger.info("Generating Fluxor summary post with OpenAI...")
            self.logger.info(f"Using model: gpt-4o-mini, max_tokens: 100, temperature: 0.8")

            response = self.client.chat.completions.create(
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

        # Simple template-based fallback
        fallback_post = ""
        if stats["created_positions"] > 0:
            fallback_post = f"🤖 High-Frequency Liquidity Oracle deployed {stats['created_positions']} new positions across {stats['markets_with_new_positions']} markets! Beta adjustments complete σ"
        elif stats["markets_rebalanced"] > 0:
            fallback_post = f"⚡ Rebalanced {stats['markets_rebalanced']} markets in {run_data['duration_seconds']:.1f}s - volatility's my playground! σ"
        else:
            fallback_post = f"📊 Analyzed {run_data['total_markets']} markets, all positions optimal. Sometimes the best trade is no trade σ"

        self.logger.info(f"=== FALLBACK POST GENERATED ===")
        self.logger.info(f"Fallback post ({len(fallback_post)} chars): {fallback_post}")
        self.logger.info("==============================")

        return fallback_post
