"""
X (Twitter) Client for FluxorBot - posts AI-generated summaries to X
"""

import logging
from typing import Optional

import tweepy

from .config import BotConfig


class XClient:
    """Posts Fluxor's quirky AI-generated summaries to X (Twitter)"""

    def __init__(self):
        self.config = BotConfig.get_config()
        self.logger = logging.getLogger("FluxorBot")
        self.api: Optional[tweepy.API] = None
        self.client: Optional[tweepy.Client] = None

        # Initialize X API if credentials are provided
        self._initialize_client()

    def _initialize_client(self) -> None:
        """Initialize X API client with authentication"""
        try:
            # Check if we have the required credentials
            if not all(
                [
                    self.config.x_api_key,
                    self.config.x_api_secret,
                    self.config.x_access_token,
                    self.config.x_access_token_secret,
                ]
            ):
                self.logger.info("X API credentials not provided - X integration disabled")
                return

            # Initialize OAuth 1.0a authentication for posting
            auth = tweepy.OAuth1UserHandler(
                consumer_key=self.config.x_api_key,
                consumer_secret=self.config.x_api_secret,
                access_token=self.config.x_access_token,
                access_token_secret=self.config.x_access_token_secret,
            )

            # Initialize API v1.1 for legacy features (if needed)
            self.api = tweepy.API(auth, wait_on_rate_limit=True)

            # Initialize Client v2 for modern posting
            self.client = tweepy.Client(
                consumer_key=self.config.x_api_key,
                consumer_secret=self.config.x_api_secret,
                access_token=self.config.x_access_token,
                access_token_secret=self.config.x_access_token_secret,
                bearer_token=self.config.x_bearer_token,
                wait_on_rate_limit=True,
            )

            # Test authentication
            if self.client:
                user = self.client.get_me()
                if user and user.data:
                    self.logger.info(f"✅ X client initialized successfully for @{user.data.username}")
                else:
                    self.logger.warning("X client initialized but user verification failed")
            else:
                self.logger.warning("X client initialization failed")

        except Exception as e:
            self.logger.error(f"Failed to initialize X client: {str(e)}")
            self.api = None
            self.client = None

    def is_enabled(self) -> bool:
        """Check if X integration is enabled and working"""
        return self.client is not None

    def _split_into_tweets(self, content: str) -> list[str]:
        """Split long content into tweet-sized chunks for threading"""
        if len(content) <= 270:  # Leave room for thread indicators
            return [content]

        # Split content into sentences
        sentences = content.replace(". ", ".|").replace("! ", "!|").replace("? ", "?|").split("|")
        tweets = []
        current_tweet = ""

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # Check if adding this sentence would exceed limit
            potential_tweet = f"{current_tweet} {sentence}".strip()

            if len(potential_tweet) <= 270:  # Leave room for thread numbering
                current_tweet = potential_tweet
            else:
                # Current tweet is full, start a new one
                if current_tweet:
                    tweets.append(current_tweet)
                current_tweet = sentence

        # Add the last tweet
        if current_tweet:
            tweets.append(current_tweet)

        # Add thread numbering if multiple tweets
        if len(tweets) > 1:
            numbered_tweets = []
            for i, tweet in enumerate(tweets, 1):
                if i == 1:
                    numbered_tweets.append(f"{tweet} (1/{len(tweets)})")
                else:
                    numbered_tweets.append(f"({i}/{len(tweets)}) {tweet}")
            return numbered_tweets

        return tweets

    def post_tweet(self, content: str) -> bool:
        """
        Post a tweet to X (handles long content by creating threads)

        Args:
            content: The tweet content (can be longer than 280 characters)

        Returns:
            True if posted successfully, False otherwise
        """
        if not self.is_enabled():
            self.logger.warning("X client not enabled - cannot post tweet")
            return False

        try:
            # Split content into tweet-sized chunks
            tweet_parts = self._split_into_tweets(content)

            self.logger.info(f"Posting {len(tweet_parts)} tweet(s) to X...")

            previous_tweet_id = None

            for i, tweet_content in enumerate(tweet_parts):
                self.logger.info(f"Tweet {i+1}/{len(tweet_parts)} ({len(tweet_content)} chars): {tweet_content}")

                # Post tweet as reply to previous if it's part of a thread
                if previous_tweet_id:
                    response = self.client.create_tweet(text=tweet_content, in_reply_to_tweet_id=previous_tweet_id)
                else:
                    response = self.client.create_tweet(text=tweet_content)

                if response.data:
                    tweet_id = response.data["id"]
                    previous_tweet_id = tweet_id
                    self.logger.info(f"✅ Tweet {i+1} posted: https://x.com/i/status/{tweet_id}")
                else:
                    self.logger.error(f"Failed to post tweet {i+1} - no response data")
                    return False

            if len(tweet_parts) > 1:
                self.logger.info(f"✅ Successfully posted tweet thread with {len(tweet_parts)} tweets")
            else:
                self.logger.info("✅ Successfully posted single tweet")

            return True

        except tweepy.TooManyRequests:
            self.logger.error("❌ Rate limited by X API - tweet not posted")
            return False
        except tweepy.Forbidden as e:
            self.logger.error(f"❌ X API access forbidden: {str(e)}")
            return False
        except tweepy.Unauthorized as e:
            self.logger.error(f"❌ X API unauthorized: {str(e)}")
            return False
        except Exception as e:
            self.logger.error(f"❌ Failed to post tweet: {str(e)}")
            return False

    def post_fluxor_summary(self, ai_generated_content: str) -> bool:
        """
        Post Fluxor's AI-generated summary to X

        Args:
            ai_generated_content: The AI-generated post content

        Returns:
            True if posted successfully, False otherwise
        """
        if not ai_generated_content:
            self.logger.warning("No AI-generated content provided for X post")
            return False

        # Add Fluxor branding to the post
        branded_content = f"🤖 {ai_generated_content}"

        return self.post_tweet(branded_content)

    def get_rate_limit_status(self) -> dict:
        """Get current rate limit status for debugging"""
        if not self.api:
            return {"error": "X API not initialized"}

        try:
            rate_limit = self.api.get_rate_limit_status()
            return {
                "tweets": rate_limit["resources"]["statuses"]["/statuses/update"],
                "user_timeline": rate_limit["resources"]["statuses"]["/statuses/user_timeline"],
            }
        except Exception as e:
            return {"error": str(e)}
