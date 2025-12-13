"""
Trade Cache Module

Persists trades locally to build historical data beyond API retention limits.
Uses SQLite for reliable, queryable storage with async/await support.
"""

import os
import sqlite3
import aiosqlite
import asyncio
import json
import hashlib
from datetime import datetime
from typing import List, Optional
from pathlib import Path

from src.exchanges.base import Trade, TradeSide
from src.utils import get_logger

logger = get_logger(__name__)


class TradeCache:
    """Local SQLite cache for trade data with async support and connection pooling."""

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

        # Connection pooling: reuse connection for batch operations
        self._connection = None
        self._connection_lock = None

        # Initialize schema synchronously (required for __init__)
        self._init_database_sync()

    @staticmethod
    def _generate_synthetic_trade_id(
        exchange: str,
        account: str,
        timestamp: datetime,
        symbol: str,
        side: str,
        amount: float,
        price: float
    ) -> str:
        """
        Generate a synthetic trade_id using SHA256 hash of trade components.

        This ensures unique identification of trades even when the exchange API
        doesn't provide a trade_id. Uses deterministic hashing for idempotency.

        Args:
            exchange: Exchange name
            account: Account name
            timestamp: Trade timestamp
            symbol: Asset symbol
            side: Trade side (buy/sell)
            amount: Trade amount
            price: Trade price

        Returns:
            Synthetic trade_id as hex string (16 characters)
        """
        # Create deterministic string from trade components
        components = f"{exchange}|{account}|{timestamp.isoformat()}|{symbol}|{side}|{amount}|{price}"

        # Generate SHA256 hash and take first 16 characters for readability
        hash_obj = hashlib.sha256(components.encode('utf-8'))
        synthetic_id = hash_obj.hexdigest()[:16]

        return f"synthetic_{synthetic_id}"

    def _init_database_sync(self):
        """Create database schema if it doesn't exist (synchronous for __init__)."""
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
                    transaction_type TEXT DEFAULT 'trade'
                )
            """)

            # Create unique composite index on (exchange, trade_id, timestamp)
            # This is the primary deduplication key
            conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_trade
                ON trades(exchange, trade_id, timestamp)
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

            # Create index for transaction_type filtering
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_transaction_type
                ON trades(transaction_type)
            """)

            # Migrate existing data: add transaction_type column if it doesn't exist
            cursor = conn.execute("PRAGMA table_info(trades)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'transaction_type' not in columns:
                logger.info("Migrating database: adding transaction_type column")
                conn.execute("ALTER TABLE trades ADD COLUMN transaction_type TEXT DEFAULT 'trade'")
                conn.execute("UPDATE trades SET transaction_type = 'trade' WHERE transaction_type IS NULL")
                conn.commit()
                logger.info("Database migration completed: all existing records set to 'trade'")

            conn.commit()
            logger.debug(f"Trade cache database initialized at {self.db_path}")

    async def _init_database(self):
        """Create database schema if it doesn't exist (async version)."""
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute("""
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
                    transaction_type TEXT DEFAULT 'trade'
                )
            """)

            # Create unique composite index on (exchange, trade_id, timestamp)
            # This is the primary deduplication key
            await conn.execute("""
                CREATE UNIQUE INDEX IF NOT EXISTS idx_unique_trade
                ON trades(exchange, trade_id, timestamp)
            """)

            # Create index for faster queries
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_timestamp
                ON trades(timestamp DESC)
            """)

            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_exchange_account
                ON trades(exchange, account_name)
            """)

            # Create index for transaction_type filtering
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_transaction_type
                ON trades(transaction_type)
            """)

            # Migrate existing data: add transaction_type column if it doesn't exist
            cursor = await conn.execute("PRAGMA table_info(trades)")
            rows = await cursor.fetchall()
            columns = [row[1] for row in rows]

            if 'transaction_type' not in columns:
                logger.info("Migrating database: adding transaction_type column")
                await conn.execute("ALTER TABLE trades ADD COLUMN transaction_type TEXT DEFAULT 'trade'")
                await conn.execute("UPDATE trades SET transaction_type = 'trade' WHERE transaction_type IS NULL")
                await conn.commit()
                logger.info("Database migration completed: all existing records set to 'trade'")

            await conn.commit()
            logger.debug(f"Trade cache database initialized at {self.db_path}")

    async def save_trades(self, trades: List[Trade], exchange: str, account_name: str, transaction_type: str = 'trade') -> int:
        """
        Save trades to cache. Ignores duplicates (async version).

        Generates synthetic trade_id for trades without one to ensure uniqueness.

        Args:
            trades: List of Trade objects
            exchange: Exchange name (e.g., 'mexc', 'kucoin')
            account_name: Account identifier (e.g., 'MM1', 'TM1')
            transaction_type: Type of transaction ('trade', 'deposit', 'withdrawal', 'transfer')

        Returns:
            Number of new trades saved
        """
        if not trades:
            return 0

        cached_at = datetime.now().isoformat()
        synthetic_count = 0

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            new_count = 0

            for trade in trades:
                # Generate synthetic trade_id if missing
                trade_id = trade.trade_id
                if not trade_id or trade_id == '':
                    trade_id = self._generate_synthetic_trade_id(
                        exchange=exchange,
                        account=account_name,
                        timestamp=trade.timestamp,
                        symbol=trade.symbol,
                        side=trade.side.value,
                        amount=trade.amount,
                        price=trade.price
                    )
                    synthetic_count += 1

                # Use INSERT OR IGNORE to skip duplicates efficiently
                await cursor.execute("""
                    INSERT OR IGNORE INTO trades (
                        trade_id, exchange, account_name, timestamp,
                        symbol, side, amount, price, fee, fee_currency, cached_at, transaction_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_id,
                    exchange,
                    account_name,
                    trade.timestamp.isoformat(),
                    trade.symbol,
                    trade.side.value,
                    trade.amount,
                    trade.price,
                    trade.fee,
                    trade.fee_currency,
                    cached_at,
                    transaction_type
                ))

                # Track how many rows were actually inserted (not ignored)
                if cursor.rowcount > 0:
                    new_count += 1

            await conn.commit()

        duplicates_skipped = len(trades) - new_count

        if new_count > 0:
            log_msg = f"Cached {new_count} new {transaction_type}s for {exchange}/{account_name}"
            if duplicates_skipped > 0:
                log_msg += f" ({duplicates_skipped} duplicates skipped)"
            if synthetic_count > 0:
                log_msg += f", {synthetic_count} synthetic IDs generated"
            logger.info(log_msg)
        elif duplicates_skipped > 0:
            logger.debug(f"All {duplicates_skipped} {transaction_type}s for {exchange}/{account_name} were duplicates, skipped")

        return new_count

    def save_trades_sync(self, trades: List[Trade], exchange: str, account_name: str, transaction_type: str = 'trade') -> int:
        """
        Save trades to cache. Ignores duplicates (synchronous fallback).

        Generates synthetic trade_id for trades without one to ensure uniqueness.

        Args:
            trades: List of Trade objects
            exchange: Exchange name (e.g., 'mexc', 'kucoin')
            account_name: Account identifier (e.g., 'MM1', 'TM1')
            transaction_type: Type of transaction ('trade', 'deposit', 'withdrawal', 'transfer')

        Returns:
            Number of new trades saved
        """
        if not trades:
            return 0

        cached_at = datetime.now().isoformat()
        synthetic_count = 0

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            new_count = 0

            for trade in trades:
                # Generate synthetic trade_id if missing
                trade_id = trade.trade_id
                if not trade_id or trade_id == '':
                    trade_id = self._generate_synthetic_trade_id(
                        exchange=exchange,
                        account=account_name,
                        timestamp=trade.timestamp,
                        symbol=trade.symbol,
                        side=trade.side.value,
                        amount=trade.amount,
                        price=trade.price
                    )
                    synthetic_count += 1

                # Use INSERT OR IGNORE to skip duplicates efficiently
                cursor.execute("""
                    INSERT OR IGNORE INTO trades (
                        trade_id, exchange, account_name, timestamp,
                        symbol, side, amount, price, fee, fee_currency, cached_at, transaction_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    trade_id,
                    exchange,
                    account_name,
                    trade.timestamp.isoformat(),
                    trade.symbol,
                    trade.side.value,
                    trade.amount,
                    trade.price,
                    trade.fee,
                    trade.fee_currency,
                    cached_at,
                    transaction_type
                ))

                # Track how many rows were actually inserted (not ignored)
                if cursor.rowcount > 0:
                    new_count += 1

            conn.commit()

        duplicates_skipped = len(trades) - new_count

        if new_count > 0:
            log_msg = f"Cached {new_count} new {transaction_type}s for {exchange}/{account_name}"
            if duplicates_skipped > 0:
                log_msg += f" ({duplicates_skipped} duplicates skipped)"
            if synthetic_count > 0:
                log_msg += f", {synthetic_count} synthetic IDs generated"
            logger.info(log_msg)
        elif duplicates_skipped > 0:
            logger.debug(f"All {duplicates_skipped} {transaction_type}s for {exchange}/{account_name} were duplicates, skipped")

        return new_count

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
        Retrieve trades from cache (async version).

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
        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        # Filter by transaction type
        if transaction_type:
            query += " AND transaction_type = ?"
            params.append(transaction_type)
        elif not include_transfers:
            # Default behavior: exclude transfers for P&L calculations
            query += " AND transaction_type = ?"
            params.append('trade')

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
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query, params)

            async for row in cursor:
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

    def get_trades_sync(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        exchange: Optional[str] = None,
        account_name: Optional[str] = None,
        include_transfers: bool = False,
        transaction_type: Optional[str] = None
    ) -> List[Trade]:
        """
        Retrieve trades from cache (synchronous fallback).

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
        query = "SELECT * FROM trades WHERE 1=1"
        params = []

        # Filter by transaction type
        if transaction_type:
            query += " AND transaction_type = ?"
            params.append(transaction_type)
        elif not include_transfers:
            # Default behavior: exclude transfers for P&L calculations
            query += " AND transaction_type = ?"
            params.append('trade')

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

    async def save_transfers(self, transfers: List[dict], exchange: str, account_name: str) -> int:
        """
        Save deposits/withdrawals to cache (async version).

        Args:
            transfers: List of transfer dictionaries with keys:
                      - transfer_id: Unique transfer identifier
                      - timestamp: Transfer datetime
                      - symbol: Asset symbol
                      - amount: Transfer amount (positive for deposits, negative for withdrawals)
                      - fee: Transfer fee
                      - fee_currency: Fee currency
                      - transfer_type: 'deposit', 'withdrawal', or 'transfer'
            exchange: Exchange name (e.g., 'mexc', 'kucoin')
            account_name: Account identifier (e.g., 'MM1', 'TM1')

        Returns:
            Number of new transfers saved
        """
        if not transfers:
            return 0

        cached_at = datetime.now().isoformat()

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.cursor()
            new_count = 0

            for transfer in transfers:
                # Determine side based on amount sign
                amount = abs(transfer['amount'])
                side = 'buy' if transfer['amount'] > 0 else 'sell'  # buy=deposit, sell=withdrawal

                # Use INSERT OR IGNORE to skip duplicates efficiently
                await cursor.execute("""
                    INSERT OR IGNORE INTO trades (
                        trade_id, exchange, account_name, timestamp,
                        symbol, side, amount, price, fee, fee_currency, cached_at, transaction_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    transfer.get('transfer_id', transfer.get('trade_id')),
                    exchange,
                    account_name,
                    transfer['timestamp'].isoformat() if isinstance(transfer['timestamp'], datetime) else transfer['timestamp'],
                    transfer['symbol'],
                    side,
                    amount,
                    0.0,  # No price for transfers
                    transfer.get('fee', 0.0),
                    transfer.get('fee_currency'),
                    cached_at,
                    transfer.get('transfer_type', 'transfer')
                ))

                # Track how many rows were actually inserted (not ignored)
                if cursor.rowcount > 0:
                    new_count += 1

            await conn.commit()

        duplicates_skipped = len(transfers) - new_count
        transfer_type = transfers[0].get('transfer_type', 'transfer') if transfers else 'transfer'

        if new_count > 0:
            log_msg = f"Cached {new_count} new {transfer_type}s for {exchange}/{account_name}"
            if duplicates_skipped > 0:
                log_msg += f" ({duplicates_skipped} duplicates skipped)"
            logger.info(log_msg)
        elif duplicates_skipped > 0:
            logger.debug(f"All {duplicates_skipped} {transfer_type}s for {exchange}/{account_name} were duplicates, skipped")

        return new_count

    def save_transfers_sync(self, transfers: List[dict], exchange: str, account_name: str) -> int:
        """
        Save deposits/withdrawals to cache (synchronous version).

        Args:
            transfers: List of transfer dictionaries with keys:
                      - transfer_id: Unique transfer identifier
                      - timestamp: Transfer datetime
                      - symbol: Asset symbol
                      - amount: Transfer amount (positive for deposits, negative for withdrawals)
                      - fee: Transfer fee
                      - fee_currency: Fee currency
                      - transfer_type: 'deposit', 'withdrawal', or 'transfer'
            exchange: Exchange name (e.g., 'mexc', 'kucoin')
            account_name: Account identifier (e.g., 'MM1', 'TM1')

        Returns:
            Number of new transfers saved
        """
        if not transfers:
            return 0

        cached_at = datetime.now().isoformat()

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            new_count = 0

            for transfer in transfers:
                # Determine side based on amount sign
                amount = abs(transfer['amount'])
                side = 'buy' if transfer['amount'] > 0 else 'sell'  # buy=deposit, sell=withdrawal

                # Use INSERT OR IGNORE to skip duplicates efficiently
                cursor.execute("""
                    INSERT OR IGNORE INTO trades (
                        trade_id, exchange, account_name, timestamp,
                        symbol, side, amount, price, fee, fee_currency, cached_at, transaction_type
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    transfer.get('transfer_id', transfer.get('trade_id')),
                    exchange,
                    account_name,
                    transfer['timestamp'].isoformat() if isinstance(transfer['timestamp'], datetime) else transfer['timestamp'],
                    transfer['symbol'],
                    side,
                    amount,
                    0.0,  # No price for transfers
                    transfer.get('fee', 0.0),
                    transfer.get('fee_currency'),
                    cached_at,
                    transfer.get('transfer_type', 'transfer')
                ))

                # Track how many rows were actually inserted (not ignored)
                if cursor.rowcount > 0:
                    new_count += 1

            conn.commit()

        duplicates_skipped = len(transfers) - new_count
        transfer_type = transfers[0].get('transfer_type', 'transfer') if transfers else 'transfer'

        if new_count > 0:
            log_msg = f"Cached {new_count} new {transfer_type}s for {exchange}/{account_name}"
            if duplicates_skipped > 0:
                log_msg += f" ({duplicates_skipped} duplicates skipped)"
            logger.info(log_msg)
        elif duplicates_skipped > 0:
            logger.debug(f"All {duplicates_skipped} {transfer_type}s for {exchange}/{account_name} were duplicates, skipped")

        return new_count

    async def get_transfers(
        self,
        exchange: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        transfer_type: Optional[str] = None
    ) -> List[dict]:
        """
        Retrieve transfers (deposits/withdrawals) from cache (async version).

        Args:
            exchange: Filter by exchange name
            since: Fetch transfers from this datetime onwards
            until: Fetch transfers up to this datetime
            transfer_type: Filter by specific type ('deposit', 'withdrawal', 'transfer')

        Returns:
            List of transfer dictionaries
        """
        query = "SELECT * FROM trades WHERE transaction_type IN ('deposit', 'withdrawal', 'transfer')"
        params = []

        if transfer_type:
            query = "SELECT * FROM trades WHERE transaction_type = ?"
            params = [transfer_type]

        if exchange:
            query += " AND exchange = ?"
            params.append(exchange)

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())

        query += " ORDER BY timestamp ASC"

        transfers = []
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(query, params)

            async for row in cursor:
                # Convert back to signed amount (positive for deposits, negative for withdrawals)
                amount = row['amount'] if row['side'] == 'buy' else -row['amount']

                transfer = {
                    'transfer_id': row['trade_id'],
                    'timestamp': datetime.fromisoformat(row['timestamp']),
                    'symbol': row['symbol'],
                    'amount': amount,
                    'fee': row['fee'],
                    'fee_currency': row['fee_currency'],
                    'transfer_type': row['transaction_type'],
                    'exchange': row['exchange'],
                    'account_name': row['account_name']
                }
                transfers.append(transfer)

        logger.debug(f"Retrieved {len(transfers)} transfers from cache")
        return transfers

    def get_transfers_sync(
        self,
        exchange: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        transfer_type: Optional[str] = None
    ) -> List[dict]:
        """
        Retrieve transfers (deposits/withdrawals) from cache (synchronous version).

        Args:
            exchange: Filter by exchange name
            since: Fetch transfers from this datetime onwards
            until: Fetch transfers up to this datetime
            transfer_type: Filter by specific type ('deposit', 'withdrawal', 'transfer')

        Returns:
            List of transfer dictionaries
        """
        query = "SELECT * FROM trades WHERE transaction_type IN ('deposit', 'withdrawal', 'transfer')"
        params = []

        if transfer_type:
            query = "SELECT * FROM trades WHERE transaction_type = ?"
            params = [transfer_type]

        if exchange:
            query += " AND exchange = ?"
            params.append(exchange)

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())

        query += " ORDER BY timestamp ASC"

        transfers = []
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(query, params)

            for row in cursor:
                # Convert back to signed amount (positive for deposits, negative for withdrawals)
                amount = row['amount'] if row['side'] == 'buy' else -row['amount']

                transfer = {
                    'transfer_id': row['trade_id'],
                    'timestamp': datetime.fromisoformat(row['timestamp']),
                    'symbol': row['symbol'],
                    'amount': amount,
                    'fee': row['fee'],
                    'fee_currency': row['fee_currency'],
                    'transfer_type': row['transaction_type'],
                    'exchange': row['exchange'],
                    'account_name': row['account_name']
                }
                transfers.append(transfer)

        logger.debug(f"Retrieved {len(transfers)} transfers from cache")
        return transfers

    async def get_net_flow(
        self,
        exchange: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        symbol: Optional[str] = None
    ) -> dict:
        """
        Calculate net deposit/withdrawal flow (async version).

        Args:
            exchange: Exchange name
            since: Calculate flow from this datetime onwards
            until: Calculate flow up to this datetime
            symbol: Filter by specific symbol (optional)

        Returns:
            Dictionary with net flow statistics:
            {
                'total_deposits': float,
                'total_withdrawals': float,
                'net_flow': float,  # positive = net deposits, negative = net withdrawals
                'by_symbol': {symbol: net_amount, ...}
            }
        """
        query = """
            SELECT symbol, side, SUM(amount) as total_amount
            FROM trades
            WHERE exchange = ? AND transaction_type IN ('deposit', 'withdrawal')
        """
        params = [exchange]

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        query += " GROUP BY symbol, side"

        deposits_by_symbol = {}
        withdrawals_by_symbol = {}

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(query, params)
            async for row in cursor:
                sym = row[0]
                side = row[1]
                amount = row[2]

                if side == 'buy':  # deposit
                    deposits_by_symbol[sym] = deposits_by_symbol.get(sym, 0) + amount
                else:  # withdrawal
                    withdrawals_by_symbol[sym] = withdrawals_by_symbol.get(sym, 0) + amount

        # Calculate net flow by symbol
        all_symbols = set(deposits_by_symbol.keys()) | set(withdrawals_by_symbol.keys())
        by_symbol = {}
        for sym in all_symbols:
            deposits = deposits_by_symbol.get(sym, 0)
            withdrawals = withdrawals_by_symbol.get(sym, 0)
            by_symbol[sym] = deposits - withdrawals

        total_deposits = sum(deposits_by_symbol.values())
        total_withdrawals = sum(withdrawals_by_symbol.values())

        result = {
            'total_deposits': total_deposits,
            'total_withdrawals': total_withdrawals,
            'net_flow': total_deposits - total_withdrawals,
            'by_symbol': by_symbol
        }

        logger.debug(f"Net flow for {exchange}: {result['net_flow']} ({len(by_symbol)} symbols)")
        return result

    def get_net_flow_sync(
        self,
        exchange: str,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        symbol: Optional[str] = None
    ) -> dict:
        """
        Calculate net deposit/withdrawal flow (synchronous version).

        Args:
            exchange: Exchange name
            since: Calculate flow from this datetime onwards
            until: Calculate flow up to this datetime
            symbol: Filter by specific symbol (optional)

        Returns:
            Dictionary with net flow statistics:
            {
                'total_deposits': float,
                'total_withdrawals': float,
                'net_flow': float,  # positive = net deposits, negative = net withdrawals
                'by_symbol': {symbol: net_amount, ...}
            }
        """
        query = """
            SELECT symbol, side, SUM(amount) as total_amount
            FROM trades
            WHERE exchange = ? AND transaction_type IN ('deposit', 'withdrawal')
        """
        params = [exchange]

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())

        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())

        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        query += " GROUP BY symbol, side"

        deposits_by_symbol = {}
        withdrawals_by_symbol = {}

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(query, params)
            for row in cursor:
                sym = row[0]
                side = row[1]
                amount = row[2]

                if side == 'buy':  # deposit
                    deposits_by_symbol[sym] = deposits_by_symbol.get(sym, 0) + amount
                else:  # withdrawal
                    withdrawals_by_symbol[sym] = withdrawals_by_symbol.get(sym, 0) + amount

        # Calculate net flow by symbol
        all_symbols = set(deposits_by_symbol.keys()) | set(withdrawals_by_symbol.keys())
        by_symbol = {}
        for sym in all_symbols:
            deposits = deposits_by_symbol.get(sym, 0)
            withdrawals = withdrawals_by_symbol.get(sym, 0)
            by_symbol[sym] = deposits - withdrawals

        total_deposits = sum(deposits_by_symbol.values())
        total_withdrawals = sum(withdrawals_by_symbol.values())

        result = {
            'total_deposits': total_deposits,
            'total_withdrawals': total_withdrawals,
            'net_flow': total_deposits - total_withdrawals,
            'by_symbol': by_symbol
        }

        logger.debug(f"Net flow for {exchange}: {result['net_flow']} ({len(by_symbol)} symbols)")
        return result

    async def get_stats(self) -> dict:
        """Get cache statistics (async version)."""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute("""
                SELECT
                    COUNT(*) as total_trades,
                    MIN(timestamp) as oldest_trade,
                    MAX(timestamp) as newest_trade,
                    COUNT(DISTINCT exchange || '/' || account_name) as account_count
                FROM trades
            """)
            row = await cursor.fetchone()

            return {
                'total_trades': row[0],
                'oldest_trade': row[1],
                'newest_trade': row[2],
                'account_count': row[3]
            }

    def get_stats_sync(self) -> dict:
        """Get cache statistics (synchronous fallback)."""
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

    async def deduplicate_trades(self) -> int:
        """
        Remove duplicate trades from the database (async version).

        Identifies and removes duplicate trades based on the unique composite key
        (exchange, trade_id, timestamp), keeping the oldest cached entry.

        This method is useful for cleaning up databases that may have accumulated
        duplicates before the unique constraint was implemented.

        Returns:
            Number of duplicate trades removed

        Example:
            cache = TradeCache()
            removed = await cache.deduplicate_trades()
            print(f"Removed {removed} duplicate trades")
        """
        async with aiosqlite.connect(self.db_path) as conn:
            # Count duplicates before removal
            cursor = await conn.execute("""
                SELECT COUNT(*) FROM (
                    SELECT exchange, trade_id, timestamp, COUNT(*) as cnt
                    FROM trades
                    GROUP BY exchange, trade_id, timestamp
                    HAVING cnt > 1
                )
            """)
            row = await cursor.fetchone()
            duplicate_groups = row[0]

            if duplicate_groups == 0:
                logger.info("No duplicate trades found")
                return 0

            # Delete duplicates, keeping the oldest cached entry (lowest id)
            cursor = await conn.execute("""
                DELETE FROM trades
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM trades
                    GROUP BY exchange, trade_id, timestamp
                )
            """)

            removed_count = cursor.rowcount
            await conn.commit()

            logger.info(
                f"Deduplication complete: removed {removed_count} duplicate trades "
                f"from {duplicate_groups} duplicate groups"
            )

            return removed_count

    def deduplicate_trades_sync(self) -> int:
        """
        Remove duplicate trades from the database (synchronous fallback).

        Identifies and removes duplicate trades based on the unique composite key
        (exchange, trade_id, timestamp), keeping the oldest cached entry.

        This method is useful for cleaning up databases that may have accumulated
        duplicates before the unique constraint was implemented.

        Returns:
            Number of duplicate trades removed

        Example:
            cache = TradeCache()
            removed = cache.deduplicate_trades_sync()
            print(f"Removed {removed} duplicate trades")
        """
        with sqlite3.connect(self.db_path) as conn:
            # Count duplicates before removal
            cursor = conn.execute("""
                SELECT COUNT(*) FROM (
                    SELECT exchange, trade_id, timestamp, COUNT(*) as cnt
                    FROM trades
                    GROUP BY exchange, trade_id, timestamp
                    HAVING cnt > 1
                )
            """)
            duplicate_groups = cursor.fetchone()[0]

            if duplicate_groups == 0:
                logger.info("No duplicate trades found")
                return 0

            # Delete duplicates, keeping the oldest cached entry (lowest id)
            cursor = conn.execute("""
                DELETE FROM trades
                WHERE id NOT IN (
                    SELECT MIN(id)
                    FROM trades
                    GROUP BY exchange, trade_id, timestamp
                )
            """)

            removed_count = cursor.rowcount
            conn.commit()

            logger.info(
                f"Deduplication complete: removed {removed_count} duplicate trades "
                f"from {duplicate_groups} duplicate groups"
            )

            return removed_count

    async def get_connection(self) -> aiosqlite.Connection:
        """
        Get a reusable async connection with proper WAL mode settings.

        This connection can be reused across multiple operations for better performance.
        Remember to call close_connection() when done with batch operations.

        Returns:
            Async SQLite connection
        """
        if self._connection is None:
            if self._connection_lock is None:
                self._connection_lock = asyncio.Lock()

            async with self._connection_lock:
                if self._connection is None:
                    self._connection = await aiosqlite.connect(self.db_path)
                    # Enable WAL mode for better concurrency
                    await self._connection.execute("PRAGMA journal_mode=WAL")
                    # Set reasonable timeout for concurrent access
                    await self._connection.execute("PRAGMA busy_timeout=5000")
                    logger.debug("Opened pooled connection to trade cache")

        return self._connection

    async def close_connection(self) -> None:
        """Close the pooled connection if it exists."""
        if self._connection:
            await self._connection.close()
            self._connection = None
            logger.debug("Closed pooled connection to trade cache")

    async def __aenter__(self):
        """Async context manager entry."""
        await self.get_connection()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close_connection()
