import logging
import re
from typing import Optional

try:
    import openai
except ImportError:
    openai = None


class OpenAIPredictor:
    """Utility for getting prediction market likelihood estimates from OpenAI"""

    def __init__(self, api_key: str):
        if not openai:
            raise ImportError("openai package not installed. Run: pip install openai")

        self.client = openai.OpenAI(api_key=api_key)
        self.logger = logging.getLogger("OpenAIPredictor")

    def get_prediction_likelihood(self, claim_statement: str) -> Optional[float]:
        """
        Get likelihood percentage (0-100) that a claim statement will resolve to 1

        Args:
            claim_statement: The prediction market claim statement

        Returns:
            Float between 0-100 representing likelihood percentage, or None if failed
        """
        try:
            prompt = self._build_prediction_prompt(claim_statement)

            response = self.client.chat.completions.create(
                model="gpt-4o-mini",  # Use the cheaper model for this task
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert analyst providing likelihood estimates for prediction markets. Always respond with just a number between 0-100 representing the percentage likelihood.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=50,
                temperature=0.1,  # Low temperature for more consistent responses
            )

            # Extract percentage from response
            response_text = response.choices[0].message.content.strip()
            percentage = self._extract_percentage(response_text)

            if percentage is not None:
                self.logger.info(f"Prediction for '{claim_statement[:50]}...': {percentage}%")
                return percentage
            else:
                self.logger.warning(f"Could not extract percentage from response: {response_text}")
                return None

        except Exception as e:
            self.logger.error(f"Error getting prediction: {str(e)}")
            return None

    def _build_prediction_prompt(self, claim_statement: str) -> str:
        """Build the prompt for the OpenAI API"""
        return f"""
Analyze this prediction market claim and provide the likelihood (as a percentage from 0-100) that it will resolve to 1 (true):

CLAIM: {claim_statement}

Consider:
- Current events and trends
- Historical patterns
- Available data and context
- Economic indicators if relevant
- Your knowledge cutoff limitations

Respond with ONLY a number between 0-100 representing the percentage likelihood that this claim will resolve to 1.

Examples:
- If very unlikely to happen: respond with a low number like "15"
- If very likely to happen: respond with a high number like "85" 
- If uncertain/50-50: respond with "50"

Your response:"""

    def _extract_percentage(self, response_text: str) -> Optional[float]:
        """Extract percentage number from OpenAI response"""
        # Look for numbers in the response
        numbers = re.findall(r"\b(\d+(?:\.\d+)?)\b", response_text)

        if not numbers:
            return None

        # Take the first number found
        try:
            percentage = float(numbers[0])
            # Ensure it's in valid range
            if 0 <= percentage <= 100:
                return percentage
            else:
                # If number is outside 0-100, try to normalize
                if percentage > 100:
                    return min(percentage, 100.0)
                else:
                    return max(percentage, 0.0)
        except ValueError:
            return None
