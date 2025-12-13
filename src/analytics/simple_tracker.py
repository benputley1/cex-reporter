"""
Simplified Position Tracker

Tracks positions over a rolling 25-day window with local caching.
Supports both CEX and DEX (Sui blockchain) data sources.
Much simpler than the full position_tracker - focused on daily reporting.
"""

import asyncio
from typing import Dict, List
from datetime import datetime, timedelta
from collections import defaultdict, deque

from config.settings import settings
from src.exchanges.base import ExchangeInterface, Trade, TradeSide
from src.data import DepositsLoader, TradeCache, DailySnapshot
from src.utils import get_logger, deduplicate_trades
from src.exchanges.sui_monitor import SuiTokenMonitor

logger = get_logger(__name__)

# DEX exchange names (for categorization in reports)
DEX_EXCHANGES = {'sui_dex', 'cetus', 'bluefin', 'turbos', 'aftermath'}


class SimpleTracker:
    """Simplified 25-day rolling window tracker with local caching."""

    def __init__(self):
        """Initialize the simple tracker."""
        self.trade_cache = TradeCache()
        self.daily_snapshot = DailySnapshot()
        self.deposits_loader = DepositsLoader()
        self.sui_monitor = None  # Initialized on demand

        # Load withdrawals
        try:
            self.withdrawals = self.deposits_loader.load_withdrawals()
            self.total_withdrawals = self.deposits_loader.get_total_withdrawals()
            logger.info(f"Loaded ${self.total_withdrawals:,.2f} in withdrawals")
        except Exception as e:
            logger.warning(f"Could not load withdrawals: {e}")
            self.withdrawals = {}
            self.total_withdrawals = 0.0

        # Load initial deposits for FIFO cost basis
        try:
            initial_deposits = self.deposits_loader.load_initial_deposits()
            alkimi_data = initial_deposits.get('ALKIMI', {})
            self.initial_deposit_amount = alkimi_data.get('total_amount', 0.0)
            self.initial_deposit_avg_price = alkimi_data.get('avg_price', 0.0)
            logger.info(
                f"Loaded initial deposits: {self.initial_deposit_amount:,.0f} ALKIMI @ "
                f"${self.initial_deposit_avg_price:.6f} avg = ${self.initial_deposit_amount * self.initial_deposit_avg_price:,.2f}"
            )
        except Exception as e:
            logger.warning(f"Could not load initial deposits: {e}")
            self.initial_deposit_amount = 0.0
            self.initial_deposit_avg_price = 0.0

    async def _get_sui_monitor(self) -> SuiTokenMonitor:
        """Get or create SuiTokenMonitor instance."""
        if self.sui_monitor is None:
            sui_config = settings.sui_config
            self.sui_monitor = SuiTokenMonitor(
                config=sui_config,
                account_name='SUI_ANALYTICS'
            )
            await self.sui_monitor.initialize()
        return self.sui_monitor

    async def get_report(self, exchanges: List[ExchangeInterface]) -> Dict:
        """
        Generate simplified report.

        Returns:
            {
                'holdings_by_exchange': {...},
                'daily_change': {...},
                'today_activity': {...},
                'rolling_25d': {...}
            }
        """
        logger.info("=" * 60)
        logger.info("Generating Simplified Position Report (complete data window)")

        # 1. Get current balances and aggregate by exchange
        current_balances, holdings_by_exchange = await self._get_holdings_by_exchange(exchanges)

        # 2. Save today's snapshot
        self.daily_snapshot.save_snapshot(current_balances)

        # 3. Get daily change (vs yesterday)
        daily_change = self._calculate_daily_change(current_balances)

        # 4. Fetch and cache trades
        all_trades, complete_window_start = await self._fetch_and_cache_trades(exchanges)

        # 5. Get today's activity
        today_activity = self._get_today_activity(all_trades)

        # 6. Get complete data window metrics (25 days + N cached days)
        rolling_25d = await self._get_rolling_25d_data(all_trades, current_balances, complete_window_start)

        # 7. Get monthly windows (November and October with complete data coverage)
        monthly_windows = self._get_monthly_windows(all_trades, current_balances, complete_window_start)

        # 8. Calculate token revenue target metrics (November only)
        token_revenue = await self._calculate_token_revenue_target(all_trades, current_balances, holdings_by_exchange)

        # 9. Separate CEX and DEX activity for reporting
        cex_dex_breakdown = self._get_cex_dex_breakdown(all_trades, complete_window_start)

        # 10. Fetch on-chain analytics (pools, holders, whale tracking)
        onchain_analytics = await self._get_onchain_analytics()

        return {
            'report_date': datetime.now(),
            'holdings_by_exchange': holdings_by_exchange,
            'total_balances': current_balances,
            'daily_change': daily_change,
            'today_activity': today_activity,
            'rolling_25d': rolling_25d,
            'monthly_windows': monthly_windows,
            'token_revenue_target': token_revenue,
            'cex_dex_breakdown': cex_dex_breakdown,
            'onchain_analytics': onchain_analytics
        }

    async def _get_holdings_by_exchange(
        self,
        exchanges: List[ExchangeInterface]
    ) -> tuple[Dict[str, float], Dict]:
        """
        Get current balances aggregated by exchange with detailed breakdown.

        Uses parallel execution with asyncio.gather to fetch from all exchanges concurrently.
        Handles partial failures gracefully - returns results from successful exchanges.

        Returns:
            (total_balances, holdings_by_exchange)

            total_balances: {'USDT': total_amount, 'ALKIMI': total_amount}
            holdings_by_exchange: {
                'EXCHANGE_NAME': {
                    'accounts': ['account1', 'account2'],
                    'USDT': {'free': X, 'locked': Y, 'total': Z},
                    'ALKIMI': {'free': X, 'locked': Y, 'total': Z}
                }
            }
        """
        logger.info(f"Fetching current balances from {len(exchanges)} exchanges in parallel...")
        start_time = datetime.now()

        # Create tasks with timeout for each exchange
        timeout = settings.exchange_timeout_seconds
        tasks = []
        for exchange in exchanges:
            task = asyncio.wait_for(
                exchange.get_balances(),
                timeout=timeout
            )
            tasks.append(task)

        # Execute all tasks in parallel with exception handling
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results and aggregate
        holdings_by_exchange = defaultdict(lambda: {
            'accounts': [],
            'USDT': {'free': 0.0, 'locked': 0.0, 'total': 0.0},
            'ALKIMI': {'free': 0.0, 'locked': 0.0, 'total': 0.0}
        })
        total_balances = {'USDT': 0.0, 'ALKIMI': 0.0}

        successful_count = 0
        failed_exchanges = []

        for exchange, result in zip(exchanges, results):
            exchange_name = exchange.exchange_name.upper()
            account_name = exchange.account_name

            # Handle failures gracefully
            if isinstance(result, Exception):
                failed_exchanges.append(f"{exchange_name}/{account_name}")
                logger.warning(
                    f"Failed to fetch balances from {exchange_name}/{account_name}: {result}"
                )
                continue

            # Process successful result
            try:
                balances = result
                successful_count += 1

                # Add to exchange total (with detailed breakdown)
                holdings_by_exchange[exchange_name]['accounts'].append(account_name)

                for asset in ['USDT', 'ALKIMI']:
                    asset_balance = balances.get(asset, {'free': 0.0, 'locked': 0.0, 'total': 0.0})
                    holdings_by_exchange[exchange_name][asset]['free'] += asset_balance['free']
                    holdings_by_exchange[exchange_name][asset]['locked'] += asset_balance['locked']
                    holdings_by_exchange[exchange_name][asset]['total'] += asset_balance['total']

                    # Add to overall total (just the total value)
                    total_balances[asset] += asset_balance['total']

                logger.debug(
                    f"{exchange_name}/{account_name}: "
                    f"USDT={balances.get('USDT', {}).get('total', 0):,.2f}, "
                    f"ALKIMI={balances.get('ALKIMI', {}).get('total', 0):,.0f}"
                )

            except Exception as e:
                failed_exchanges.append(f"{exchange_name}/{account_name}")
                logger.error(f"Error processing balances from {exchange_name}/{account_name}: {e}")

        # Convert to regular dict
        holdings_by_exchange = dict(holdings_by_exchange)

        # Log timing and success rate
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Parallel balance fetch completed in {elapsed_time:.2f}s "
            f"({successful_count}/{len(exchanges)} successful)"
        )

        if failed_exchanges:
            logger.warning(f"Failed exchanges: {', '.join(failed_exchanges)}")

        logger.info(
            f"Total balances: USDT=${total_balances['USDT']:,.2f}, "
            f"ALKIMI={total_balances['ALKIMI']:,.0f}"
        )

        return total_balances, holdings_by_exchange

    def _calculate_daily_change(self, current_balances: Dict[str, float]) -> Dict:
        """Calculate change vs yesterday's snapshot."""
        yesterday_balances = self.daily_snapshot.get_yesterday_snapshot()

        if not yesterday_balances:
            logger.warning("No yesterday snapshot found - daily change unavailable")
            return {
                'available': False,
                'message': 'No historical data (first run)'
            }

        usdt_change = current_balances['USDT'] - yesterday_balances.get('USDT', 0)
        usdt_change_pct = (usdt_change / yesterday_balances.get('USDT', 1)) * 100 if yesterday_balances.get('USDT', 0) > 0 else 0

        alkimi_change = current_balances['ALKIMI'] - yesterday_balances.get('ALKIMI', 0)
        alkimi_change_pct = (alkimi_change / yesterday_balances.get('ALKIMI', 1)) * 100 if yesterday_balances.get('ALKIMI', 0) > 0 else 0

        return {
            'available': True,
            'usdt': {
                'previous': yesterday_balances.get('USDT', 0),
                'current': current_balances['USDT'],
                'change': usdt_change,
                'change_percent': usdt_change_pct
            },
            'alkimi': {
                'previous': yesterday_balances.get('ALKIMI', 0),
                'current': current_balances['ALKIMI'],
                'change': alkimi_change,
                'change_percent': alkimi_change_pct
            }
        }

    async def _fetch_and_cache_trades(
        self,
        exchanges: List[ExchangeInterface]
    ) -> tuple[List[Trade], datetime]:
        """
        Fetch trades from APIs and cache them locally.
        Returns trades and the complete data window start date.

        Uses parallel execution with asyncio.gather to fetch from all exchanges concurrently.
        Handles partial failures gracefully - returns results from successful exchanges.

        The complete data window is limited by the exchange with the shortest
        API retention (MEXC: 25 days). This ensures we only use data where we
        have complete coverage across all exchanges.

        Returns:
            (all_trades, complete_window_start): Trades and the start date of complete data
        """
        logger.info(f"Fetching trades from {len(exchanges)} exchanges in parallel...")
        start_time = datetime.now()

        # Fetch from APIs (last 30 days to ensure we get everything available)
        api_start = datetime.now() - timedelta(days=30)

        # Create tasks with timeout for each exchange
        timeout = settings.exchange_timeout_seconds
        tasks = []
        for exchange in exchanges:
            task = asyncio.wait_for(
                exchange.get_trades(since=api_start),
                timeout=timeout
            )
            tasks.append(task)

        # Execute all tasks in parallel with exception handling
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Process results
        all_api_trades = []
        oldest_trade_per_exchange = {}  # Track oldest trade from each exchange
        successful_count = 0
        failed_exchanges = []

        for exchange, result in zip(exchanges, results):
            exchange_name = exchange.exchange_name
            account_name = exchange.account_name

            # Handle failures gracefully
            if isinstance(result, Exception):
                failed_exchanges.append(f"{exchange_name}/{account_name}")
                logger.warning(
                    f"Failed to fetch trades from {exchange_name}/{account_name}: {result}"
                )
                continue

            # Process successful result
            try:
                trades = result
                successful_count += 1

                # Save to cache
                cached_count = self.trade_cache.save_trades(
                    trades,
                    exchange_name,
                    account_name
                )

                all_api_trades.extend(trades)

                # Track oldest trade for this exchange
                if trades:
                    oldest_trade = min(trades, key=lambda t: t.timestamp)
                    if exchange_name not in oldest_trade_per_exchange:
                        oldest_trade_per_exchange[exchange_name] = oldest_trade.timestamp
                    else:
                        oldest_trade_per_exchange[exchange_name] = min(
                            oldest_trade_per_exchange[exchange_name],
                            oldest_trade.timestamp
                        )

                logger.info(
                    f"{exchange_name}/{account_name}: "
                    f"Fetched {len(trades)} trades from API, cached {cached_count} new"
                )

            except Exception as e:
                failed_exchanges.append(f"{exchange_name}/{account_name}")
                logger.error(f"Error processing trades from {exchange_name}/{account_name}: {e}")

        # Log timing and success rate
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(
            f"Parallel trade fetch completed in {elapsed_time:.2f}s "
            f"({successful_count}/{len(exchanges)} successful)"
        )

        if failed_exchanges:
            logger.warning(f"Failed exchanges: {', '.join(failed_exchanges)}")

        # Deduplicate API trades
        all_api_trades = deduplicate_trades(all_api_trades)

        # Find complete data window start (oldest date among all exchanges)
        # This is limited by the exchange with shortest retention (MEXC: ~25 days)
        if oldest_trade_per_exchange:
            complete_window_start = max(oldest_trade_per_exchange.values())  # Most recent of the oldest dates
            logger.info(
                f"Complete data window starts: {complete_window_start.date()} "
                f"(limited by shortest API retention across exchanges)"
            )
        else:
            # Fallback if no trades found
            complete_window_start = datetime.now() - timedelta(days=25)
            logger.warning("No trades found from APIs, using 25-day fallback window")

        # Get cached trades going back to historical start OR complete window start
        # We want all cached trades for full historical view
        historical_start = datetime.fromisoformat(settings.historical_start_date)
        cache_start = min(complete_window_start, historical_start)
        cached_trades = self.trade_cache.get_trades(since=cache_start)

        logger.info(
            f"Retrieved {len(cached_trades)} trades from cache "
            f"({len(all_api_trades)} from APIs)"
        )

        # Merge and deduplicate (API trades + cached trades)
        all_trades = deduplicate_trades(all_api_trades + cached_trades)

        logger.info(f"Total unique trades available: {len(all_trades)}")

        return all_trades, complete_window_start

    def _get_today_activity(self, all_trades: List[Trade]) -> Dict:
        """Get today's trading activity."""
        today = datetime.now().date()

        today_trades = [t for t in all_trades if t.timestamp.date() == today]

        if not today_trades:
            return {
                'trade_count': 0,
                'buys': 0,
                'sells': 0,
                'fees': 0.0
            }

        buys = len([t for t in today_trades if t.side == TradeSide.BUY])
        sells = len([t for t in today_trades if t.side == TradeSide.SELL])
        total_fees = sum(t.fee for t in today_trades)

        return {
            'trade_count': len(today_trades),
            'buys': buys,
            'sells': sells,
            'fees': total_fees
        }

    async def _get_rolling_25d_data(
        self,
        all_trades: List[Trade],
        current_balances: Dict[str, float],
        complete_window_start: datetime
    ) -> Dict:
        """
        Calculate metrics for complete data window.

        The window is from the complete_window_start (limited by shortest API retention)
        to now. This ensures we only calculate P&L with complete data from all exchanges.

        Args:
            all_trades: All available trades
            current_balances: Current holdings
            complete_window_start: Start of complete data window (from all APIs)
        """
        # Complete data window
        end_date = datetime.now()
        start_date = complete_window_start

        # Filter trades to complete window
        window_trades = [
            t for t in all_trades
            if start_date <= t.timestamp <= end_date
        ]

        # Calculate days including both endpoints
        window_days = (end_date.date() - start_date.date()).days + 1
        logger.info(f"Complete data window: {len(window_trades)} trades from {start_date.date()} to {end_date.date()} ({window_days} days)")

        # Get current ALKIMI balance
        current_alkimi_balance = current_balances.get('ALKIMI', 0.0)

        # Calculate P&L (mark-to-market)
        pnl_data = self._calculate_pnl(
            window_trades,
            current_alkimi_balance,
            start_date,
            end_date
        )

        # Get withdrawals in 25-day window
        withdrawal_data = self._get_withdrawals_in_window(start_date, end_date)

        return {
            'start_date': start_date,
            'end_date': end_date,
            'days': window_days,
            'trades': pnl_data,
            'withdrawals': withdrawal_data
        }

    def _get_monthly_windows(
        self,
        all_trades: List[Trade],
        current_balances: Dict[str, float],
        complete_window_start: datetime
    ) -> Dict:
        """
        Calculate monthly performance windows using only complete data coverage dates.

        Returns separate windows for each month where we have complete API coverage.
        Currently returns October (from complete_window_start to Oct 31) and
        November (Nov 1 to current).

        Args:
            all_trades: All available trades
            current_balances: Current holdings
            complete_window_start: Start of complete data window (from all APIs)

        Returns:
            Dictionary with 'november' and 'october' keys (if applicable)
        """
        from datetime import date
        from calendar import monthrange

        now = datetime.now()
        current_month = now.month
        current_year = now.year

        windows = {}

        # November window (Nov 1 to current, only if we're in November)
        if current_month == 11:
            nov_start = datetime(current_year, 11, 1)
            nov_end = now

            # Filter trades to November
            nov_trades = [
                t for t in all_trades
                if nov_start <= t.timestamp <= nov_end
            ]

            nov_days = (nov_end.date() - nov_start.date()).days + 1

            # Calculate P&L for November
            nov_pnl = self._calculate_pnl(
                nov_trades,
                current_balances.get('ALKIMI', 0.0),
                nov_start,
                nov_end
            )

            nov_withdrawals = self._get_withdrawals_in_window(nov_start, nov_end)

            windows['november'] = {
                'start_date': nov_start,
                'end_date': nov_end,
                'days': nov_days,
                'trades': nov_pnl,
                'withdrawals': nov_withdrawals,
                'month_name': 'November'
            }

        # October window (from complete_window_start to Oct 31)
        # Only include if complete_window_start is in October
        if complete_window_start.month == 10:
            oct_start = complete_window_start
            # Last day of October
            oct_end = datetime(current_year, 10, 31, 23, 59, 59)

            # Filter trades to October
            oct_trades = [
                t for t in all_trades
                if oct_start <= t.timestamp <= oct_end
            ]

            if oct_trades:  # Only create window if we have October trades
                oct_days = (oct_end.date() - oct_start.date()).days + 1

                # For October, we need to calculate what the balance was at end of October
                # We can do this by taking current balance and reversing November trades
                if 'november' in windows:
                    # Calculate October ending balance
                    nov_trades_list = [
                        t for t in all_trades
                        if datetime(current_year, 11, 1) <= t.timestamp <= now
                    ]
                    nov_net_change = sum(t.amount for t in nov_trades_list if t.side == TradeSide.BUY) - \
                                   sum(t.amount for t in nov_trades_list if t.side == TradeSide.SELL)
                    oct_ending_balance = current_balances.get('ALKIMI', 0.0) - nov_net_change
                else:
                    oct_ending_balance = current_balances.get('ALKIMI', 0.0)

                # Calculate P&L for October
                oct_pnl = self._calculate_pnl(
                    oct_trades,
                    oct_ending_balance,
                    oct_start,
                    oct_end
                )

                oct_withdrawals = self._get_withdrawals_in_window(oct_start, oct_end)

                windows['october'] = {
                    'start_date': oct_start,
                    'end_date': oct_end,
                    'days': oct_days,
                    'trades': oct_pnl,
                    'withdrawals': oct_withdrawals,
                    'month_name': 'October'
                }

        return windows

    def _calculate_pnl(
        self,
        trades: List[Trade],
        current_balance: float,
        start_date: datetime,
        end_date: datetime
    ) -> Dict:
        """
        Calculate mark-to-market P&L for the window using price from 25 days ago.

        P&L = (Current Value) - (Starting Value) + (Withdrawals in Window)

        Args:
            trades: All trades in the window
            current_balance: Current ALKIMI balance
            start_date: Window start date (25 days ago)
            end_date: Window end date (now)
        """
        if not trades:
            return {
                'trade_count': 0,
                'buys': 0,
                'sells': 0,
                'pnl_mark_to_market': 0.0,
                'pnl_trading': 0.0,
                'fees': 0.0,
                'starting_value': 0.0,
                'current_value': 0.0,
                'starting_price': 0.0,
                'current_price': 0.0
            }

        # Separate ALKIMI buys and sells
        alkimi_trades = [t for t in trades if t.symbol == 'ALKIMI']
        buys = [t for t in alkimi_trades if t.side == TradeSide.BUY]
        sells = [t for t in alkimi_trades if t.side == TradeSide.SELL]
        total_fees = sum(t.fee for t in alkimi_trades)

        # Get starting price (from oldest trade in window)
        sorted_trades = sorted(alkimi_trades, key=lambda t: t.timestamp)
        starting_price = sorted_trades[0].price if sorted_trades else 0.0

        # Get current price (from newest trade in window)
        current_price = sorted_trades[-1].price if sorted_trades else starting_price

        # Calculate starting balance (current balance - net change from trades)
        # Net change = buys - sells
        net_alkimi_change = sum(t.amount for t in buys) - sum(t.amount for t in sells)
        starting_balance = current_balance - net_alkimi_change

        # Calculate values
        starting_value = starting_balance * starting_price
        current_value = current_balance * current_price

        # Get withdrawals in window (as positive value - money that left)
        withdrawals_in_window = self._get_withdrawals_in_window(start_date, end_date)
        total_withdrawals = withdrawals_in_window.get('total_amount', 0.0)

        # Mark-to-market P&L = Change in position value + withdrawals taken
        pnl_mark_to_market = (current_value - starting_value) + total_withdrawals

        # Trading P&L = Realized gains from FIFO matching buys/sells in window
        pnl_trading = self._calculate_trading_pnl_fifo(sorted_trades)

        logger.info(
            f"P&L calculation for complete data window:\n"
            f"  Mark-to-Market:\n"
            f"    Starting: {starting_balance:,.0f} ALKIMI @ ${starting_price:.6f} = ${starting_value:,.2f}\n"
            f"    Current:  {current_balance:,.0f} ALKIMI @ ${current_price:.6f} = ${current_value:,.2f}\n"
            f"    Withdrawals: ${total_withdrawals:,.2f}\n"
            f"    M2M P&L: ${pnl_mark_to_market:,.2f}\n"
            f"  Trading P&L (Realized): ${pnl_trading:,.2f}"
        )

        return {
            'trade_count': len(alkimi_trades),
            'buys': len(buys),
            'sells': len(sells),
            'pnl_mark_to_market': pnl_mark_to_market,
            'pnl_trading': pnl_trading,
            'fees': total_fees,
            'starting_balance': starting_balance,
            'current_balance': current_balance,
            'starting_value': starting_value,
            'current_value': current_value,
            'starting_price': starting_price,
            'current_price': current_price,
            'withdrawals': total_withdrawals
        }

    def _calculate_trading_pnl_fifo(self, sorted_trades: List[Trade]) -> float:
        """
        Calculate realized trading P&L using FIFO matching of buys and sells.

        This shows actual profit from trading activity within the window,
        matching each sell to its corresponding buy using FIFO.

        Args:
            sorted_trades: Trades sorted by timestamp

        Returns:
            Total realized P&L from trading
        """
        # FIFO queue of buy positions: (amount, price_including_fee)
        buy_queue = deque()
        realized_pnl = 0.0

        for trade in sorted_trades:
            if trade.side == TradeSide.BUY:
                # Add buy to queue (amount, cost per unit including fees)
                cost_per_unit = trade.price + (trade.fee / trade.amount) if trade.amount > 0 else trade.price
                buy_queue.append((trade.amount, cost_per_unit))

            elif trade.side == TradeSide.SELL:
                # Match sell against buys using FIFO
                sell_amount = trade.amount
                sell_price = trade.price - (trade.fee / trade.amount) if trade.amount > 0 else trade.price

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

        return realized_pnl

    async def _calculate_token_revenue_target(
        self,
        all_trades: List[Trade],
        current_balances: Dict[str, float],
        holdings_by_exchange: Dict
    ) -> Dict:
        """
        Calculate token revenue target metrics for November.

        Revenue = Total USDT from selling ALKIMI tokens in November
        Target = $500k/month

        Returns:
            Dictionary with revenue metrics and projections
        """
        from datetime import date

        now = datetime.now()
        current_month = now.month
        current_year = now.year

        # Only calculate for November
        if current_month != 11:
            return {
                'available': False,
                'message': 'Revenue tracking only active during November'
            }

        # November window (Nov 1 to current)
        nov_start = datetime(current_year, 11, 1)
        nov_end = now

        # Filter November trades
        nov_trades = [
            t for t in all_trades
            if nov_start <= t.timestamp <= nov_end and t.symbol == 'ALKIMI'
        ]

        # Calculate revenue from sells (USDT received from selling ALKIMI)
        sells = [t for t in nov_trades if t.side == TradeSide.SELL]
        trading_revenue = sum(t.amount * t.price for t in sells)  # ALKIMI amount * price = USDT
        total_alkimi_sold = sum(t.amount for t in sells)
        total_fees = sum(t.fee for t in sells)

        # Hardcoded November adjustment: RAMAN OTC purchase
        # 3M ALKIMI purchased from ex-employee @ $0.027333333 = $82,000
        # This is a capital expense (buying tokens), not negative revenue
        raman_otc_cost = 82_000.00
        raman_otc_alkimi = 3_000_000
        raman_otc_price = 0.027333333

        # Calculate days in November so far
        days_elapsed = (now.date() - nov_start.date()).days + 1
        days_in_month = 30

        # Daily average based on TRADING revenue (not affected by OTC purchase)
        daily_avg_revenue = trading_revenue / days_elapsed if days_elapsed > 0 else 0
        # Projected monthly NET position (trading revenue projection minus OTC cost)
        projected_monthly = (daily_avg_revenue * days_in_month) - raman_otc_cost

        # Net cash position after OTC purchase
        net_cash_position = trading_revenue - raman_otc_cost

        # Target metrics based on net cash position
        monthly_target = 500_000  # $500k
        gap = monthly_target - net_cash_position
        gap_percentage = (gap / monthly_target * 100) if monthly_target > 0 else 0

        # Days remaining calculation
        days_remaining = days_in_month - days_elapsed
        required_daily = gap / days_remaining if days_remaining > 0 else 0

        return {
            'available': True,
            'month': 'November',
            'days_elapsed': days_elapsed,
            'days_in_month': days_in_month,
            'revenue': {
                'trading_revenue': trading_revenue,  # Trading revenue only (from sells)
                'net_cash_position': net_cash_position,  # After OTC purchase
                'total': net_cash_position,  # Keep for backward compatibility
                'target': monthly_target,
                'gap': gap,
                'gap_percentage': gap_percentage,
                'daily_avg': daily_avg_revenue,  # Based on trading revenue
                'projected_monthly': projected_monthly,  # Based on trading revenue
                'required_daily': required_daily,
                'days_remaining': days_remaining
            },
            'activity': {
                'alkimi_sold': total_alkimi_sold,
                'sell_count': len(sells),
                'fees': total_fees,
                'raman_otc': {
                    'cost': raman_otc_cost,
                    'alkimi': raman_otc_alkimi,
                    'price': raman_otc_price
                }
            },
            'holdings_by_exchange': holdings_by_exchange
        }

    def _get_withdrawals_in_window(self, start_date: datetime, end_date: datetime) -> Dict:
        """Get withdrawals that occurred in the time window."""
        window_withdrawals = []
        total_amount = 0.0

        for asset, data in self.withdrawals.items():
            for withdrawal in data['withdrawals']:
                if start_date <= withdrawal['date'] <= end_date:
                    window_withdrawals.append({
                        'date': withdrawal['date'],
                        'asset': asset,
                        'amount': withdrawal['amount'],
                        'source': withdrawal['source']
                    })
                    total_amount += withdrawal['amount']

        return {
            'count': len(window_withdrawals),
            'total_amount': total_amount,
            'withdrawals': window_withdrawals
        }

    def _get_cex_dex_breakdown(self, all_trades: List[Trade], complete_window_start: datetime) -> Dict:
        """
        Separate trades into CEX and DEX categories for reporting.

        Args:
            all_trades: All available trades
            complete_window_start: Start of complete data window

        Returns:
            Dictionary with CEX and DEX trade summaries
        """
        end_date = datetime.now()

        # Filter trades to complete window
        window_trades = [
            t for t in all_trades
            if complete_window_start <= t.timestamp <= end_date
        ]

        # Separate CEX and DEX trades
        cex_trades = []
        dex_trades = []

        for trade in window_trades:
            exchange_lower = trade.exchange.lower() if trade.exchange else ''
            if exchange_lower in DEX_EXCHANGES or 'dex' in exchange_lower:
                dex_trades.append(trade)
            else:
                cex_trades.append(trade)

        # Calculate CEX metrics
        cex_volume = sum(t.amount * t.price for t in cex_trades)
        cex_buys = [t for t in cex_trades if t.side == TradeSide.BUY]
        cex_sells = [t for t in cex_trades if t.side == TradeSide.SELL]
        cex_buy_volume = sum(t.amount * t.price for t in cex_buys)
        cex_sell_volume = sum(t.amount * t.price for t in cex_sells)

        # Group CEX by exchange
        cex_by_exchange = defaultdict(lambda: {'count': 0, 'volume': 0.0})
        for t in cex_trades:
            cex_by_exchange[t.exchange]['count'] += 1
            cex_by_exchange[t.exchange]['volume'] += t.amount * t.price

        # Calculate DEX metrics
        dex_volume = sum(t.amount * t.price for t in dex_trades)
        dex_buys = [t for t in dex_trades if t.side == TradeSide.BUY]
        dex_sells = [t for t in dex_trades if t.side == TradeSide.SELL]
        dex_buy_volume = sum(t.amount * t.price for t in dex_buys)
        dex_sell_volume = sum(t.amount * t.price for t in dex_sells)

        # Group DEX by exchange (protocol)
        dex_by_exchange = defaultdict(lambda: {'count': 0, 'volume': 0.0})
        for t in dex_trades:
            dex_by_exchange[t.exchange]['count'] += 1
            dex_by_exchange[t.exchange]['volume'] += t.amount * t.price

        return {
            'window_start': complete_window_start,
            'window_end': end_date,
            'cex': {
                'trade_count': len(cex_trades),
                'total_volume': cex_volume,
                'buy_count': len(cex_buys),
                'sell_count': len(cex_sells),
                'buy_volume': cex_buy_volume,
                'sell_volume': cex_sell_volume,
                'by_exchange': dict(cex_by_exchange)
            },
            'dex': {
                'trade_count': len(dex_trades),
                'total_volume': dex_volume,
                'buy_count': len(dex_buys),
                'sell_count': len(dex_sells),
                'buy_volume': dex_buy_volume,
                'sell_volume': dex_sell_volume,
                'by_exchange': dict(dex_by_exchange)
            },
            'total_volume': cex_volume + dex_volume,
            'cex_percentage': (cex_volume / (cex_volume + dex_volume) * 100) if (cex_volume + dex_volume) > 0 else 0,
            'dex_percentage': (dex_volume / (cex_volume + dex_volume) * 100) if (cex_volume + dex_volume) > 0 else 0
        }

    async def _get_onchain_analytics(self) -> Dict:
        """
        Fetch on-chain analytics from Sui blockchain.

        Returns pools, top holders, and watched wallet activity.
        """
        try:
            sui_monitor = await self._get_sui_monitor()
            analytics = await sui_monitor.get_onchain_analytics()

            # Convert dataclasses to dicts for JSON serialization
            pools = []
            for pool in analytics.get('pools', []):
                if hasattr(pool, '__dict__'):
                    pools.append({
                        'pool_id': pool.pool_id,
                        'dex': pool.dex,
                        'name': pool.name,
                        'token_a': pool.token_a,
                        'token_b': pool.token_b,
                        'tvl_usd': pool.tvl_usd,
                        'volume_24h': pool.volume_24h,
                        'price': pool.price,
                        'fee_tier': pool.fee_tier,
                        'price_change_24h': pool.price_change_24h
                    })
                else:
                    pools.append(pool)

            holders = []
            for holder in analytics.get('holders', []):
                if hasattr(holder, '__dict__'):
                    holders.append({
                        'address': holder.address,
                        'balance': holder.balance,
                        'percentage': holder.percentage,
                        'rank': holder.rank
                    })
                else:
                    holders.append(holder)

            return {
                'pools': pools,
                'holders': holders,
                'watched_wallets': analytics.get('watched_wallets', []),
                'timestamp': analytics.get('timestamp', datetime.now())
            }

        except Exception as e:
            logger.warning(f"Failed to fetch on-chain analytics: {e}")
            return {
                'pools': [],
                'holders': [],
                'watched_wallets': [],
                'error': str(e)
            }
