"""
Position Tracker Module

Tracks position changes in USDT and ALKIMI across all accounts,
focusing on quantity changes and trading performance metrics.
"""

from typing import Dict, List, Optional
from datetime import datetime, timedelta
from collections import defaultdict

from src.exchanges.base import ExchangeInterface, Trade, TradeSide
from src.data import DepositsLoader
from src.utils import get_logger, deduplicate_trades, analyze_trade_duplication
from config.settings import settings


logger = get_logger(__name__)


class PositionTracker:
    """
    Tracks position changes and trading performance for USDT and ALKIMI.

    Focuses on:
    - Net position changes (quantities)
    - USDT flow from ALKIMI trading
    - Average buy/sell prices
    - Realized profits
    """

    def __init__(self):
        """Initialize the position tracker."""
        self.historical_start_date = datetime.fromisoformat(settings.historical_start_date)

        # Load initial deposits for cost basis
        try:
            self.deposits_loader = DepositsLoader()
            self.initial_deposits = self.deposits_loader.load_initial_deposits()

            # Extract ALKIMI deposit data
            if 'ALKIMI' in self.initial_deposits:
                alkimi_data = self.initial_deposits['ALKIMI']
                self.initial_alkimi_amount = alkimi_data['total_amount']
                self.initial_alkimi_avg_price = alkimi_data['avg_price']
                logger.info(
                    f"Loaded initial deposits: {self.initial_alkimi_amount:,.0f} ALKIMI @ "
                    f"${self.initial_alkimi_avg_price:.6f} = ${alkimi_data['total_cost']:,.2f}"
                )
            else:
                self.initial_alkimi_amount = 0.0
                self.initial_alkimi_avg_price = 0.0
                logger.warning("No ALKIMI deposits found in deposits file")

            # Load withdrawals for accurate P&L calculation
            try:
                self.withdrawals = self.deposits_loader.load_withdrawals()
                self.total_withdrawals = self.deposits_loader.get_total_withdrawals()
                logger.info(
                    f"Loaded withdrawals: ${self.total_withdrawals:,.2f} total stablecoin withdrawals"
                )
            except Exception as e:
                logger.warning(f"Could not load withdrawals: {str(e)}. Using zero withdrawals.")
                self.withdrawals = {}
                self.total_withdrawals = 0.0

        except Exception as e:
            logger.warning(f"Could not load initial deposits: {str(e)}. Using zero cost basis.")
            self.initial_alkimi_amount = 0.0
            self.initial_alkimi_avg_price = 0.0
            self.withdrawals = {}
            self.total_withdrawals = 0.0

        logger.info(f"PositionTracker initialized. Start date: {self.historical_start_date.date()}")

    async def get_position_report(
        self,
        exchanges: List[ExchangeInterface]
    ) -> Dict:
        """
        Generate comprehensive position and trading report.

        Args:
            exchanges: List of initialized exchange clients

        Returns:
            Dictionary containing:
            - usdt_position: USDT position tracking
            - alkimi_position: ALKIMI position tracking
            - trading_performance: Buy/sell metrics
            - summary: Overall performance
        """
        logger.info("Generating position report")

        # Fetch current balances
        current_balances = await self._fetch_all_balances(exchanges)

        # Fetch all trades
        all_trades = await self._fetch_all_trades(exchanges)

        # Fetch all deposits and withdrawals
        transactions = await self._fetch_all_transactions(exchanges)

        # Calculate starting positions (reverse engineer from current + trades + deposits/withdrawals)
        starting_positions = self._calculate_starting_positions(
            current_balances,
            all_trades,
            transactions
        )

        # Calculate USDT position
        usdt_position = self._calculate_usdt_position(
            starting_positions.get('USDT', 0),
            current_balances.get('USDT', 0),
            all_trades
        )

        # Calculate ALKIMI position
        alkimi_position = self._calculate_alkimi_position(
            starting_positions.get('ALKIMI', 0),
            current_balances.get('ALKIMI', 0),
            all_trades
        )

        # Calculate trading performance
        trading_performance = self._calculate_trading_performance(all_trades)

        # Calculate exchange-level breakdown
        exchange_breakdown = await self._calculate_exchange_breakdown(
            exchanges,
            all_trades
        )

        # Calculate fee analysis
        fee_analysis = self._calculate_fee_analysis(all_trades)

        # Calculate deposit/withdrawal summary
        deposit_withdrawal_summary = self._calculate_deposit_withdrawal_summary(transactions)

        # Calculate daily change (last 24h)
        daily_change = self._calculate_daily_change(current_balances, all_trades)

        # Calculate monthly breakdown
        monthly_breakdown = self._calculate_monthly_breakdown(all_trades)

        # Generate summary
        summary = self._generate_summary(
            usdt_position,
            alkimi_position,
            trading_performance,
            fee_analysis
        )

        # Add withdrawals data
        withdrawals_data = {
            'total_withdrawals': self.total_withdrawals,
            'by_asset': self.withdrawals
        }

        report = {
            'daily_change': daily_change,
            'monthly_breakdown': monthly_breakdown,
            'usdt_position': usdt_position,
            'alkimi_position': alkimi_position,
            'trading_performance': trading_performance,
            'exchange_breakdown': exchange_breakdown,
            'fee_analysis': fee_analysis,
            'deposit_withdrawal_summary': deposit_withdrawal_summary,
            'withdrawals': withdrawals_data,
            'summary': summary,
            'timestamp': datetime.utcnow().isoformat(),
        }

        logger.info("Position report generated successfully")
        return report

    async def _fetch_all_balances(
        self,
        exchanges: List[ExchangeInterface]
    ) -> Dict[str, float]:
        """Fetch and aggregate balances from all exchanges."""
        logger.debug("Fetching balances from all exchanges")

        aggregated = defaultdict(float)

        for exchange in exchanges:
            try:
                balances = await exchange.get_balances()
                for asset, amount in balances.items():
                    aggregated[asset] += amount
            except Exception as e:
                logger.error(f"Failed to fetch balances from {exchange.__class__.__name__}: {e}")

        return dict(aggregated)

    async def _fetch_all_trades(
        self,
        exchanges: List[ExchangeInterface]
    ) -> List[Trade]:
        """Fetch all trades since historical start date."""
        logger.debug(f"Fetching trades since {self.historical_start_date.date()}")

        all_trades = []

        for exchange in exchanges:
            try:
                trades = await exchange.get_trades(self.historical_start_date)
                all_trades.extend(trades)
            except Exception as e:
                logger.error(f"Failed to fetch trades from {exchange.__class__.__name__}: {e}")

        # Sort by timestamp
        all_trades.sort(key=lambda t: t.timestamp)

        # Deduplicate trades from linked sub-accounts
        logger.info(f"Fetched {len(all_trades)} total trades (before deduplication)")
        all_trades = deduplicate_trades(all_trades)
        logger.info(f"After deduplication: {len(all_trades)} unique trades")

        return all_trades

    async def _fetch_all_transactions(
        self,
        exchanges: List[ExchangeInterface]
    ) -> Dict[str, List]:
        """Fetch all deposits and withdrawals since historical start date."""
        logger.debug(f"Fetching deposits/withdrawals since {self.historical_start_date.date()}")

        all_deposits = []
        all_withdrawals = []

        for exchange in exchanges:
            try:
                deposits = await exchange.get_deposits(self.historical_start_date)
                all_deposits.extend(deposits)
            except Exception as e:
                logger.debug(f"Failed to fetch deposits from {exchange.__class__.__name__}: {e}")

            try:
                withdrawals = await exchange.get_withdrawals(self.historical_start_date)
                all_withdrawals.extend(withdrawals)
            except Exception as e:
                logger.debug(f"Failed to fetch withdrawals from {exchange.__class__.__name__}: {e}")

        # Sort by timestamp
        all_deposits.sort(key=lambda t: t.timestamp)
        all_withdrawals.sort(key=lambda t: t.timestamp)

        logger.info(f"Fetched {len(all_deposits)} deposits, {len(all_withdrawals)} withdrawals")

        return {
            'deposits': all_deposits,
            'withdrawals': all_withdrawals
        }

    def _calculate_starting_positions(
        self,
        current_balances: Dict[str, float],
        trades: List[Trade],
        transactions: Dict[str, List]
    ) -> Dict[str, float]:
        """
        Calculate starting positions by working backwards from current balances.

        Starting Position = Current Balance - Net Trading - Deposits + Withdrawals
        """
        logger.debug("Calculating starting positions")

        starting = {}
        deposits = transactions.get('deposits', [])
        withdrawals = transactions.get('withdrawals', [])

        for asset in ['USDT', 'ALKIMI']:
            current = current_balances.get(asset, 0)

            # Calculate net change from trades
            net_trading = 0
            for trade in trades:
                if trade.symbol != asset:
                    continue

                if trade.side == TradeSide.BUY:
                    # Bought this asset (increases position)
                    net_trading += trade.amount
                else:  # SELL
                    # Sold this asset (decreases position)
                    net_trading -= trade.amount

            # Calculate net deposits/withdrawals
            total_deposits = sum(t.amount for t in deposits if t.symbol == asset)
            total_withdrawals = sum(t.amount for t in withdrawals if t.symbol == asset)
            net_deposits = total_deposits - total_withdrawals

            # Starting = Current - Net Trading - Net Deposits
            starting[asset] = current - net_trading - net_deposits

            logger.debug(
                f"{asset} starting position: {starting[asset]:,.2f} "
                f"(current: {current:,.2f}, net trading: {net_trading:+,.2f}, "
                f"deposits: +{total_deposits:,.2f}, withdrawals: -{total_withdrawals:,.2f})"
            )

        return starting

    def _calculate_usdt_position(
        self,
        starting_balance: float,
        current_balance: float,
        trades: List[Trade]
    ) -> Dict:
        """
        Calculate USDT position changes.

        Tracks how USDT balance changed from ALKIMI trading activity.
        """
        logger.debug("Calculating USDT position")

        # USDT spent on buying ALKIMI
        usdt_spent = 0
        # USDT received from selling ALKIMI
        usdt_received = 0

        for trade in trades:
            if trade.symbol == 'ALKIMI':
                # ALKIMI trades affect USDT balance
                trade_value = trade.amount * trade.price

                if trade.side == TradeSide.BUY:
                    # Bought ALKIMI with USDT (USDT decreases)
                    usdt_spent += trade_value + trade.fee  # Include fees
                else:  # SELL
                    # Sold ALKIMI for USDT (USDT increases)
                    usdt_received += trade_value - trade.fee  # Subtract fees

        # Net USDT change from ALKIMI trading
        net_trading_change = usdt_received - usdt_spent

        # Total change (includes trading + any other changes)
        total_change = current_balance - starting_balance

        # Other changes (deposits, withdrawals, interest, etc.)
        other_changes = total_change - net_trading_change

        position = {
            'starting_balance': starting_balance,
            'current_balance': current_balance,
            'total_change': total_change,
            'change_percent': (total_change / starting_balance * 100) if starting_balance > 0 else 0,
            'trading_activity': {
                'spent_on_alkimi': usdt_spent,
                'received_from_alkimi': usdt_received,
                'net_from_trading': net_trading_change,
            },
            'other_changes': other_changes,  # Deposits, withdrawals, etc.
        }

        logger.info(
            f"USDT position: {starting_balance:,.2f} → {current_balance:,.2f} "
            f"({total_change:+,.2f}, {position['change_percent']:+.2f}%)"
        )

        return position

    def _calculate_alkimi_position(
        self,
        starting_balance: float,
        current_balance: float,
        trades: List[Trade]
    ) -> Dict:
        """
        Calculate ALKIMI position changes.

        Tracks quantity changes and value changes.
        """
        logger.debug("Calculating ALKIMI position")

        # Get current ALKIMI price (from most recent trade)
        current_price = self._get_latest_price('ALKIMI', trades)

        # Calculate starting value (need to estimate starting price)
        starting_price = self._get_earliest_price('ALKIMI', trades)

        starting_value = starting_balance * starting_price if starting_price else 0
        current_value = current_balance * current_price if current_price else 0

        # Quantity changes
        quantity_change = current_balance - starting_balance
        quantity_change_percent = (quantity_change / starting_balance * 100) if starting_balance > 0 else 0

        # Value changes
        value_change = current_value - starting_value
        value_change_percent = (value_change / starting_value * 100) if starting_value > 0 else 0

        position = {
            'starting_balance': starting_balance,
            'current_balance': current_balance,
            'quantity_change': quantity_change,
            'quantity_change_percent': quantity_change_percent,
            'starting_value_usd': starting_value,
            'current_value_usd': current_value,
            'value_change_usd': value_change,
            'value_change_percent': value_change_percent,
            'starting_price': starting_price,
            'current_price': current_price,
            'price_change': current_price - starting_price if (current_price and starting_price) else 0,
            'price_change_percent': ((current_price - starting_price) / starting_price * 100)
                                   if starting_price else 0,
        }

        logger.info(
            f"ALKIMI position: {starting_balance:,.0f} → {current_balance:,.0f} "
            f"({quantity_change:+,.0f}, {quantity_change_percent:+.2f}%)"
        )

        return position

    def _calculate_trading_performance(self, trades: List[Trade]) -> Dict:
        """
        Calculate ALKIMI trading performance metrics.

        Focuses on:
        - Average buy price
        - Average sell price
        - Realized profit from completed trades
        """
        logger.debug("Calculating trading performance")

        alkimi_trades = [t for t in trades if t.symbol == 'ALKIMI']

        # Separate buys and sells
        buys = [t for t in alkimi_trades if t.side == TradeSide.BUY]
        sells = [t for t in alkimi_trades if t.side == TradeSide.SELL]

        # Buy metrics
        total_bought = sum(t.amount for t in buys)
        total_cost = sum(t.amount * t.price + t.fee for t in buys)  # Include fees
        avg_buy_price = (total_cost / total_bought) if total_bought > 0 else 0

        # Sell metrics
        total_sold = sum(t.amount for t in sells)
        total_revenue = sum(t.amount * t.price - t.fee for t in sells)  # Subtract fees
        avg_sell_price = (total_revenue / total_sold) if total_sold > 0 else 0

        # Realized profit (from amount sold)
        # For the amount sold, what did we pay vs what did we receive?
        if total_sold > 0:
            # CRITICAL FIX: Use FIFO starting with initial deposit, then trading buys
            cost_of_sold = 0
            remaining_to_match = total_sold

            # First, match against initial deposit (if available)
            if hasattr(self, 'initial_alkimi_amount') and hasattr(self, 'initial_alkimi_avg_price'):
                if self.initial_alkimi_amount > 0 and remaining_to_match > 0:
                    amount_from_deposit = min(self.initial_alkimi_amount, remaining_to_match)
                    cost_of_sold += amount_from_deposit * self.initial_alkimi_avg_price
                    remaining_to_match -= amount_from_deposit
                    logger.debug(
                        f"FIFO: Matched {amount_from_deposit:,.0f} ALKIMI against initial deposit "
                        f"@ ${self.initial_alkimi_avg_price:.6f}"
                    )

            # Then match remaining against trading buys
            for buy in buys:
                if remaining_to_match <= 0:
                    break

                amount_to_use = min(buy.amount, remaining_to_match)
                cost_of_sold += amount_to_use * buy.price + (buy.fee * amount_to_use / buy.amount)
                remaining_to_match -= amount_to_use

            realized_profit = total_revenue - cost_of_sold
            realized_profit_percent = (realized_profit / cost_of_sold * 100) if cost_of_sold > 0 else 0

            logger.info(
                f"Realized P&L: Sold {total_sold:,.0f} ALKIMI for ${total_revenue:,.2f}, "
                f"cost basis ${cost_of_sold:,.2f}, profit ${realized_profit:,.2f} ({realized_profit_percent:+.2f}%)"
            )
        else:
            realized_profit = 0
            realized_profit_percent = 0

        performance = {
            'buys': {
                'count': len(buys),
                'total_quantity': total_bought,
                'total_cost_usd': total_cost,
                'average_price': avg_buy_price,
            },
            'sells': {
                'count': len(sells),
                'total_quantity': total_sold,
                'total_revenue_usd': total_revenue,
                'average_price': avg_sell_price,
            },
            'realized_profit': {
                'profit_usd': realized_profit,
                'profit_percent': realized_profit_percent,
                'spread': avg_sell_price - avg_buy_price,
                'spread_percent': ((avg_sell_price - avg_buy_price) / avg_buy_price * 100)
                                 if avg_buy_price > 0 else 0,
            },
        }

        logger.info(
            f"Trading performance: {len(buys)} buys @ ${avg_buy_price:.4f}, "
            f"{len(sells)} sells @ ${avg_sell_price:.4f}, "
            f"realized profit: ${realized_profit:,.2f}"
        )

        return performance

    async def _calculate_exchange_breakdown(
        self,
        exchanges: List[ExchangeInterface],
        all_trades: List[Trade]
    ) -> Dict:
        """
        Calculate per-exchange breakdown of holdings and activity.
        """
        logger.debug("Calculating exchange-level breakdown")

        breakdown = {}

        for exchange in exchanges:
            # Use full_name to include account identifier (e.g., "mexc_mm1")
            exchange_key = exchange.full_name

            try:
                # Get balances for this exchange
                balances = await exchange.get_balances()

                # Get trades for this exchange (match by base exchange name)
                base_exchange_name = exchange.exchange_name
                exchange_trades = [t for t in all_trades if t.trade_id and base_exchange_name in t.trade_id.lower()]
                if not exchange_trades:
                    # Fallback: try to match by exchange type in the trade object
                    exchange_trades = []  # Will need manual attribution in production

                # Calculate metrics for this exchange
                buy_trades = [t for t in exchange_trades if t.side == TradeSide.BUY and t.symbol == 'ALKIMI']
                sell_trades = [t for t in exchange_trades if t.side == TradeSide.SELL and t.symbol == 'ALKIMI']

                buy_volume = sum(t.amount * t.price for t in buy_trades)
                sell_volume = sum(t.amount * t.price for t in sell_trades)
                total_fees = sum(t.fee for t in exchange_trades)

                alkimi_price = self._get_latest_price('ALKIMI', all_trades) or 0

                breakdown[exchange_key] = {
                    'usdt_balance': balances.get('USDT', 0),
                    'alkimi_balance': balances.get('ALKIMI', 0),
                    'alkimi_value_usd': balances.get('ALKIMI', 0) * alkimi_price,
                    'trade_count': len(exchange_trades),
                    'buy_count': len(buy_trades),
                    'sell_count': len(sell_trades),
                    'buy_volume_usd': buy_volume,
                    'sell_volume_usd': sell_volume,
                    'total_volume_usd': buy_volume + sell_volume,
                    'fees_paid_usd': total_fees,
                }

                logger.debug(
                    f"{exchange_key}: {balances.get('ALKIMI', 0):,.0f} ALKIMI, "
                    f"{len(exchange_trades)} trades, ${total_fees:.2f} fees"
                )

            except Exception as e:
                logger.error(f"Failed to get breakdown for {exchange_key}: {e}")
                breakdown[exchange_key] = {
                    'usdt_balance': 0,
                    'alkimi_balance': 0,
                    'alkimi_value_usd': 0,
                    'trade_count': 0,
                    'buy_count': 0,
                    'sell_count': 0,
                    'buy_volume_usd': 0,
                    'sell_volume_usd': 0,
                    'total_volume_usd': 0,
                    'fees_paid_usd': 0,
                }

        logger.info(f"Exchange breakdown calculated for {len(breakdown)} exchanges")
        return breakdown

    def _calculate_fee_analysis(self, trades: List[Trade]) -> Dict:
        """
        Calculate comprehensive fee analysis.
        """
        logger.debug("Calculating fee analysis")

        alkimi_trades = [t for t in trades if t.symbol == 'ALKIMI']

        # Total fees
        total_fees = sum(t.fee for t in alkimi_trades)

        # Fees by trade side
        buy_fees = sum(t.fee for t in alkimi_trades if t.side == TradeSide.BUY)
        sell_fees = sum(t.fee for t in alkimi_trades if t.side == TradeSide.SELL)

        # Calculate volume for fee percentage
        total_volume = sum(t.amount * t.price for t in alkimi_trades)
        fee_as_percent = (total_fees / total_volume * 100) if total_volume > 0 else 0

        # Average fee per trade
        avg_fee_per_trade = total_fees / len(alkimi_trades) if alkimi_trades else 0

        # Fees by exchange (try to extract from trade_id)
        fees_by_exchange = {}
        for exchange_name in ['mexc', 'kraken', 'kucoin', 'gateio']:
            exchange_trades = [t for t in alkimi_trades if t.trade_id and exchange_name in t.trade_id.lower()]
            if exchange_trades:
                fees_by_exchange[exchange_name] = sum(t.fee for t in exchange_trades)

        analysis = {
            'total_fees_usd': total_fees,
            'buy_fees_usd': buy_fees,
            'sell_fees_usd': sell_fees,
            'fee_as_percent_of_volume': fee_as_percent,
            'avg_fee_per_trade': avg_fee_per_trade,
            'total_trades': len(alkimi_trades),
            'fees_by_exchange': fees_by_exchange,
        }

        logger.info(
            f"Fee analysis: ${total_fees:.2f} total ({fee_as_percent:.3f}% of volume), "
            f"${avg_fee_per_trade:.2f} avg per trade"
        )

        return analysis

    def _calculate_deposit_withdrawal_summary(self, transactions: Dict[str, List]) -> Dict:
        """
        Calculate comprehensive deposit/withdrawal summary.
        """
        logger.debug("Calculating deposit/withdrawal summary")

        deposits = transactions.get('deposits', [])
        withdrawals = transactions.get('withdrawals', [])

        # Calculate by asset
        usdt_deposits = sum(t.amount for t in deposits if t.symbol == 'USDT')
        usdt_withdrawals = sum(t.amount for t in withdrawals if t.symbol == 'USDT')
        usdt_net_flow = usdt_deposits - usdt_withdrawals

        alkimi_deposits = sum(t.amount for t in deposits if t.symbol == 'ALKIMI')
        alkimi_withdrawals = sum(t.amount for t in withdrawals if t.symbol == 'ALKIMI')
        alkimi_net_flow = alkimi_deposits - alkimi_withdrawals

        summary = {
            'usdt': {
                'total_deposits': usdt_deposits,
                'deposit_count': len([t for t in deposits if t.symbol == 'USDT']),
                'total_withdrawals': usdt_withdrawals,
                'withdrawal_count': len([t for t in withdrawals if t.symbol == 'USDT']),
                'net_flow': usdt_net_flow,
            },
            'alkimi': {
                'total_deposits': alkimi_deposits,
                'deposit_count': len([t for t in deposits if t.symbol == 'ALKIMI']),
                'total_withdrawals': alkimi_withdrawals,
                'withdrawal_count': len([t for t in withdrawals if t.symbol == 'ALKIMI']),
                'net_flow': alkimi_net_flow,
            },
            'total_transactions': len(deposits) + len(withdrawals),
        }

        logger.info(
            f"Deposits/Withdrawals: USDT net flow {usdt_net_flow:+,.2f}, "
            f"ALKIMI net flow {alkimi_net_flow:+,.0f}"
        )

        return summary

    def _calculate_daily_change(
        self,
        current_balances: Dict[str, float],
        all_trades: List[Trade]
    ) -> Dict:
        """
        Calculate position changes over the last 24 hours based on trades.

        Args:
            current_balances: Current balances for all assets
            all_trades: All trades since historical start

        Returns:
            Dictionary with daily change metrics
        """
        logger.debug("Calculating daily change (last 24h)")

        # Get trades from last 24 hours (UTC)
        now = datetime.utcnow()
        yesterday = now - timedelta(days=1)
        daily_trades = [t for t in all_trades if t.timestamp >= yesterday]

        logger.info(f"Daily tracker: Found {len(daily_trades)} trades in last 24h (since {yesterday.strftime('%Y-%m-%d %H:%M:%S')} UTC)")

        # Calculate USDT change from ALKIMI trades
        usdt_change_from_trading = 0
        for trade in daily_trades:
            if trade.symbol == 'ALKIMI':
                if trade.side == TradeSide.BUY:
                    usdt_change_from_trading -= (trade.amount * trade.price + trade.fee)
                else:  # SELL
                    usdt_change_from_trading += (trade.amount * trade.price - trade.fee)

        # Calculate ALKIMI quantity change from trades
        alkimi_quantity_change = 0
        for trade in daily_trades:
            if trade.symbol == 'ALKIMI':
                if trade.side == TradeSide.BUY:
                    alkimi_quantity_change += trade.amount
                else:  # SELL
                    alkimi_quantity_change -= trade.amount

        # Estimate yesterday's balances
        yesterday_usdt = current_balances.get('USDT', 0) - usdt_change_from_trading
        yesterday_alkimi = current_balances.get('ALKIMI', 0) - alkimi_quantity_change

        # Calculate percentage changes
        usdt_change_percent = (usdt_change_from_trading / yesterday_usdt * 100) if yesterday_usdt > 0 else 0
        alkimi_change_percent = (alkimi_quantity_change / yesterday_alkimi * 100) if yesterday_alkimi > 0 else 0

        # Count trades by type
        alkimi_trades = [t for t in daily_trades if t.symbol == 'ALKIMI']
        buy_count = len([t for t in alkimi_trades if t.side == TradeSide.BUY])
        sell_count = len([t for t in alkimi_trades if t.side == TradeSide.SELL])

        # Calculate realized P&L for the day
        daily_pnl = self._calculate_trading_performance(daily_trades)

        daily_change = {
            'period': '24h',
            'usdt': {
                'previous': yesterday_usdt,
                'current': current_balances.get('USDT', 0),
                'change': usdt_change_from_trading,
                'change_percent': usdt_change_percent,
            },
            'alkimi': {
                'previous': yesterday_alkimi,
                'current': current_balances.get('ALKIMI', 0),
                'change': alkimi_quantity_change,
                'change_percent': alkimi_change_percent,
            },
            'trading': {
                'total_trades': len(daily_trades),
                'buy_count': buy_count,
                'sell_count': sell_count,
                'realized_pnl': daily_pnl['realized_profit']['profit_usd'],
                'fees': sum(t.fee for t in daily_trades),
            },
            'timestamp': now.isoformat(),
        }

        logger.info(
            f"Daily change: USDT {usdt_change_from_trading:+,.2f} ({usdt_change_percent:+.2f}%), "
            f"ALKIMI {alkimi_quantity_change:+,.0f} ({alkimi_change_percent:+.2f}%), "
            f"{len(daily_trades)} trades"
        )

        return daily_change

    def _calculate_monthly_breakdown(self, all_trades: List[Trade]) -> Dict:
        """
        Calculate trading performance breakdown by month.
        Shows all months since historical start date.

        Args:
            all_trades: All trades since historical start

        Returns:
            Dictionary with monthly breakdown
        """
        logger.debug("Calculating monthly breakdown")

        from collections import defaultdict
        from calendar import month_name

        # Group trades by month
        monthly_trades = defaultdict(list)
        for trade in all_trades:
            month_key = trade.timestamp.strftime('%Y-%m')
            monthly_trades[month_key].append(trade)

        # Group withdrawals by month
        monthly_withdrawals = defaultdict(list)
        for asset, data in self.withdrawals.items():
            for withdrawal in data['withdrawals']:
                month_key = withdrawal['date'].strftime('%Y-%m')
                monthly_withdrawals[month_key].append({
                    'asset': asset,
                    'amount': withdrawal['amount'],
                    'source': withdrawal['source'],
                    'date': withdrawal['date']
                })

        # Get all unique months from both trades and withdrawals
        all_months = set(monthly_trades.keys()) | set(monthly_withdrawals.keys())

        # Sort months (newest first)
        sorted_months = sorted(all_months, reverse=True)

        # Process all months in detail
        monthly_data = []
        current_month = datetime.utcnow().strftime('%Y-%m')

        for i, month_key in enumerate(sorted_months):
            trades = monthly_trades[month_key]
            year, month_num = month_key.split('-')
            month_num = int(month_num)

            # Calculate performance for this month
            perf = self._calculate_trading_performance(trades)

            # Check if this is current month
            is_current = (month_key == current_month)

            # Calculate days in period
            if is_current:
                days_in_period = datetime.utcnow().day
            else:
                # Use actual days in the month based on trades
                month_trades_sorted = sorted(trades, key=lambda t: t.timestamp)
                if month_trades_sorted:
                    first_day = month_trades_sorted[0].timestamp.day
                    last_day = month_trades_sorted[-1].timestamp.day
                    days_in_period = last_day - first_day + 1
                else:
                    days_in_period = 30  # fallback

            # Calculate cash flow (money in/out)
            alkimi_trades = [t for t in trades if t.symbol == 'ALKIMI']
            spent_on_buys = sum((t.amount * t.price + t.fee) for t in alkimi_trades if t.side == TradeSide.BUY)
            received_from_sells = sum((t.amount * t.price - t.fee) for t in alkimi_trades if t.side == TradeSide.SELL)
            net_cash_flow = received_from_sells - spent_on_buys

            # Calculate volumes
            buy_volume = sum(t.amount * t.price for t in alkimi_trades if t.side == TradeSide.BUY)
            sell_volume = sum(t.amount * t.price for t in alkimi_trades if t.side == TradeSide.SELL)
            total_volume = buy_volume + sell_volume

            # Calculate weighted averages (accounts for quantity traded)
            buy_qty = perf['buys']['total_quantity']
            sell_qty = perf['sells']['total_quantity']
            weighted_avg_buy = (buy_volume / buy_qty) if buy_qty > 0 else 0
            weighted_avg_sell = (sell_volume / sell_qty) if sell_qty > 0 else 0

            # Get withdrawals for this month
            month_withdrawals = monthly_withdrawals.get(month_key, [])
            total_withdrawals = sum(w['amount'] for w in month_withdrawals)
            withdrawals_by_asset = {}
            for w in month_withdrawals:
                asset = w['asset']
                if asset not in withdrawals_by_asset:
                    withdrawals_by_asset[asset] = {'amount': 0, 'count': 0}
                withdrawals_by_asset[asset]['amount'] += w['amount']
                withdrawals_by_asset[asset]['count'] += 1

            monthly_data.append({
                'month': f"{month_name[month_num]} {year}",
                'month_key': month_key,
                'is_current': is_current,
                'days': days_in_period,
                'trades': {
                    'total': len(trades),
                    'buys': perf['buys']['count'],
                    'sells': perf['sells']['count'],
                },
                'prices': {
                    'weighted_avg_buy': weighted_avg_buy,
                    'weighted_avg_sell': weighted_avg_sell,
                    'simple_avg_buy': perf['buys']['average_price'],  # Keep for comparison
                    'simple_avg_sell': perf['sells']['average_price'],
                },
                'cash_flow': {
                    'spent_on_buys': spent_on_buys,
                    'received_from_sells': received_from_sells,
                    'net': net_cash_flow,
                },
                'volume': {
                    'buy': buy_volume,
                    'sell': sell_volume,
                    'total': total_volume,
                },
                'inventory': {
                    'bought': buy_qty,
                    'sold': sell_qty,
                    'net_change': buy_qty - sell_qty,
                },
                'realized_pnl': perf['realized_profit']['profit_usd'],
                'fees': sum(t.fee for t in trades),
                'withdrawals': {
                    'total_amount': total_withdrawals,
                    'count': len(month_withdrawals),
                    'by_asset': withdrawals_by_asset,
                },
            })

        logger.info(f"Monthly breakdown calculated for {len(monthly_data)} months")

        return {
            'months': monthly_data,
            'total_months': len(sorted_months),
        }

    def _generate_summary(
        self,
        usdt_position: Dict,
        alkimi_position: Dict,
        trading_performance: Dict,
        fee_analysis: Dict
    ) -> Dict:
        """Generate overall summary metrics."""

        # Calculate total assets including withdrawals
        # Withdrawals are stablecoins that were removed from exchanges but are still part of realized value
        total_portfolio_value = (
            usdt_position['current_balance'] +
            alkimi_position['current_value_usd'] +
            self.total_withdrawals
        )

        summary = {
            'net_usdt_change': usdt_position['total_change'],
            'net_usdt_change_percent': usdt_position['change_percent'],
            'net_alkimi_quantity_change': alkimi_position['quantity_change'],
            'net_alkimi_value_change': alkimi_position['value_change_usd'],
            'realized_profit': trading_performance['realized_profit']['profit_usd'],
            'total_fees_paid': fee_analysis['total_fees_usd'],
            'net_profit_after_fees': trading_performance['realized_profit']['profit_usd'] - fee_analysis['total_fees_usd'],
            'current_portfolio_value': total_portfolio_value,
            'withdrawals_included': self.total_withdrawals,
            'alkimi_avg_buy_price': trading_performance['buys']['average_price'],
            'alkimi_avg_sell_price': trading_performance['sells']['average_price'],
            'total_trades': (
                trading_performance['buys']['count'] +
                trading_performance['sells']['count']
            ),
        }

        return summary

    def _get_latest_price(self, asset: str, trades: List[Trade]) -> Optional[float]:
        """Get the most recent price for an asset from trades."""
        asset_trades = [t for t in trades if t.symbol == asset]
        if asset_trades:
            # Get most recent trade
            latest = max(asset_trades, key=lambda t: t.timestamp)
            return latest.price
        return None

    def _get_earliest_price(self, asset: str, trades: List[Trade]) -> Optional[float]:
        """Get the earliest price for an asset from trades."""
        asset_trades = [t for t in trades if t.symbol == asset]
        if asset_trades:
            # Get earliest trade
            earliest = min(asset_trades, key=lambda t: t.timestamp)
            return earliest.price
        return None
