"""
P&L (Profit and Loss) Calculator Module

Calculates realized and unrealized profit/loss using FIFO accounting,
providing comprehensive P&L reports across different timeframes.
"""

from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta, timezone
from collections import defaultdict, deque
import asyncio

from src.exchanges.base import ExchangeInterface, Trade, TradeSide, ExchangeError
from src.utils import get_logger
from config.settings import settings


logger = get_logger(__name__)


class PnLCalculator:
    """
    Calculates profit and loss using FIFO (First-In-First-Out) accounting.

    Provides methods for calculating realized P&L from completed trades,
    unrealized P&L from current holdings, and timeframe-based P&L analysis.
    """

    def __init__(self):
        """Initialize the P&L calculator."""
        self.tracked_assets = settings.tracked_assets
        self.historical_start_date = datetime.fromisoformat(settings.historical_start_date)
        logger.info(
            f"PnLCalculator initialized. Tracking assets: {self.tracked_assets}, "
            f"Historical start: {self.historical_start_date.date()}"
        )

    async def calculate_unrealized_pnl(
        self,
        current_balances: Dict[str, float],
        trades: List[Trade]
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate unrealized P&L for current holdings.

        Uses FIFO accounting to determine the cost basis of current holdings,
        then compares against current market prices to calculate unrealized gains/losses.

        Args:
            current_balances: Dictionary mapping asset symbols to current amounts
            trades: List of all trades (used to calculate cost basis)

        Returns:
            Dictionary structured as:
            {
                "USDT": {
                    "unrealized_pnl": 150.50,
                    "avg_entry": 0.998,
                    "current_price": 1.0,
                    "current_amount": 125000.0,
                    "cost_basis": 124850.0,
                    "current_value": 125000.0
                },
                "ALKIMI": {...}
            }

        Example:
            >>> calculator = PnLCalculator()
            >>> balances = {"USDT": 125000.0, "ALKIMI": 50000.0}
            >>> unrealized = await calculator.calculate_unrealized_pnl(balances, trades)
            >>> print(unrealized["USDT"]["unrealized_pnl"])
            150.50
        """
        logger.info("Calculating unrealized P&L")

        result = {}

        for asset, current_amount in current_balances.items():
            if asset not in self.tracked_assets:
                continue

            if current_amount <= 0:
                logger.debug(f"Skipping {asset} - zero or negative balance")
                continue

            # Get cost basis using FIFO
            cost_basis, avg_entry = self._calculate_cost_basis(asset, current_amount, trades)

            # Get current price from recent trades
            current_price = self._get_current_price_from_trades(asset, trades)

            if current_price is None:
                logger.warning(
                    f"Cannot calculate unrealized P&L for {asset} - no price data",
                    extra={"asset": asset}
                )
                continue

            # Calculate unrealized P&L
            current_value = current_amount * current_price
            unrealized_pnl = current_value - cost_basis
            unrealized_pnl_percent = (unrealized_pnl / cost_basis * 100) if cost_basis > 0 else 0.0

            result[asset] = {
                "unrealized_pnl": unrealized_pnl,
                "unrealized_pnl_percent": unrealized_pnl_percent,
                "avg_entry": avg_entry,
                "current_price": current_price,
                "current_amount": current_amount,
                "cost_basis": cost_basis,
                "current_value": current_value
            }

            logger.debug(
                f"Unrealized P&L calculated for {asset}",
                extra={
                    "asset": asset,
                    "unrealized_pnl": unrealized_pnl,
                    "avg_entry": avg_entry,
                    "current_price": current_price
                }
            )

        logger.info(
            f"Unrealized P&L calculated for {len(result)} assets",
            extra={"assets": list(result.keys())}
        )

        return result

    async def calculate_realized_pnl(
        self,
        trades: List[Trade]
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate realized P&L from completed trades.

        Matches buy and sell trades using FIFO accounting to determine
        realized gains and losses from closed positions.

        Args:
            trades: List of all trades

        Returns:
            Dictionary structured as:
            {
                "USDT": {
                    "realized_pnl": 500.25,
                    "total_bought": 150000.0,
                    "total_sold": 25000.0,
                    "avg_buy_price": 0.998,
                    "avg_sell_price": 1.020,
                    "num_trades": 15
                },
                "ALKIMI": {...}
            }

        Example:
            >>> calculator = PnLCalculator()
            >>> realized = await calculator.calculate_realized_pnl(trades)
            >>> print(realized["USDT"]["realized_pnl"])
            500.25
        """
        logger.info("Calculating realized P&L")

        # Group trades by asset
        trades_by_asset = self._group_trades_by_asset(trades)

        result = {}

        for asset, asset_trades in trades_by_asset.items():
            if asset not in self.tracked_assets:
                continue

            # Calculate realized P&L using FIFO
            realized_pnl, stats = self._calculate_realized_pnl_fifo(asset_trades)

            if stats["num_trades"] == 0:
                logger.debug(f"No trades found for {asset}")
                continue

            result[asset] = {
                "realized_pnl": realized_pnl,
                "total_bought": stats["total_bought"],
                "total_sold": stats["total_sold"],
                "avg_buy_price": stats["avg_buy_price"],
                "avg_sell_price": stats["avg_sell_price"],
                "num_trades": stats["num_trades"]
            }

            logger.debug(
                f"Realized P&L calculated for {asset}",
                extra={
                    "asset": asset,
                    "realized_pnl": realized_pnl,
                    "num_trades": stats["num_trades"]
                }
            )

        logger.info(
            f"Realized P&L calculated for {len(result)} assets",
            extra={"assets": list(result.keys())}
        )

        return result

    async def calculate_timeframe_pnl(
        self,
        trades: List[Trade],
        timeframe: str
    ) -> Dict[str, Dict[str, float]]:
        """
        Calculate P&L for a specific timeframe.

        Filters trades by the specified timeframe and calculates realized
        and unrealized P&L for that period.

        Args:
            trades: List of all trades
            timeframe: One of "24h", "7d", "30d", or "all"

        Returns:
            Dictionary structured as:
            {
                "USDT": {
                    "pnl": 250.50,
                    "pnl_percent": 2.5,
                    "num_trades": 5,
                    "volume": 10000.0,
                    "start_date": "2025-10-01T00:00:00",
                    "end_date": "2025-11-04T00:00:00"
                },
                "ALKIMI": {...}
            }

        Raises:
            ValueError: If timeframe is not one of the supported values

        Example:
            >>> calculator = PnLCalculator()
            >>> pnl_7d = await calculator.calculate_timeframe_pnl(trades, "7d")
            >>> print(pnl_7d["USDT"]["pnl"])
            250.50
        """
        logger.info(f"Calculating P&L for timeframe: {timeframe}")

        # Validate timeframe
        valid_timeframes = ["24h", "7d", "30d", "all"]
        if timeframe not in valid_timeframes:
            raise ValueError(
                f"Invalid timeframe '{timeframe}'. Must be one of: {valid_timeframes}"
            )

        # Calculate timeframe boundaries
        end_date = datetime.utcnow()
        start_date = self._get_timeframe_start(timeframe, end_date)

        logger.debug(
            f"Timeframe boundaries: {start_date.date()} to {end_date.date()}",
            extra={"timeframe": timeframe, "start_date": start_date, "end_date": end_date}
        )

        # Filter trades by timeframe
        filtered_trades = [
            trade for trade in trades
            if start_date <= trade.timestamp <= end_date
        ]

        logger.info(
            f"Filtered {len(filtered_trades)} trades for timeframe {timeframe}",
            extra={"timeframe": timeframe, "num_trades": len(filtered_trades)}
        )

        # Group trades by asset
        trades_by_asset = self._group_trades_by_asset(filtered_trades)

        result = {}

        for asset, asset_trades in trades_by_asset.items():
            if asset not in self.tracked_assets:
                continue

            # Calculate realized P&L for the timeframe
            realized_pnl, stats = self._calculate_realized_pnl_fifo(asset_trades)

            # Calculate total volume
            total_volume = sum(trade.amount * trade.price for trade in asset_trades)

            # Calculate P&L percentage (based on buy volume)
            buy_volume = sum(
                trade.amount * trade.price
                for trade in asset_trades
                if trade.side == TradeSide.BUY
            )
            pnl_percent = (realized_pnl / buy_volume * 100) if buy_volume > 0 else 0.0

            result[asset] = {
                "pnl": realized_pnl,
                "pnl_percent": pnl_percent,
                "num_trades": stats["num_trades"],
                "volume": total_volume,
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "timeframe": timeframe
            }

            logger.debug(
                f"Timeframe P&L calculated for {asset}",
                extra={
                    "asset": asset,
                    "timeframe": timeframe,
                    "pnl": realized_pnl,
                    "num_trades": stats["num_trades"]
                }
            )

        logger.info(
            f"Timeframe P&L calculated for {len(result)} assets",
            extra={"timeframe": timeframe, "assets": list(result.keys())}
        )

        return result

    async def get_full_pnl_report(
        self,
        exchanges: List[ExchangeInterface]
    ) -> Dict:
        """
        Generate comprehensive P&L report.

        Combines all P&L calculations into a single comprehensive report
        including realized, unrealized, and timeframe-based P&L data.

        Args:
            exchanges: List of initialized ExchangeInterface instances

        Returns:
            Dictionary containing:
            {
                "timestamp": "2025-11-04T12:00:00",
                "realized_pnl": {...},
                "unrealized_pnl": {...},
                "timeframes": {
                    "24h": {...},
                    "7d": {...},
                    "30d": {...},
                    "all": {...}
                },
                "summary": {
                    "total_realized_pnl": 500.50,
                    "total_unrealized_pnl": 150.25,
                    "total_pnl": 650.75
                }
            }

        Example:
            >>> calculator = PnLCalculator()
            >>> report = await calculator.get_full_pnl_report(exchanges)
            >>> print(report["summary"]["total_pnl"])
            650.75
        """
        logger.info("Generating full P&L report")

        # Fetch all trades from all exchanges
        all_trades = await self._fetch_all_trades(exchanges)

        if not all_trades:
            logger.warning("No trades found for P&L report")
            return self._empty_pnl_report()

        # Fetch current balances
        current_balances = await self._fetch_all_balances(exchanges)

        # Calculate realized P&L
        realized_pnl = await self.calculate_realized_pnl(all_trades)

        # Calculate unrealized P&L
        unrealized_pnl = await self.calculate_unrealized_pnl(current_balances, all_trades)

        # Calculate timeframe P&L
        timeframes = {
            "24h": await self.calculate_timeframe_pnl(all_trades, "24h"),
            "7d": await self.calculate_timeframe_pnl(all_trades, "7d"),
            "30d": await self.calculate_timeframe_pnl(all_trades, "30d"),
            "all": await self.calculate_timeframe_pnl(all_trades, "all")
        }

        # Calculate summary
        total_realized_pnl = sum(
            asset_data.get("realized_pnl", 0.0)
            for asset_data in realized_pnl.values()
        )
        total_unrealized_pnl = sum(
            asset_data.get("unrealized_pnl", 0.0)
            for asset_data in unrealized_pnl.values()
        )
        total_pnl = total_realized_pnl + total_unrealized_pnl

        report = {
            "timestamp": datetime.utcnow().isoformat(),
            "realized_pnl": realized_pnl,
            "unrealized_pnl": unrealized_pnl,
            "timeframes": timeframes,
            "summary": {
                "total_realized_pnl": total_realized_pnl,
                "total_unrealized_pnl": total_unrealized_pnl,
                "total_pnl": total_pnl,
                "num_trades": len(all_trades),
                "num_exchanges": len(exchanges)
            }
        }

        logger.info(
            "Full P&L report generated",
            extra={
                "total_pnl": total_pnl,
                "num_trades": len(all_trades),
                "num_exchanges": len(exchanges)
            }
        )

        return report

    def _calculate_cost_basis(
        self,
        asset: str,
        current_amount: float,
        trades: List[Trade],
        initial_deposit_amount: float = 0.0,
        initial_deposit_avg_price: float = 0.0
    ) -> Tuple[float, float]:
        """
        Calculate cost basis for current holdings using FIFO.

        Args:
            asset: Asset symbol
            current_amount: Current amount held
            trades: List of all trades
            initial_deposit_amount: Initial deposit amount (cost basis)
            initial_deposit_avg_price: Average price paid for initial deposit

        Returns:
            Tuple of (total_cost_basis, average_entry_price)
        """
        # Get trades for this asset, sorted by timestamp
        asset_trades = sorted(
            [t for t in trades if t.symbol == asset],
            key=lambda x: x.timestamp
        )

        # FIFO queue of buy positions
        buy_queue = deque()
        remaining_amount = current_amount

        # CRITICAL FIX: Add initial deposit to buy queue FIRST
        if initial_deposit_amount > 0 and initial_deposit_avg_price > 0:
            buy_queue.append((initial_deposit_amount, initial_deposit_avg_price))

        # Process trades chronologically
        for trade in asset_trades:
            if trade.side == TradeSide.BUY:
                # Add buy to queue (amount, price with fees)
                cost_per_unit = trade.price + (trade.fee / trade.amount) if trade.amount > 0 else trade.price
                buy_queue.append((trade.amount, cost_per_unit))
            elif trade.side == TradeSide.SELL:
                # Remove from queue (FIFO)
                sell_amount = trade.amount
                while sell_amount > 0 and buy_queue:
                    buy_amount, buy_price = buy_queue[0]
                    if buy_amount <= sell_amount:
                        buy_queue.popleft()
                        sell_amount -= buy_amount
                    else:
                        buy_queue[0] = (buy_amount - sell_amount, buy_price)
                        sell_amount = 0

        # Calculate cost basis from remaining buys
        total_cost = 0.0
        total_amount = 0.0

        for amount, price in buy_queue:
            if total_amount >= current_amount:
                break

            # Take only what we need
            use_amount = min(amount, current_amount - total_amount)
            total_cost += use_amount * price
            total_amount += use_amount

        avg_entry = total_cost / total_amount if total_amount > 0 else 0.0

        return total_cost, avg_entry

    def _calculate_realized_pnl_fifo(
        self,
        trades: List[Trade],
        initial_deposit_amount: float = 0.0,
        initial_deposit_avg_price: float = 0.0
    ) -> Tuple[float, Dict]:
        """
        Calculate realized P&L using FIFO matching.

        Args:
            trades: List of trades for a single asset
            initial_deposit_amount: Initial deposit amount (cost basis)
            initial_deposit_avg_price: Average price paid for initial deposit

        Returns:
            Tuple of (realized_pnl, statistics_dict)
        """
        # Sort trades chronologically
        sorted_trades = sorted(trades, key=lambda x: x.timestamp)

        # FIFO queue of buy positions
        buy_queue = deque()
        realized_pnl = 0.0

        # CRITICAL FIX: Add initial deposit to buy queue FIRST
        if initial_deposit_amount > 0 and initial_deposit_avg_price > 0:
            buy_queue.append((initial_deposit_amount, initial_deposit_avg_price))
            logger.info(
                f"Added initial deposit to FIFO queue: {initial_deposit_amount:,.0f} @ "
                f"${initial_deposit_avg_price:.6f} = ${initial_deposit_amount * initial_deposit_avg_price:,.2f}"
            )

        total_bought = 0.0
        total_sold = 0.0
        buy_cost_sum = 0.0
        sell_revenue_sum = 0.0

        for trade in sorted_trades:
            if trade.side == TradeSide.BUY:
                # Add buy to queue (amount, cost_per_unit including fees)
                cost_per_unit = trade.price + (trade.fee / trade.amount) if trade.amount > 0 else trade.price
                buy_queue.append((trade.amount, cost_per_unit))
                total_bought += trade.amount
                buy_cost_sum += trade.amount * trade.price
            elif trade.side == TradeSide.SELL:
                # Match against buys (FIFO)
                sell_amount = trade.amount
                sell_price = trade.price - (trade.fee / trade.amount) if trade.amount > 0 else trade.price
                total_sold += trade.amount
                sell_revenue_sum += trade.amount * trade.price

                while sell_amount > 0 and buy_queue:
                    buy_amount, buy_price = buy_queue[0]

                    if buy_amount <= sell_amount:
                        # Fully consume this buy
                        realized_pnl += buy_amount * (sell_price - buy_price)
                        sell_amount -= buy_amount
                        buy_queue.popleft()
                    else:
                        # Partially consume this buy
                        realized_pnl += sell_amount * (sell_price - buy_price)
                        buy_queue[0] = (buy_amount - sell_amount, buy_price)
                        sell_amount = 0

        stats = {
            "total_bought": total_bought,
            "total_sold": total_sold,
            "avg_buy_price": buy_cost_sum / total_bought if total_bought > 0 else 0.0,
            "avg_sell_price": sell_revenue_sum / total_sold if total_sold > 0 else 0.0,
            "num_trades": len(sorted_trades)
        }

        return realized_pnl, stats

    def _get_current_price_from_trades(
        self,
        asset: str,
        trades: List[Trade]
    ) -> Optional[float]:
        """
        Get current price from most recent trade.

        Args:
            asset: Asset symbol
            trades: List of all trades

        Returns:
            Most recent trade price, or None if no trades found
        """
        asset_trades = [t for t in trades if t.symbol == asset]

        if not asset_trades:
            return None

        # Get most recent trade
        most_recent = max(asset_trades, key=lambda x: x.timestamp)
        return most_recent.price

    def _group_trades_by_asset(
        self,
        trades: List[Trade]
    ) -> Dict[str, List[Trade]]:
        """
        Group trades by asset symbol.

        Args:
            trades: List of trades

        Returns:
            Dictionary mapping asset symbols to lists of trades
        """
        grouped = defaultdict(list)

        for trade in trades:
            grouped[trade.symbol].append(trade)

        return dict(grouped)

    def _get_timeframe_start(
        self,
        timeframe: str,
        end_date: datetime
    ) -> datetime:
        """
        Calculate start date for a timeframe.

        Args:
            timeframe: One of "24h", "7d", "30d", "all"
            end_date: End date for the timeframe

        Returns:
            Start date for the timeframe
        """
        if timeframe == "24h":
            return end_date - timedelta(hours=24)
        elif timeframe == "7d":
            return end_date - timedelta(days=7)
        elif timeframe == "30d":
            return end_date - timedelta(days=30)
        elif timeframe == "all":
            return self.historical_start_date
        else:
            return end_date

    async def _fetch_all_trades(
        self,
        exchanges: List[ExchangeInterface]
    ) -> List[Trade]:
        """
        Fetch all trades from all exchanges.

        Args:
            exchanges: List of ExchangeInterface instances

        Returns:
            Combined list of all trades
        """
        logger.info(f"Fetching trades from {len(exchanges)} exchanges")

        trade_tasks = [
            exchange.get_trades(since=self.historical_start_date)
            for exchange in exchanges
        ]

        results = await asyncio.gather(*trade_tasks, return_exceptions=True)

        all_trades = []

        for i, result in enumerate(results):
            exchange = exchanges[i]

            if isinstance(result, Exception):
                logger.error(
                    f"Failed to fetch trades from {exchange.exchange_name}: {result}",
                    extra={"exchange": exchange.exchange_name}
                )
                continue

            all_trades.extend(result)

        logger.info(
            f"Fetched {len(all_trades)} total trades",
            extra={"num_trades": len(all_trades)}
        )

        return all_trades

    async def _fetch_all_balances(
        self,
        exchanges: List[ExchangeInterface]
    ) -> Dict[str, float]:
        """
        Fetch and aggregate balances from all exchanges.

        Args:
            exchanges: List of ExchangeInterface instances

        Returns:
            Dictionary mapping assets to total amounts
        """
        logger.info(f"Fetching balances from {len(exchanges)} exchanges")

        balance_tasks = [
            exchange.get_balances()
            for exchange in exchanges
        ]

        results = await asyncio.gather(*balance_tasks, return_exceptions=True)

        aggregated_balances = defaultdict(float)

        for i, result in enumerate(results):
            exchange = exchanges[i]

            if isinstance(result, Exception):
                logger.error(
                    f"Failed to fetch balances from {exchange.exchange_name}: {result}",
                    extra={"exchange": exchange.exchange_name}
                )
                continue

            for asset, amount in result.items():
                if asset in self.tracked_assets:
                    aggregated_balances[asset] += amount

        return dict(aggregated_balances)

    def _empty_pnl_report(self) -> Dict:
        """
        Generate empty P&L report structure.

        Returns:
            Empty P&L report dictionary
        """
        return {
            "timestamp": datetime.utcnow().isoformat(),
            "realized_pnl": {},
            "unrealized_pnl": {},
            "timeframes": {
                "24h": {},
                "7d": {},
                "30d": {},
                "all": {}
            },
            "summary": {
                "total_realized_pnl": 0.0,
                "total_unrealized_pnl": 0.0,
                "total_pnl": 0.0,
                "num_trades": 0,
                "num_exchanges": 0
            }
        }
