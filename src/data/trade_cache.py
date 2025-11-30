"""
Trade Cache Module

Persists trades locally to build historical data beyond API retention limits.
Uses SQLite for reliable, queryable storage.
"""

import os
import sqlite3
import json
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from src.exchanges.base import Trade, TradeSide
from src.utils import get_logger

logger = get_logger(__name__)


class TradeCache:
    """Local SQLite cache for trade data."""

    def __init__(self, db_path: str = None):
        """
        Initialize trade cache.

        Args:
            db_path: Path to SQLite database file.
                    Defaults to TRADE_CACHE_DB env var or 'data/trade_cache.db'
        """
        if db_path is None:
            db_path = os.getenv('TRADE_CACHE_DB', 'data/trade_cache.db')
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Create database schema if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT,
                    exchange TEXT NOT NULL,
                    account_name TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    side TEXT NOT NULL,
                    amount REAL NOT NULL,
                    price REAL NOT NULL,
                    fee REAL NOT NULL,
                    fee_currency TEXT,
                    cached_at TEXT NOT NULL,
                    UNIQUE(exchange, account_name, trade_id, timestamp, symbol, side, amount, price)
                )
            """)

            # Create index for faster queries
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON trades(timestamp DESC)
            """)

            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_exchange_account
                ON trades(exchange, account_name)
            """)

            conn.commit()
            logger.debug(f"Trade cache database initialized at {self.db_path}")

    def save_trades(self, trades: List[Trade], exchange: str, account_name: str) -> int:
        """
        Save trades to cache. Ignores duplicates.

        Args:
            trades: List of Trade objects
            exchange: Exchange name (e.g., 'mexc', 'kucoin')
            account_name: Account identifier (e.g., 'MM1', 'TM1')

        Returns:
            Number of new trades saved
        """
        if not trades:
            return 0

        cached_at = datetime.now().isoformat()
        new_count = 0

        with sqlite3.connect(self.db_path) as conn:
            for trade in trades:
                try:
                    conn.execute("""
                        INSERT INTO trades (
                            trade_id, exchange, account_name, timestamp,
                            symbol, side, amount, price, fee, fee_currency, cached_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        trade.trade_id,
                        exchange,
                        account_name,
                        trade.timestamp.isoformat(),
                        trade.symbol,
                        trade.side.value,
                        trade.amount,
                        trade.price,
                        trade.fee,
                        trade.fee_currency,
                        cached_at
                    ))
                    new_count += 1
                except sqlite3.IntegrityError:
                    # Duplicate trade, skip
                    continue

            conn.commit()

        if new_count > 0:
            logger.info(
                f"Cached {new_count} new trades for {exchange}/{account_name} "
                f"(attempted {len(trades)}, {len(trades) - new_count} duplicates skipped)"
            )

        return new_count

    def get_trades(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        exchange: Optional[str] = None,
        account_name: Optional[str] = None
    ) -> List[Trade]:
        """
        Retrieve trades from cache.

        Args:
            since: Fetch trades from this datetime onwards
            until: Fetch trades up to this datetime
            exchange: Filter by exchange name
            account_name: Filter by account name

        Returns:
            List of Trade objects
        """
        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())

        if exchange:
            query += " AND exchange = ?"
            params.append(exchange)

        if account_name:
            query += " AND account_name = ?"
            params.append(account_name)

        query += " ORDER BY timestamp ASC"

        trades = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)

            for row in cursor:
                trade = Trade(
                    timestamp=datetime.fromisoformat(row['timestamp']),
                    symbol=row['symbol'],
                    side=TradeSide(row['side']),
                    amount=row['amount'],
                    price=row['price'],
                    fee=row['fee'],
                    fee_currency=row['fee_currency'],
                    trade_id=row['trade_id'],
                    exchange=row['exchange']
                )
                trades.append(trade)

        logger.debug(f"Retrieved {len(trades)} trades from cache")
        return trades

    def get_stats(self) -> dict:
        """Get cache statistics."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    MIN(timestamp) as oldest_trade,
                    MAX(timestamp) as newest_trade,
                    COUNT(DISTINCT exchange || '/' || account_name) as account_count
                FROM trades
            """)
            row = cursor.fetchone()

            return {
                'total_trades': row[0],
                'oldest_trade': row[1],
                'newest_trade': row[2],
                'account_count': row[3]
            }
