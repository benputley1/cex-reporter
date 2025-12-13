"""
Price Repository Module

Handles price tracking, market data, and price change detection.
"""

from datetime import datetime, timedelta
from typing import Optional, List, Tuple, Dict, Any

from src.data.coingecko_client import CoinGeckoClient
from src.utils import get_logger

logger = get_logger(__name__)


class PriceRepository:
    """Repository for price tracking and market data operations."""

    def __init__(self, coingecko: CoinGeckoClient):
        """
        Initialize price repository.

        Args:
            coingecko: CoinGeckoClient instance for market data
        """
        self.coingecko = coingecko
        self.price_history: List[Tuple[datetime, float]] = []  # List of (timestamp, price) tuples
        self.max_price_history = 60  # Keep 60 data points (1 hour at 1min intervals)

    async def get_current_price(self) -> Optional[float]:
        """
        Get current ALKIMI price from CoinGecko.

        Returns:
            Current price in USD, or None if fetch fails
        """
        try:
            price = await self.coingecko.get_current_price()
            if price:
                logger.debug(f"Current ALKIMI price: ${price:.6f}")
            return price
        except Exception as e:
            logger.error(f"Error fetching current price: {e}")
            return None

    async def get_market_data(self) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive market data for ALKIMI.

        Returns:
            Dict with price, volume, market cap, and 24h change
        """
        try:
            return await self.coingecko.get_market_data()
        except Exception as e:
            logger.error(f"Error fetching market data: {e}")
            return None

    def record_price(self, price: float) -> None:
        """
        Record price for change detection.

        Args:
            price: Current price to record
        """
        now = datetime.now()
        self.price_history.append((now, price))

        # Trim to max history to prevent unbounded growth
        if len(self.price_history) > self.max_price_history:
            self.price_history.pop(0)

        logger.debug(f"Recorded price: ${price:.6f} (history size: {len(self.price_history)})")

    def get_price_change(self, minutes: int = 60) -> Optional[float]:
        """
        Get price change percentage over last N minutes.

        Args:
            minutes: Time window in minutes (default: 60)

        Returns:
            Price change percentage, or None if insufficient data
        """
        if len(self.price_history) < 2:
            logger.debug("Insufficient price history for change calculation")
            return None

        cutoff = datetime.now() - timedelta(minutes=minutes)
        old_prices = [p for ts, p in self.price_history if ts <= cutoff]

        if not old_prices:
            logger.debug(f"No prices found older than {minutes} minutes")
            return None

        old_price = old_prices[0]
        current_price = self.price_history[-1][1]

        change_percent = ((current_price - old_price) / old_price) * 100
        logger.debug(
            f"Price change: ${old_price:.6f} -> ${current_price:.6f} "
            f"({change_percent:+.2f}% over {minutes}min)"
        )

        return change_percent

    def get_latest_price(self) -> Optional[float]:
        """
        Get the most recently recorded price.

        Returns:
            Latest price or None if no history
        """
        if self.price_history:
            return self.price_history[-1][1]
        return None

    def get_price_history_data(self) -> List[Dict[str, Any]]:
        """
        Get price history as list of dicts.

        Returns:
            List of {timestamp, price} dicts
        """
        return [
            {'timestamp': ts.isoformat(), 'price': price}
            for ts, price in self.price_history
        ]

    def clear_price_history(self) -> None:
        """Clear all recorded price history."""
        self.price_history.clear()
        logger.debug("Cleared price history")

    def get_price_stats(self) -> Optional[Dict[str, Any]]:
        """
        Get statistics about recorded prices.

        Returns:
            Dict with min, max, avg, and latest price, or None if no history
        """
        if not self.price_history:
            return None

        prices = [p for _, p in self.price_history]
        return {
            'min': min(prices),
            'max': max(prices),
            'avg': sum(prices) / len(prices),
            'latest': prices[-1],
            'count': len(prices),
            'oldest_timestamp': self.price_history[0][0].isoformat(),
            'latest_timestamp': self.price_history[-1][0].isoformat()
        }

    async def close(self) -> None:
        """Close connections and cleanup resources."""
        await self.coingecko.close()
        logger.debug("PriceRepository closed")
