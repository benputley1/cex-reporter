"""
Data Provider Module

Unified data access layer for the ALKIMI Slack bot.
Consolidates access to trade cache, snapshots, DEX data, and market prices.
"""

import os
import json
import sqlite3
import pandas as pd
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from src.data.trade_cache import TradeCache
from src.data.daily_snapshot import DailySnapshot
from src.data.coingecko_client import CoinGeckoClient
from src.exchanges.sui_monitor import SuiTokenMonitor
from src.exchanges.base import Trade, TradeSide
from src.utils import get_logger

logger = get_logger(__name__)


class DataProvider:
    """
    Unified data access layer for trading bot.

    Provides convenient async methods to access:
    - Trade data from SQLite cache
    - Daily balance snapshots
    - DEX trades from Sui blockchain
    - Current market prices from CoinGecko
    - Analytics and summaries
    """

    def __init__(
        self,
        db_path: str = "data/trade_cache.db",
        snapshots_dir: str = "data/snapshots",
        sui_config: Optional[Dict[str, Any]] = None
    ):
        """
        Initialize data provider.

        Args:
            db_path: Path to SQLite database file
            snapshots_dir: Directory containing daily snapshot JSON files
            sui_config: Configuration for Sui DEX monitor (optional)
        """
        self.db_path = Path(db_path)
        self.snapshots_dir = Path(snapshots_dir)

        # Initialize components
        self.trade_cache = TradeCache(str(self.db_path))
        self.snapshot_manager = DailySnapshot(str(self.snapshots_dir))
        self.coingecko = CoinGeckoClient()

        # Initialize Sui monitor if config provided
        self.sui_monitor: Optional[SuiTokenMonitor] = None
        if sui_config:
            self.sui_monitor = SuiTokenMonitor(config=sui_config)

        # Ensure database migrations are applied
        self._apply_migrations()

        logger.info(
            f"DataProvider initialized: db={self.db_path}, "
            f"snapshots={self.snapshots_dir}, sui_enabled={self.sui_monitor is not None}"
        )

    def _apply_migrations(self) -> None:
        """Apply database migrations for new tables."""
        with sqlite3.connect(self.db_path) as conn:
            # Query history table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS query_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    user_name TEXT,
                    channel_id TEXT,
                    query_text TEXT NOT NULL,
                    query_type TEXT NOT NULL,
                    generated_code TEXT,
                    result_summary TEXT,
                    execution_time_ms INTEGER,
                    success BOOLEAN DEFAULT TRUE,
                    error_message TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Saved functions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS saved_functions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT,
                    code TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_used TIMESTAMP,
                    use_count INTEGER DEFAULT 0
                )
            """)

            # PnL configuration table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS pnl_config (
                    id INTEGER PRIMARY KEY,
                    key TEXT UNIQUE NOT NULL,
                    value TEXT NOT NULL,
                    updated_by TEXT,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # OTC transactions table
            conn.execute("""
                CREATE TABLE IF NOT EXISTS otc_transactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date TEXT NOT NULL,
                    counterparty TEXT,
                    alkimi_amount REAL NOT NULL,
                    usd_amount REAL NOT NULL,
                    price REAL NOT NULL,
                    side TEXT NOT NULL,
                    notes TEXT,
                    created_by TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Create indexes for performance
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_history_user
                ON query_history(user_id, created_at DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_query_history_type
                ON query_history(query_type, created_at DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_otc_date
                ON otc_transactions(date DESC)
            """)

            conn.commit()
            logger.info("Database migrations applied successfully")

    async def initialize(self) -> None:
        """
        Initialize async components (Sui monitor).
        Should be called before using DEX-related methods.
        """
        if self.sui_monitor:
            await self.sui_monitor.initialize()
            logger.info("Sui monitor initialized")

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
        trades = self.trade_cache.get_trades(
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

    async def get_balances(self) -> Dict[str, Dict[str, float]]:
        """
        Get current balances by exchange/account from latest snapshot.

        Returns:
            Nested dict: {exchange_account: {asset: balance}}
            Example: {'mexc_mm1': {'USDT': 1000.0, 'ALKIMI': 50000.0}}
        """
        latest_snapshot = self.snapshot_manager.load_snapshot(date.today())

        if not latest_snapshot:
            # Try yesterday's snapshot
            logger.warning("No snapshot for today, trying yesterday")
            latest_snapshot = self.snapshot_manager.get_yesterday_snapshot()

        if not latest_snapshot:
            logger.warning("No recent snapshots found")
            return {}

        # Parse snapshot structure
        # Assuming snapshot format: {asset: balance} or {exchange_asset: balance}
        balances = {}

        for key, value in latest_snapshot.items():
            if '_' in key:
                # Format: exchange_account_asset or exchange_asset
                parts = key.split('_')
                if len(parts) >= 2:
                    account_key = '_'.join(parts[:-1])  # Everything except last part
                    asset = parts[-1]  # Last part is asset

                    if account_key not in balances:
                        balances[account_key] = {}
                    balances[account_key][asset] = float(value)
            else:
                # Simple asset: balance format
                if 'total' not in balances:
                    balances['total'] = {}
                balances['total'][key] = float(value)

        logger.debug(f"Retrieved balances for {len(balances)} accounts")
        return balances

    async def get_snapshots(self, days: int = 30) -> List[Dict]:
        """
        Get daily balance snapshots for the last N days.

        Args:
            days: Number of days to look back

        Returns:
            List of snapshot dicts with 'date', 'timestamp', and 'balances'
        """
        snapshots = []
        current_date = date.today()

        for i in range(days):
            snapshot_date = current_date - timedelta(days=i)
            snapshot_data = self.snapshot_manager.load_snapshot(snapshot_date)

            if snapshot_data:
                snapshots.append({
                    'date': snapshot_date.isoformat(),
                    'timestamp': datetime.combine(snapshot_date, datetime.min.time()).isoformat(),
                    'balances': snapshot_data
                })

        # Reverse to get chronological order (oldest first)
        snapshots.reverse()
        logger.debug(f"Retrieved {len(snapshots)} snapshots from last {days} days")
        return snapshots

    async def get_dex_trades(
        self,
        since: Optional[datetime] = None
    ) -> pd.DataFrame:
        """
        Get DEX trades from Sui monitor.

        Args:
            since: Fetch trades from this datetime onwards (default: 7 days ago)

        Returns:
            DataFrame with DEX trade data
        """
        if not self.sui_monitor:
            logger.warning("Sui monitor not configured, returning empty DataFrame")
            return pd.DataFrame(columns=[
                'timestamp', 'exchange', 'symbol', 'side',
                'amount', 'price', 'fee', 'fee_currency', 'trade_id'
            ])

        if since is None:
            since = datetime.now() - timedelta(days=7)

        try:
            trades = await self.sui_monitor.get_trades(since)

            if not trades:
                return pd.DataFrame(columns=[
                    'timestamp', 'exchange', 'symbol', 'side',
                    'amount', 'price', 'fee', 'fee_currency', 'trade_id'
                ])

            # Convert to DataFrame
            data = []
            for trade in trades:
                data.append({
                    'timestamp': trade.timestamp,
                    'exchange': trade.exchange,
                    'symbol': trade.symbol,
                    'side': trade.side.value,
                    'amount': trade.amount,
                    'price': trade.price,
                    'fee': trade.fee,
                    'fee_currency': trade.fee_currency,
                    'trade_id': trade.trade_id
                })

            df = pd.DataFrame(data)
            logger.info(f"Retrieved {len(df)} DEX trades since {since}")
            return df

        except Exception as e:
            logger.error(f"Error fetching DEX trades: {e}")
            return pd.DataFrame(columns=[
                'timestamp', 'exchange', 'symbol', 'side',
                'amount', 'price', 'fee', 'fee_currency', 'trade_id'
            ])

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

    # =========================================================================
    # Additional utility methods
    # =========================================================================

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

    async def save_query_history(
        self,
        user_id: str,
        query_text: str,
        query_type: str,
        user_name: Optional[str] = None,
        channel_id: Optional[str] = None,
        generated_code: Optional[str] = None,
        result_summary: Optional[str] = None,
        execution_time_ms: Optional[int] = None,
        success: bool = True,
        error_message: Optional[str] = None
    ) -> int:
        """
        Save a query to history.

        Returns:
            ID of the saved query record
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO query_history (
                    user_id, user_name, channel_id, query_text, query_type,
                    generated_code, result_summary, execution_time_ms,
                    success, error_message
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                user_id, user_name, channel_id, query_text, query_type,
                generated_code, result_summary, execution_time_ms,
                success, error_message
            ))
            conn.commit()
            return cursor.lastrowid

    async def get_query_history(
        self,
        user_id: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get query history, optionally filtered by user.

        Args:
            user_id: Filter by user ID (optional)
            limit: Maximum number of records to return

        Returns:
            List of query history records
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if user_id:
                query = """
                    SELECT * FROM query_history
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                cursor = conn.execute(query, (user_id, limit))
            else:
                query = """
                    SELECT * FROM query_history
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                cursor = conn.execute(query, (limit,))

            return [dict(row) for row in cursor.fetchall()]

    async def save_function(
        self,
        name: str,
        code: str,
        created_by: str,
        description: Optional[str] = None
    ) -> bool:
        """
        Save a reusable function.

        Args:
            name: Function name (must be unique)
            code: Function code
            created_by: User ID who created it
            description: Optional description

        Returns:
            True if saved successfully, False if name already exists
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO saved_functions (name, description, code, created_by)
                    VALUES (?, ?, ?, ?)
                """, (name, description, code, created_by))
                conn.commit()
                logger.info(f"Saved function '{name}' by {created_by}")
                return True
        except sqlite3.IntegrityError:
            logger.warning(f"Function '{name}' already exists")
            return False

    async def get_function(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a saved function by name.

        Returns:
            Function dict or None if not found
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM saved_functions WHERE name = ?",
                (name,)
            )
            row = cursor.fetchone()

            if row:
                # Update usage stats
                conn.execute("""
                    UPDATE saved_functions
                    SET last_used = CURRENT_TIMESTAMP,
                        use_count = use_count + 1
                    WHERE name = ?
                """, (name,))
                conn.commit()

                return dict(row)
            return None

    async def list_functions(self) -> List[Dict[str, Any]]:
        """
        List all saved functions.

        Returns:
            List of function metadata (without code)
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute("""
                SELECT name, description, created_by, created_at, last_used, use_count
                FROM saved_functions
                ORDER BY use_count DESC, name ASC
            """)
            return [dict(row) for row in cursor.fetchall()]

    async def save_otc_transaction(
        self,
        date_str: str,
        alkimi_amount: float,
        usd_amount: float,
        price: float,
        side: str,
        counterparty: Optional[str] = None,
        notes: Optional[str] = None,
        created_by: Optional[str] = None
    ) -> int:
        """
        Save an OTC transaction.

        Args:
            date_str: Transaction date (ISO format)
            alkimi_amount: Amount of ALKIMI traded
            usd_amount: USD value
            price: Price per ALKIMI
            side: 'buy' or 'sell'
            counterparty: Counterparty name (optional)
            notes: Additional notes (optional)
            created_by: User who recorded it (optional)

        Returns:
            ID of the saved transaction
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                INSERT INTO otc_transactions (
                    date, counterparty, alkimi_amount, usd_amount,
                    price, side, notes, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date_str, counterparty, alkimi_amount, usd_amount,
                price, side, notes, created_by
            ))
            conn.commit()
            logger.info(f"Saved OTC transaction: {side} {alkimi_amount} ALKIMI @ ${price}")
            return cursor.lastrowid

    async def get_otc_transactions(
        self,
        since: Optional[str] = None,
        until: Optional[str] = None
    ) -> pd.DataFrame:
        """
        Get OTC transactions as DataFrame.

        Args:
            since: Start date (ISO format)
            until: End date (ISO format)

        Returns:
            DataFrame with OTC transaction data
        """
        query = "SELECT * FROM otc_transactions WHERE 1=1"
        params = []

        if since:
            query += " AND date >= ?"
            params.append(since)

        if until:
            query += " AND date <= ?"
            params.append(until)

        query += " ORDER BY date DESC"

        with sqlite3.connect(self.db_path) as conn:
            df = pd.read_sql_query(query, conn, params=params)

        logger.debug(f"Retrieved {len(df)} OTC transactions")
        return df

    async def close(self) -> None:
        """Close all connections and cleanup resources."""
        await self.coingecko.close()

        if self.sui_monitor:
            await self.sui_monitor.close()

        logger.info("DataProvider closed")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()
