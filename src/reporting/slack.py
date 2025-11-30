"""
Slack Client Module

Provides SlackClient class for sending messages to Slack via webhooks,
with rate limiting, retry logic, and mock mode support.
"""

import asyncio
import time
from typing import Dict, Optional
from datetime import datetime

import aiohttp

from config.settings import settings
from src.utils.logging import get_logger
from .formatter import SlackFormatter


logger = get_logger(__name__)


class SlackClient:
    """
    Async Slack client for sending messages via webhooks.

    Features:
    - Rate limiting (1 message per second)
    - Retry logic with exponential backoff
    - Mock mode support (logs instead of sending)
    - Error handling and logging
    """

    def __init__(self, webhook_url: Optional[str] = None):
        """
        Initialize Slack client.

        Args:
            webhook_url: Slack webhook URL (defaults to settings.slack_webhook_url)
        """
        self.webhook_url = webhook_url or settings.slack_webhook_url
        self.formatter = SlackFormatter()
        self.last_message_time = 0
        self.rate_limit_delay = 1.0  # 1 message per second
        self.max_retries = 3
        self.initial_retry_delay = 1.0  # Initial delay in seconds

        logger.info(
            f"SlackClient initialized (mock_mode={settings.mock_mode})"
        )

    async def send_message(self, blocks: Dict) -> bool:
        """
        Send message to Slack via webhook.

        Args:
            blocks: Dictionary containing Slack Block Kit formatted message

        Returns:
            True if message was sent successfully, False otherwise
        """
        # Mock mode - just log the message
        if settings.mock_mode:
            logger.info(
                f"[MOCK MODE] Would send Slack message",
                extra={'extra_fields': {'blocks': blocks}}
            )
            return True

        # Validate webhook URL
        if not self.webhook_url:
            logger.error("Slack webhook URL not configured")
            return False

        # Rate limiting - ensure 1 second between messages
        await self._enforce_rate_limit()

        # Send with retry logic
        for attempt in range(self.max_retries):
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.post(
                        self.webhook_url,
                        json=blocks,
                        timeout=aiohttp.ClientTimeout(total=10)
                    ) as response:
                        if response.status == 200:
                            logger.info("Slack message sent successfully")
                            self.last_message_time = time.time()
                            return True
                        elif response.status == 429:
                            # Rate limited by Slack
                            retry_after = int(response.headers.get('Retry-After', 60))
                            logger.warning(
                                f"Slack rate limit hit, retry after {retry_after}s"
                            )
                            if attempt < self.max_retries - 1:
                                await asyncio.sleep(retry_after)
                                continue
                        else:
                            error_text = await response.text()
                            logger.error(
                                f"Failed to send Slack message: {response.status}",
                                extra={'extra_fields': {
                                    'status': response.status,
                                    'error': error_text
                                }}
                            )

            except asyncio.TimeoutError:
                logger.warning(
                    f"Slack webhook timeout (attempt {attempt + 1}/{self.max_retries})"
                )
            except aiohttp.ClientError as e:
                logger.warning(
                    f"Slack webhook client error: {e} (attempt {attempt + 1}/{self.max_retries})"
                )
            except Exception as e:
                logger.error(
                    f"Unexpected error sending Slack message: {e}",
                    exc_info=True
                )

            # Exponential backoff for retries
            if attempt < self.max_retries - 1:
                delay = self.initial_retry_delay * (2 ** attempt)
                logger.info(f"Retrying in {delay}s...")
                await asyncio.sleep(delay)

        logger.error(
            f"Failed to send Slack message after {self.max_retries} attempts"
        )
        return False

    async def _enforce_rate_limit(self):
        """
        Enforce rate limit of 1 message per second.

        Waits if necessary to maintain rate limit.
        """
        if self.last_message_time > 0:
            time_since_last = time.time() - self.last_message_time
            if time_since_last < self.rate_limit_delay:
                wait_time = self.rate_limit_delay - time_since_last
                logger.debug(f"Rate limiting: waiting {wait_time:.2f}s")
                await asyncio.sleep(wait_time)

    async def send_portfolio_update(
        self,
        portfolio_data: Dict,
        pnl_data: Dict
    ) -> bool:
        """
        Format and send portfolio update message.

        Args:
            portfolio_data: Dictionary containing portfolio information
            pnl_data: Dictionary containing P&L information

        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            logger.info("Sending portfolio update to Slack")
            blocks = self.formatter.format_portfolio_update(
                portfolio_data,
                pnl_data
            )
            return await self.send_message(blocks)

        except Exception as e:
            logger.error(
                f"Error formatting portfolio update: {e}",
                exc_info=True
            )
            return False

    async def send_alert(
        self,
        alert_type: str,
        message: str,
        data: Dict
    ) -> bool:
        """
        Format and send alert message.

        Args:
            alert_type: Type of alert (price_change, error, significant_movement)
            message: Alert message text
            data: Additional data relevant to the alert

        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            logger.info(
                f"Sending alert to Slack: {alert_type}",
                extra={'extra_fields': {'alert_type': alert_type}}
            )
            blocks = self.formatter.format_alert(alert_type, message, data)
            return await self.send_message(blocks)

        except Exception as e:
            logger.error(
                f"Error formatting alert: {e}",
                exc_info=True
            )
            return False

    async def send_error(
        self,
        error: Exception,
        context: Dict
    ) -> bool:
        """
        Format and send error notification.

        Args:
            error: Exception object
            context: Dictionary containing error context

        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            logger.info(
                "Sending error notification to Slack",
                extra={'extra_fields': {'error_type': type(error).__name__}}
            )
            blocks = self.formatter.format_error_notification(error, context)
            return await self.send_message(blocks)

        except Exception as e:
            logger.error(
                f"Error formatting error notification: {e}",
                exc_info=True
            )
            return False

    async def send_daily_summary(
        self,
        portfolio_data: Dict,
        pnl_data: Dict,
        stats: Dict
    ) -> bool:
        """
        Format and send daily summary message.

        Args:
            portfolio_data: Dictionary containing portfolio information
            pnl_data: Dictionary containing P&L information
            stats: Dictionary containing additional statistics

        Returns:
            True if message was sent successfully, False otherwise
        """
        try:
            logger.info("Sending daily summary to Slack")
            blocks = self.formatter.format_daily_summary(
                portfolio_data,
                pnl_data,
                stats
            )
            return await self.send_message(blocks)

        except Exception as e:
            logger.error(
                f"Error formatting daily summary: {e}",
                exc_info=True
            )
            return False


# Convenience function to get a configured SlackClient instance
def get_slack_client(webhook_url: Optional[str] = None) -> SlackClient:
    """
    Get a configured SlackClient instance.

    Args:
        webhook_url: Optional webhook URL (defaults to settings)

    Returns:
        Configured SlackClient instance
    """
    return SlackClient(webhook_url=webhook_url)
