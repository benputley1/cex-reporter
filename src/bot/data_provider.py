"""
Data Provider Module

Unified data access layer for the ALKIMI Slack bot.
Consolidates access to trade cache, snapshots, DEX data, and market prices.

This class now acts as a facade for various repository classes,
providing backward compatibility while delegating to focused repositories.
"""

import os
import json
import sqlite3
import aiosqlite
import pandas as pd
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Set

from src.data.trade_cache import TradeCache
from src.data.daily_snapshot import DailySnapshot
from src.data.coingecko_client import CoinGeckoClient
from src.exchanges.sui_monitor import SuiTokenMonitor
from src.exchanges.base import Trade, TradeSide
from src.monitoring.health import HealthChecker, SystemHealth
from src.repositories import (
    TradeRepository,
    BalanceRepository,
    SnapshotRepository,
    QueryRepository,
    ThreadRepository,
    PriceRepository,
    OTCRepository
)
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

        # Initialize core components (kept for backward compatibility)
        self.trade_cache = TradeCache(str(self.db_path))
        self.snapshot_manager = DailySnapshot(str(self.snapshots_dir))
        self.coingecko = CoinGeckoClient()

        # Initialize Sui monitor if config provided
        self.sui_monitor: Optional[SuiTokenMonitor] = None
        if sui_config:
            self.sui_monitor = SuiTokenMonitor(config=sui_config)

        # Initialize health checker
        self.health_checker: Optional[HealthChecker] = None

        # Initialize repositories
        self.trades = TradeRepository(self.trade_cache)
        self.balances = BalanceRepository(self.snapshot_manager)
        self.snapshots = SnapshotRepository(self.snapshot_manager)
        self.queries = QueryRepository(self.db_path)
        self.threads = ThreadRepository(self.db_path)
        self.prices = PriceRepository(self.coingecko)
        self.otc = OTCRepository(self.db_path)

        # Keep price_history for backward compatibility (delegated to PriceRepository)
        self.price_history = self.prices.price_history
        self.max_price_history = self.prices.max_price_history

        # Ensure database migrations are applied
        self._apply_migrations()

        logger.info(
            f"DataProvider initialized: db={self.db_path}, "
            f"snapshots={self.snapshots_dir}, sui_enabled={self.sui_monitor is not None}"
        )

    def _apply_migrations(self) -> None:
        """Apply database migrations for new tables (synchronous for __init__)."""
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

            # Conversation logs table for fine-tuning data
            conn.execute("""
                CREATE TABLE IF NOT EXISTS conversation_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_ts TEXT,
                    user_id TEXT NOT NULL,
                    user_message TEXT NOT NULL,
                    assistant_response TEXT NOT NULL,
                    tools_used TEXT,
                    model TEXT,
                    processing_time_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_logs_thread
                ON conversation_logs(thread_ts, created_at)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_conversation_logs_user
                ON conversation_logs(user_id, created_at DESC)
            """)

            # Active threads table for thread reply tracking (survives restarts)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS active_threads (
                    thread_ts TEXT PRIMARY KEY,
                    channel_id TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
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
        return await self.trades.get_trades_df(
            since=since,
            until=until,
            exchange=exchange,
            account=account
        )

    async def get_balances(self) -> Dict[str, Dict[str, float]]:
        """
        Get current balances by exchange/account from latest snapshot.

        Returns:
            Nested dict: {exchange_account: {asset: balance}}
            Example: {'mexc_mm1': {'USDT': 1000.0, 'ALKIMI': 50000.0}}
        """
        return await self.balances.get_balances()

    async def get_snapshots(self, days: int = 30) -> List[Dict]:
        """
        Get daily balance snapshots for the last N days.

        Args:
            days: Number of days to look back

        Returns:
            List of snapshot dicts with 'date', 'timestamp', and 'balances'
        """
        return await self.snapshots.get_snapshots(days=days)

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
        return await self.prices.get_current_price()

    def record_price(self, price: float) -> None:
        """
        Record price for change detection.

        Args:
            price: Current price to record
        """
        self.prices.record_price(price)

    def get_price_change(self, minutes: int = 60) -> Optional[float]:
        """
        Get price change percentage over last N minutes.

        Args:
            minutes: Time window in minutes (default: 60)

        Returns:
            Price change percentage, or None if insufficient data
        """
        return self.prices.get_price_change(minutes=minutes)

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
        return await self.trades.get_trade_summary(since=since, until=until)

    # =========================================================================
    # Additional utility methods
    # =========================================================================

    async def get_market_data(self) -> Optional[Dict[str, Any]]:
        """
        Get comprehensive market data for ALKIMI.

        Returns:
            Dict with price, volume, market cap, and 24h change
        """
        return await self.prices.get_market_data()

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
        return await self.queries.save_query_history(
            user_id=user_id,
            query_text=query_text,
            query_type=query_type,
            user_name=user_name,
            channel_id=channel_id,
            generated_code=generated_code,
            result_summary=result_summary,
            execution_time_ms=execution_time_ms,
            success=success,
            error_message=error_message
        )

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
        return await self.queries.get_query_history(user_id=user_id, limit=limit)

    async def save_conversation_log(
        self,
        thread_ts: str,
        user_id: str,
        user_message: str,
        assistant_response: str,
        tools_used: Optional[List[str]] = None,
        model: Optional[str] = None,
        processing_time_ms: Optional[int] = None
    ) -> int:
        """
        Save a conversation exchange for fine-tuning data.

        Args:
            thread_ts: Slack thread timestamp
            user_id: User ID who sent the message
            user_message: The user's message text
            assistant_response: The bot's response text
            tools_used: List of tool names used (will be JSON serialized)
            model: Model name used for the response
            processing_time_ms: Time taken to process the request

        Returns:
            ID of the saved conversation record
        """
        return await self.queries.save_conversation_log(
            thread_ts=thread_ts,
            user_id=user_id,
            user_message=user_message,
            assistant_response=assistant_response,
            tools_used=tools_used,
            model=model,
            processing_time_ms=processing_time_ms
        )

    async def add_active_thread(self, thread_ts: str, channel_id: str) -> None:
        """
        Track a thread the bot is participating in.

        Args:
            thread_ts: Slack thread timestamp (primary identifier)
            channel_id: Channel ID where the thread is located
        """
        await self.threads.add_active_thread(thread_ts, channel_id)

    async def is_active_thread(self, thread_ts: str) -> bool:
        """
        Check if bot is participating in this thread.

        Args:
            thread_ts: Slack thread timestamp

        Returns:
            True if the bot is tracking this thread
        """
        return await self.threads.is_active_thread(thread_ts)

    def load_active_threads(self) -> Set[str]:
        """
        Load all active thread IDs (for startup) - synchronous version.

        Returns:
            Set of thread_ts values the bot is participating in
        """
        return self.threads.load_active_threads_sync()

    def cleanup_old_threads(self, days: int = 30) -> int:
        """
        Remove threads older than specified days - synchronous version.

        Args:
            days: Remove threads older than this many days

        Returns:
            Number of threads removed
        """
        return self.threads.cleanup_old_threads_sync(days=days)

    async def get_stale_threads(self, days: int = 7) -> List[str]:
        """
        Get list of thread IDs that are older than specified days.
        Used for periodic cleanup without deleting from database.

        Args:
            days: Get threads older than this many days

        Returns:
            List of thread_ts values that are stale
        """
        return await self.threads.get_stale_threads(days=days)

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
        return await self.queries.save_function(
            name=name,
            code=code,
            created_by=created_by,
            description=description
        )

    async def get_function(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a saved function by name.

        Returns:
            Function dict or None if not found
        """
        return await self.queries.get_function(name)

    async def list_functions(self) -> List[Dict[str, Any]]:
        """
        List all saved functions.

        Returns:
            List of function metadata (without code)
        """
        return await self.queries.list_functions()

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
        return await self.otc.save_otc_transaction(
            date_str=date_str,
            alkimi_amount=alkimi_amount,
            usd_amount=usd_amount,
            price=price,
            side=side,
            counterparty=counterparty,
            notes=notes,
            created_by=created_by
        )

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
        return await self.otc.get_otc_transactions(since=since, until=until)

    async def health_check(
        self,
        exchange_clients: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> SystemHealth:
        """
        Perform comprehensive health check on all system components.

        This method checks:
        - Database connectivity and performance
        - Exchange API connectivity (if exchange_clients provided)
        - CoinGecko API connectivity
        - Sui blockchain monitor (if configured)

        Args:
            exchange_clients: Optional dictionary mapping exchange names to client instances
            use_cache: Whether to use cached health check results (default: True)

        Returns:
            SystemHealth object with overall status and component details

        Example:
            ```python
            # Basic health check (database + APIs only)
            health = await data_provider.health_check()
            print(f"System status: {health.overall_status.value}")

            # Full health check including exchanges
            exchange_clients = {
                'mexc_mm1': mexc_client1,
                'mexc_mm2': mexc_client2,
                'kucoin_mm1': kucoin_client
            }
            health = await data_provider.health_check(exchange_clients)
            for component in health.components:
                print(f"{component.name}: {component.status.value} ({component.latency_ms}ms)")
            ```
        """
        # Lazy initialize health checker
        if not self.health_checker:
            self.health_checker = HealthChecker(self)
            logger.debug("Health checker initialized")

        # Perform system health check
        system_health = await self.health_checker.get_system_health(
            exchange_clients=exchange_clients,
            use_cache=use_cache
        )

        return system_health

    def format_health_for_slack(self, system_health: SystemHealth) -> str:
        """
        Format system health status for Slack message.

        Args:
            system_health: SystemHealth object from health_check()

        Returns:
            Formatted string suitable for Slack messages

        Example:
            ```python
            health = await data_provider.health_check()
            slack_message = data_provider.format_health_for_slack(health)
            # Post slack_message to Slack channel
            ```
        """
        if not self.health_checker:
            self.health_checker = HealthChecker(self)

        return self.health_checker.format_health_for_slack(system_health)

    async def close(self) -> None:
        """Close all connections and cleanup resources."""
        await self.prices.close()

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
