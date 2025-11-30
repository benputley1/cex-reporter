"""
Portfolio Aggregator Module

Aggregates balances and portfolio data across multiple exchanges,
providing consolidated views of total holdings and valuations.
"""

import asyncio
from typing import Dict, List, Optional
from datetime import datetime

from src.exchanges.base import ExchangeInterface, ExchangeError
from src.utils import cached, get_logger
from config.settings import settings


logger = get_logger(__name__)


class PortfolioAggregator:
    """
    Aggregates portfolio data across multiple exchanges.

    Provides methods to consolidate balances, calculate total portfolio value,
    and generate detailed portfolio breakdowns with per-asset and per-exchange
    distribution information.
    """

    def __init__(self):
        """Initialize the portfolio aggregator."""
        self.tracked_assets = settings.tracked_assets
        logger.info(f"PortfolioAggregator initialized. Tracking assets: {self.tracked_assets}")

    @cached(ttl=60)
    async def aggregate_balances(
        self,
        exchanges: List[ExchangeInterface]
    ) -> Dict[str, Dict[str, float]]:
        """
        Aggregate balances across all exchanges.

        Fetches balances from all provided exchanges in parallel and consolidates
        them into a single structure organized by asset and exchange.

        Args:
            exchanges: List of initialized ExchangeInterface instances

        Returns:
            Dictionary structured as:
            {
                "USDT": {"mexc": 50000.0, "kraken": 75000.0, ...},
                "ALKIMI": {"mexc": 100000.0, "kucoin": 50000.0, ...},
                ...
            }

        Example:
            >>> aggregator = PortfolioAggregator()
            >>> exchanges = [mexc_exchange, kraken_exchange]
            >>> balances = await aggregator.aggregate_balances(exchanges)
            >>> print(balances["USDT"]["mexc"])
            50000.0
        """
        logger.info(f"Aggregating balances from {len(exchanges)} exchanges")

        # Fetch balances from all exchanges in parallel
        balance_tasks = [
            self._fetch_exchange_balances(exchange)
            for exchange in exchanges
        ]

        exchange_balances = await asyncio.gather(*balance_tasks, return_exceptions=True)

        # Aggregate results by asset
        aggregated: Dict[str, Dict[str, float]] = {}

        for i, result in enumerate(exchange_balances):
            exchange = exchanges[i]
            exchange_name = exchange.exchange_name

            # Handle failures gracefully
            if isinstance(result, Exception):
                logger.error(
                    f"Failed to fetch balances from {exchange_name}: {result}",
                    extra={"exchange": exchange_name, "error": str(result)}
                )
                continue

            if not result:
                logger.warning(f"No balances returned from {exchange_name}")
                continue

            # Organize balances by asset
            for asset, amount in result.items():
                if asset not in self.tracked_assets:
                    continue

                if asset not in aggregated:
                    aggregated[asset] = {}

                aggregated[asset][exchange_name] = amount
                logger.debug(
                    f"Added balance for {asset} on {exchange_name}: {amount}",
                    extra={"asset": asset, "exchange": exchange_name, "amount": amount}
                )

        # Ensure all tracked assets are present (even if zero)
        for asset in self.tracked_assets:
            if asset not in aggregated:
                aggregated[asset] = {}

        logger.info(
            f"Successfully aggregated balances for {len(aggregated)} assets",
            extra={"assets": list(aggregated.keys())}
        )

        return aggregated

    @cached(ttl=60)
    async def get_total_portfolio_value(
        self,
        exchanges: List[ExchangeInterface]
    ) -> float:
        """
        Calculate total portfolio value in USD.

        Aggregates all balances across exchanges and calculates the total
        USD value based on current market prices.

        Args:
            exchanges: List of initialized ExchangeInterface instances

        Returns:
            Total portfolio value in USD

        Example:
            >>> aggregator = PortfolioAggregator()
            >>> exchanges = [mexc_exchange, kraken_exchange]
            >>> total_value = await aggregator.get_total_portfolio_value(exchanges)
            >>> print(f"Total portfolio: ${total_value:,.2f}")
            Total portfolio: $125,450.75
        """
        logger.info("Calculating total portfolio value")

        # Get aggregated balances
        balances = await self.aggregate_balances(exchanges)

        if not balances:
            logger.warning("No balances found, returning 0 portfolio value")
            return 0.0

        # Get current prices (use first available exchange)
        prices = await self._fetch_current_prices(exchanges)

        if not prices:
            logger.error("Failed to fetch prices for portfolio valuation")
            return 0.0

        # Calculate total value
        total_value = 0.0

        for asset, exchange_balances in balances.items():
            asset_total = sum(exchange_balances.values())
            asset_price = prices.get(asset, 0.0)
            asset_value = asset_total * asset_price

            total_value += asset_value

            logger.debug(
                f"Asset value calculated: {asset}",
                extra={
                    "asset": asset,
                    "total_amount": asset_total,
                    "price": asset_price,
                    "value": asset_value
                }
            )

        logger.info(
            f"Total portfolio value calculated: ${total_value:,.2f}",
            extra={"total_value": total_value}
        )

        return total_value

    @cached(ttl=60)
    async def get_portfolio_breakdown(
        self,
        exchanges: List[ExchangeInterface]
    ) -> Dict:
        """
        Generate detailed portfolio breakdown.

        Provides a comprehensive analysis of the portfolio including per-asset
        totals, USD values, portfolio percentages, and per-exchange distribution.

        Args:
            exchanges: List of initialized ExchangeInterface instances

        Returns:
            Dictionary containing:
            {
                "total_value": float,  # Total portfolio value in USD
                "timestamp": str,      # ISO format timestamp
                "assets": {
                    "USDT": {
                        "total_amount": 125000.0,
                        "usd_value": 125000.0,
                        "percentage": 50.5,
                        "exchanges": {
                            "mexc": {"amount": 50000.0, "percentage": 40.0},
                            "kraken": {"amount": 75000.0, "percentage": 60.0}
                        }
                    },
                    "ALKIMI": {...}
                }
            }

        Example:
            >>> aggregator = PortfolioAggregator()
            >>> breakdown = await aggregator.get_portfolio_breakdown(exchanges)
            >>> print(breakdown["assets"]["USDT"]["percentage"])
            50.5
        """
        logger.info("Generating portfolio breakdown")

        # Get aggregated balances and prices
        balances = await self.aggregate_balances(exchanges)
        prices = await self._fetch_current_prices(exchanges)

        if not balances or not prices:
            logger.warning("Insufficient data for portfolio breakdown")
            return {
                "total_value": 0.0,
                "timestamp": datetime.utcnow().isoformat(),
                "assets": {}
            }

        # Calculate total portfolio value
        total_value = 0.0
        asset_values: Dict[str, float] = {}

        for asset, exchange_balances in balances.items():
            asset_total = sum(exchange_balances.values())
            asset_price = prices.get(asset, 0.0)
            asset_value = asset_total * asset_price

            asset_values[asset] = asset_value
            total_value += asset_value

        # Build detailed breakdown
        breakdown = {
            "total_value": total_value,
            "timestamp": datetime.utcnow().isoformat(),
            "assets": {}
        }

        for asset, exchange_balances in balances.items():
            asset_total = sum(exchange_balances.values())
            asset_price = prices.get(asset, 0.0)
            asset_value = asset_values[asset]
            asset_percentage = (asset_value / total_value * 100) if total_value > 0 else 0.0

            # Calculate per-exchange distribution
            exchange_distribution = {}
            for exchange_name, amount in exchange_balances.items():
                exchange_percentage = (amount / asset_total * 100) if asset_total > 0 else 0.0
                exchange_distribution[exchange_name] = {
                    "amount": amount,
                    "percentage": round(exchange_percentage, 2)
                }

            breakdown["assets"][asset] = {
                "total_amount": asset_total,
                "usd_value": asset_value,
                "price": asset_price,
                "percentage": round(asset_percentage, 2),
                "exchanges": exchange_distribution
            }

            logger.debug(
                f"Breakdown calculated for {asset}",
                extra={
                    "asset": asset,
                    "total_amount": asset_total,
                    "usd_value": asset_value,
                    "percentage": asset_percentage
                }
            )

        logger.info(
            "Portfolio breakdown generated successfully",
            extra={
                "total_value": total_value,
                "num_assets": len(breakdown["assets"])
            }
        )

        return breakdown

    async def _fetch_exchange_balances(
        self,
        exchange: ExchangeInterface
    ) -> Dict[str, float]:
        """
        Fetch balances from a single exchange with error handling.

        Args:
            exchange: ExchangeInterface instance

        Returns:
            Dictionary of balances, or empty dict on failure
        """
        try:
            balances = await exchange.get_balances()
            logger.debug(
                f"Fetched balances from {exchange.exchange_name}",
                extra={"exchange": exchange.exchange_name, "assets": list(balances.keys())}
            )
            return balances
        except ExchangeError as e:
            logger.error(
                f"Exchange error fetching balances from {exchange.exchange_name}: {e}",
                extra={"exchange": exchange.exchange_name, "error": str(e)}
            )
            return {}
        except Exception as e:
            logger.error(
                f"Unexpected error fetching balances from {exchange.exchange_name}: {e}",
                extra={"exchange": exchange.exchange_name, "error": str(e)}
            )
            return {}

    async def _fetch_current_prices(
        self,
        exchanges: List[ExchangeInterface]
    ) -> Dict[str, float]:
        """
        Fetch current prices for tracked assets.

        Tries each exchange until prices are successfully fetched.

        Args:
            exchanges: List of ExchangeInterface instances

        Returns:
            Dictionary mapping asset symbols to USD prices
        """
        for exchange in exchanges:
            try:
                prices = await exchange.get_prices(self.tracked_assets)
                if prices:
                    logger.debug(
                        f"Fetched prices from {exchange.exchange_name}",
                        extra={"exchange": exchange.exchange_name, "prices": prices}
                    )
                    return prices
            except ExchangeError as e:
                logger.warning(
                    f"Failed to fetch prices from {exchange.exchange_name}: {e}",
                    extra={"exchange": exchange.exchange_name}
                )
                continue
            except Exception as e:
                logger.warning(
                    f"Unexpected error fetching prices from {exchange.exchange_name}: {e}",
                    extra={"exchange": exchange.exchange_name}
                )
                continue

        logger.error("Failed to fetch prices from any exchange")
        return {}
