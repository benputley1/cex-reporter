"""
Trade Repository Module

Handles all trade-related data operations including fetching, caching, and querying.
"""

import pandas as pd
from datetime import datetime
from typing import List, Optional, Dict, Any

from src.data.trade_cache import TradeCache
from src.exchanges.base import Trade
from src.utils import get_logger

logger = get_logger(__name__)


class TradeRepository:
    """Repository for trade data operations."""

    def __init__(self, trade_cache: TradeCache):
        """
        Initialize trade repository.

        Args:
            trade_cache: TradeCache instance for data persistence
        """
        self.trade_cache = trade_cache

    async def get_trades(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        exchange: Optional[str] = None,
        account_name: Optional[str] = None,
        include_transfers: bool = False,
        transaction_type: Optional[str] = None
    ) -> List[Trade]:
        """
        Retrieve trades from cache.

        Args:
            since: Fetch trades from this datetime onwards
            until: Fetch trades up to this datetime
            exchange: Filter by exchange name
            account_name: Filter by account name
            include_transfers: If False (default), only return 'trade' type transactions
            transaction_type: Filter by specific transaction type ('trade', 'deposit', 'withdrawal', 'transfer')

        Returns:
            List of Trade objects
        """
        return await self.trade_cache.get_trades(
            since=since,
            until=until,
            exchange=exchange,
            account_name=account_name,
            include_transfers=include_transfers,
            transaction_type=transaction_type
        )

    async def get_trades_df(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        exchange: Optional[str] = None,
        account: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get trades as pandas DataFrame with optional filters.

        Args:
            since: Fetch trades from this datetime onwards
            until: Fetch trades up to this datetime
            exchange: Filter by exchange name (e.g., 'mexc', 'kucoin')
            account: Filter by account name (e.g., 'MM1', 'TM1')

        Returns:
            DataFrame with columns: timestamp, exchange, account_name, symbol,
                                   side, amount, price, fee, fee_currency, trade_id
        """
        trades = await self.trade_cache.get_trades(
            since=since,
            until=until,
            exchange=exchange,
            account_name=account
        )

        if not trades:
            # Return empty DataFrame with expected schema
            return pd.DataFrame(columns=[
                'timestamp', 'exchange', 'account_name', 'symbol',
                'side', 'amount', 'price', 'fee', 'fee_currency', 'trade_id'
            ])

        # Convert Trade objects to DataFrame
        data = []
        for trade in trades:
            data.append({
                'timestamp': trade.timestamp,
                'exchange': trade.exchange,
                'account_name': 'MAIN',  # Default if not in trade object
                'symbol': trade.symbol,
                'side': trade.side.value,
                'amount': trade.amount,
                'price': trade.price,
                'fee': trade.fee,
                'fee_currency': trade.fee_currency,
                'trade_id': trade.trade_id
            })

        df = pd.DataFrame(data)
        logger.debug(f"Retrieved {len(df)} trades as DataFrame")
        return df

    async def save_trades(
        self,
        trades: List[Trade],
        exchange: str,
        account_name: str,
        transaction_type: str = 'trade'
    ) -> int:
        """
        Save trades to cache.

        Args:
            trades: List of Trade objects
            exchange: Exchange name (e.g., 'mexc', 'kucoin')
            account_name: Account identifier (e.g., 'MM1', 'TM1')
            transaction_type: Type of transaction ('trade', 'deposit', 'withdrawal', 'transfer')

        Returns:
            Number of new trades saved
        """
        return await self.trade_cache.save_trades(
            trades=trades,
            exchange=exchange,
            account_name=account_name,
            transaction_type=transaction_type
        )

    async def get_trade_summary(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Get summary statistics for trades.

        Args:
            since: Start datetime for summary
            until: End datetime for summary

        Returns:
            Dict with summary stats:
                - total_volume: Total trade volume in USD
                - trade_count: Number of trades
                - buy_volume: Total buy volume
                - sell_volume: Total sell volume
                - by_exchange: Breakdown by exchange
                - by_account: Breakdown by account
                - avg_price: Average trade price
        """
        df = await self.get_trades_df(since=since, until=until)

        if df.empty:
            return {
                'total_volume': 0,
                'trade_count': 0,
                'buy_volume': 0,
                'sell_volume': 0,
                'by_exchange': {},
                'by_account': {},
                'avg_price': 0
            }

        # Calculate volume (amount * price)
        df['volume'] = df['amount'] * df['price']

        # Split by side
        buys = df[df['side'] == 'buy']
        sells = df[df['side'] == 'sell']

        # By exchange breakdown
        by_exchange = {}
        for exchange in df['exchange'].unique():
            exchange_df = df[df['exchange'] == exchange]
            by_exchange[exchange] = {
                'trade_count': len(exchange_df),
                'volume': float(exchange_df['volume'].sum()),
                'buy_count': len(exchange_df[exchange_df['side'] == 'buy']),
                'sell_count': len(exchange_df[exchange_df['side'] == 'sell'])
            }

        # By account breakdown
        by_account = {}
        for account in df['account_name'].unique():
            account_df = df[df['account_name'] == account]
            by_account[account] = {
                'trade_count': len(account_df),
                'volume': float(account_df['volume'].sum()),
                'buy_count': len(account_df[account_df['side'] == 'buy']),
                'sell_count': len(account_df[account_df['side'] == 'sell'])
            }

        summary = {
            'total_volume': float(df['volume'].sum()),
            'trade_count': len(df),
            'buy_volume': float(buys['volume'].sum()) if not buys.empty else 0,
            'sell_volume': float(sells['volume'].sum()) if not sells.empty else 0,
            'buy_count': len(buys),
            'sell_count': len(sells),
            'by_exchange': by_exchange,
            'by_account': by_account,
            'avg_price': float(df['price'].mean()),
            'min_price': float(df['price'].min()),
            'max_price': float(df['price'].max()),
            'total_fees': float(df['fee'].sum()),
            'date_range': {
                'start': df['timestamp'].min().isoformat() if not df.empty else None,
                'end': df['timestamp'].max().isoformat() if not df.empty else None
            }
        }

        logger.info(
            f"Trade summary: {summary['trade_count']} trades, "
            f"${summary['total_volume']:.2f} volume"
        )
        return summary

    async def get_transfers(
        self,
        exchange: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        transfer_type: Optional[str] = None
    ) -> List[dict]:
        """
        Retrieve transfers (deposits/withdrawals) from cache.

        Args:
            exchange: Filter by exchange name
            since: Fetch transfers from this datetime onwards
            until: Fetch transfers up to this datetime
            transfer_type: Filter by specific type ('deposit', 'withdrawal', 'transfer')

        Returns:
            List of transfer dictionaries
        """
        return await self.trade_cache.get_transfers(
            exchange=exchange,
            since=since,
            until=until,
            transfer_type=transfer_type
        )

    async def save_transfers(
        self,
        transfers: List[dict],
        exchange: str,
        account_name: str
    ) -> int:
        """
        Save deposits/withdrawals to cache.

        Args:
            transfers: List of transfer dictionaries
            exchange: Exchange name
            account_name: Account identifier

        Returns:
            Number of new transfers saved
        """
        return await self.trade_cache.save_transfers(
            transfers=transfers,
            exchange=exchange,
            account_name=account_name
        )

    async def get_net_flow(
        self,
        exchange: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        symbol: Optional[str] = None
    ) -> dict:
        """
        Calculate net deposit/withdrawal flow.

        Args:
            exchange: Exchange name
            since: Calculate flow from this datetime onwards
            until: Calculate flow up to this datetime
            symbol: Filter by specific symbol (optional)

        Returns:
            Dictionary with net flow statistics
        """
        return await self.trade_cache.get_net_flow(
            exchange=exchange,
            since=since,
            until=until,
            symbol=symbol
        )

    async def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with total_trades, oldest_trade, newest_trade, account_count
        """
        return await self.trade_cache.get_stats()

    async def deduplicate_trades(self) -> int:
        """
        Remove duplicate trades from the database.

        Returns:
            Number of duplicate trades removed
        """
        return await self.trade_cache.deduplicate_trades()
