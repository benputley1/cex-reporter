"""
P&L Configuration and OTC Transaction Management for ALKIMI Slack Bot.

This module provides:
- P&L calculation method configuration (FIFO, LIFO, Average)
- OTC transaction management
- Complete P&L calculation with realized and unrealized components
"""

from enum import Enum
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
from datetime import datetime
import sqlite3
import json
import logging
from collections import deque
import pandas as pd

logger = logging.getLogger(__name__)


class CostBasisMethod(Enum):
    """Cost basis calculation methods."""
    FIFO = "fifo"      # First In, First Out
    LIFO = "lifo"      # Last In, First Out
    AVERAGE = "avg"    # Average Cost


@dataclass
class PnLReport:
    """P&L calculation result."""
    period_start: datetime
    period_end: datetime

    # Realized P&L
    total_sells: float
    total_cost_basis: float
    realized_pnl: float

    # Unrealized P&L
    current_holdings: float
    avg_cost_per_token: float
    current_price: float
    unrealized_pnl: float

    # Net P&L
    net_pnl: float

    # Breakdown
    by_exchange: Dict[str, float]
    trade_count: int

    def __str__(self) -> str:
        """Format P&L report as string."""
        return (
            f"P&L Report ({self.period_start.date()} to {self.period_end.date()})\n"
            f"{'='*60}\n"
            f"Realized P&L:\n"
            f"  Total Sells: ${self.total_sells:,.2f}\n"
            f"  Cost Basis: ${self.total_cost_basis:,.2f}\n"
            f"  Realized P&L: ${self.realized_pnl:,.2f}\n"
            f"\n"
            f"Unrealized P&L:\n"
            f"  Holdings: {self.current_holdings:,.0f} ALKIMI\n"
            f"  Avg Cost: ${self.avg_cost_per_token:.6f}\n"
            f"  Current Price: ${self.current_price:.6f}\n"
            f"  Unrealized P&L: ${self.unrealized_pnl:,.2f}\n"
            f"\n"
            f"Net P&L: ${self.net_pnl:,.2f}\n"
            f"Trades: {self.trade_count}\n"
        )


@dataclass
class OTCTransaction:
    """An OTC transaction record."""
    id: int
    date: datetime
    counterparty: str
    alkimi_amount: float
    usd_amount: float
    price: float
    side: str  # 'buy' or 'sell'
    notes: str
    created_by: str
    created_at: datetime

    def __str__(self) -> str:
        """Format OTC transaction as string."""
        return (
            f"OTC #{self.id}: {self.side.upper()} {self.alkimi_amount:,.0f} ALKIMI "
            f"@ ${self.price:.6f} = ${self.usd_amount:,.2f} "
            f"({self.counterparty}) on {self.date.date()}"
        )


class PnLConfig:
    """Manage P&L calculation configuration."""

    DEFAULT_CONFIG = {
        'cost_basis_method': 'fifo',
        'include_fees': 'true',
        'excluded_accounts': '[]',
        'base_currency': 'USD',
    }

    def __init__(self, db_path: str = "data/trade_cache.db"):
        self.db_path = db_path
        self._ensure_table()
        self._set_defaults()

    def _ensure_table(self):
        """Create pnl_config table if not exists."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pnl_config (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT,
                    updated_by TEXT
                )
            """)

            conn.commit()
            conn.close()
            logger.debug("P&L config table ensured")

        except Exception as e:
            logger.error(f"Error creating pnl_config table: {e}")
            raise

    def _set_defaults(self):
        """Set default config values if not present."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            for key, value in self.DEFAULT_CONFIG.items():
                cursor.execute(
                    "INSERT OR IGNORE INTO pnl_config (key, value, updated_at) VALUES (?, ?, ?)",
                    (key, value, datetime.now().isoformat())
                )

            conn.commit()
            conn.close()
            logger.debug("Default P&L config values set")

        except Exception as e:
            logger.error(f"Error setting default config: {e}")
            raise

    async def get_config(self) -> Dict[str, str]:
        """Get all config as dict."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT key, value FROM pnl_config")
            config = {row[0]: row[1] for row in cursor.fetchall()}

            conn.close()
            return config

        except Exception as e:
            logger.error(f"Error getting config: {e}")
            return {}

    async def get(self, key: str) -> Optional[str]:
        """Get a single config value."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("SELECT value FROM pnl_config WHERE key = ?", (key,))
            row = cursor.fetchone()

            conn.close()
            return row[0] if row else None

        except Exception as e:
            logger.error(f"Error getting config key '{key}': {e}")
            return None

    async def set(self, key: str, value: str, updated_by: str = None) -> bool:
        """Set a config value."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT OR REPLACE INTO pnl_config (key, value, updated_at, updated_by)
                VALUES (?, ?, ?, ?)
                """,
                (key, value, datetime.now().isoformat(), updated_by)
            )

            conn.commit()
            conn.close()

            logger.info(f"Config '{key}' set to '{value}' by {updated_by}")
            return True

        except Exception as e:
            logger.error(f"Error setting config '{key}': {e}")
            return False

    async def get_cost_basis_method(self) -> CostBasisMethod:
        """Get current cost basis method."""
        value = await self.get('cost_basis_method')
        if value == 'lifo':
            return CostBasisMethod.LIFO
        elif value == 'avg':
            return CostBasisMethod.AVERAGE
        else:
            return CostBasisMethod.FIFO

    async def set_cost_basis_method(self, method: CostBasisMethod, updated_by: str = None):
        """Set cost basis method."""
        await self.set('cost_basis_method', method.value, updated_by)
        logger.info(f"Cost basis method set to {method.value} by {updated_by}")

    async def get_excluded_accounts(self) -> List[str]:
        """Get list of excluded account names."""
        value = await self.get('excluded_accounts')
        if not value:
            return []

        try:
            return json.loads(value)
        except json.JSONDecodeError:
            logger.error("Error decoding excluded_accounts JSON")
            return []

    async def exclude_account(self, account: str, updated_by: str = None):
        """Add account to exclusion list."""
        excluded = await self.get_excluded_accounts()

        if account not in excluded:
            excluded.append(account)
            await self.set('excluded_accounts', json.dumps(excluded), updated_by)
            logger.info(f"Account '{account}' excluded by {updated_by}")

    async def include_account(self, account: str, updated_by: str = None):
        """Remove account from exclusion list."""
        excluded = await self.get_excluded_accounts()

        if account in excluded:
            excluded.remove(account)
            await self.set('excluded_accounts', json.dumps(excluded), updated_by)
            logger.info(f"Account '{account}' included by {updated_by}")

    async def include_fees(self) -> bool:
        """Check if fees should be included in P&L."""
        value = await self.get('include_fees')
        return value == 'true' if value else True


class OTCManager:
    """Manage OTC transactions."""

    def __init__(self, db_path: str = "data/trade_cache.db"):
        self.db_path = db_path
        self._ensure_table()

    def _ensure_table(self):
        """Create otc_transactions table if not exists."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
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
                    created_at TEXT NOT NULL
                )
            """)

            # Create index on date for faster queries
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_otc_date
                ON otc_transactions(date)
            """)

            conn.commit()
            conn.close()
            logger.debug("OTC transactions table ensured")

        except Exception as e:
            logger.error(f"Error creating otc_transactions table: {e}")
            raise

    async def add(self,
                  date: datetime,
                  alkimi_amount: float,
                  usd_amount: float,
                  side: str,
                  counterparty: str = None,
                  notes: str = None,
                  created_by: str = None) -> int:
        """Add OTC transaction. Returns ID."""
        try:
            # Validate side
            if side.lower() not in ['buy', 'sell']:
                raise ValueError("Side must be 'buy' or 'sell'")

            # Calculate price
            price = abs(usd_amount / alkimi_amount) if alkimi_amount != 0 else 0

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                INSERT INTO otc_transactions
                (date, counterparty, alkimi_amount, usd_amount, price, side, notes, created_by, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    date.isoformat(),
                    counterparty,
                    alkimi_amount,
                    usd_amount,
                    price,
                    side.lower(),
                    notes,
                    created_by,
                    datetime.now().isoformat()
                )
            )

            otc_id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(f"OTC transaction #{otc_id} added: {side} {alkimi_amount:,.0f} @ ${price:.6f} by {created_by}")
            return otc_id

        except Exception as e:
            logger.error(f"Error adding OTC transaction: {e}")
            raise

    async def list_all(self) -> List[OTCTransaction]:
        """List all OTC transactions."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, date, counterparty, alkimi_amount, usd_amount, price,
                       side, notes, created_by, created_at
                FROM otc_transactions
                ORDER BY date DESC
            """)

            transactions = []
            for row in cursor.fetchall():
                transactions.append(OTCTransaction(
                    id=row[0],
                    date=datetime.fromisoformat(row[1]),
                    counterparty=row[2] or "Unknown",
                    alkimi_amount=row[3],
                    usd_amount=row[4],
                    price=row[5],
                    side=row[6],
                    notes=row[7] or "",
                    created_by=row[8] or "Unknown",
                    created_at=datetime.fromisoformat(row[9])
                ))

            conn.close()
            return transactions

        except Exception as e:
            logger.error(f"Error listing OTC transactions: {e}")
            return []

    async def get(self, id: int) -> Optional[OTCTransaction]:
        """Get OTC transaction by ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT id, date, counterparty, alkimi_amount, usd_amount, price,
                       side, notes, created_by, created_at
                FROM otc_transactions
                WHERE id = ?
            """, (id,))

            row = cursor.fetchone()
            conn.close()

            if not row:
                return None

            return OTCTransaction(
                id=row[0],
                date=datetime.fromisoformat(row[1]),
                counterparty=row[2] or "Unknown",
                alkimi_amount=row[3],
                usd_amount=row[4],
                price=row[5],
                side=row[6],
                notes=row[7] or "",
                created_by=row[8] or "Unknown",
                created_at=datetime.fromisoformat(row[9])
            )

        except Exception as e:
            logger.error(f"Error getting OTC transaction #{id}: {e}")
            return None

    async def remove(self, id: int) -> bool:
        """Remove OTC transaction by ID."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("DELETE FROM otc_transactions WHERE id = ?", (id,))
            deleted = cursor.rowcount > 0

            conn.commit()
            conn.close()

            if deleted:
                logger.info(f"OTC transaction #{id} removed")
            else:
                logger.warning(f"OTC transaction #{id} not found")

            return deleted

        except Exception as e:
            logger.error(f"Error removing OTC transaction #{id}: {e}")
            return False

    async def get_total_otc_cost_basis(self) -> float:
        """Get total cost basis from OTC buys."""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                SELECT SUM(usd_amount)
                FROM otc_transactions
                WHERE side = 'buy'
            """)

            row = cursor.fetchone()
            conn.close()

            return row[0] if row[0] is not None else 0.0

        except Exception as e:
            logger.error(f"Error getting OTC cost basis: {e}")
            return 0.0

    async def get_otc_trades_df(self) -> pd.DataFrame:
        """Get OTC transactions as DataFrame for P&L calculation."""
        try:
            conn = sqlite3.connect(self.db_path)

            df = pd.read_sql_query("""
                SELECT
                    date as timestamp,
                    'OTC' as exchange,
                    'OTC' as account,
                    side,
                    alkimi_amount as amount,
                    price,
                    usd_amount as total,
                    0 as fee,
                    counterparty as note
                FROM otc_transactions
                ORDER BY date
            """, conn)

            conn.close()

            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])

            return df

        except Exception as e:
            logger.error(f"Error getting OTC trades DataFrame: {e}")
            return pd.DataFrame()


@dataclass
class TradeLot:
    """A lot of tokens from a buy transaction."""
    timestamp: datetime
    amount: float
    price: float
    exchange: str
    remaining: float  # Amount not yet sold

    def __repr__(self) -> str:
        return f"Lot({self.remaining:,.0f} @ ${self.price:.6f} from {self.exchange})"


class PnLCalculator:
    """Calculate P&L using configured method."""

    def __init__(self, data_provider, pnl_config: PnLConfig, otc_manager: OTCManager):
        self.data_provider = data_provider
        self.config = pnl_config
        self.otc = otc_manager

    async def calculate(self,
                        since: datetime = None,
                        until: datetime = None) -> PnLReport:
        """
        Calculate P&L for the given period.
        Includes both exchange trades and OTC transactions.
        """
        try:
            logger.info(f"Calculating P&L from {since} to {until}")

            # Default to all time if not specified
            if not until:
                until = datetime.now()
            if not since:
                since = datetime(2020, 1, 1)  # Start of crypto time :)

            # 1. Get trades from data provider
            exchange_trades = await self._get_exchange_trades()

            # 2. Get OTC transactions
            otc_trades = await self.otc.get_otc_trades_df()

            # 3. Combine all trades
            if not exchange_trades.empty and not otc_trades.empty:
                all_trades = pd.concat([exchange_trades, otc_trades], ignore_index=True)
            elif not exchange_trades.empty:
                all_trades = exchange_trades
            elif not otc_trades.empty:
                all_trades = otc_trades
            else:
                # No trades at all
                return self._empty_report(since, until)

            # 4. Apply exclusion filters
            excluded = await self.config.get_excluded_accounts()
            if excluded:
                all_trades = all_trades[~all_trades['account'].isin(excluded)]
                logger.info(f"Excluded accounts: {excluded}")

            # 5. Filter by date range
            all_trades = all_trades[
                (all_trades['timestamp'] >= since) &
                (all_trades['timestamp'] <= until)
            ]

            if all_trades.empty:
                return self._empty_report(since, until)

            # Sort by timestamp
            all_trades = all_trades.sort_values('timestamp')

            # 6. Calculate using configured cost basis method
            method = await self.config.get_cost_basis_method()

            if method == CostBasisMethod.FIFO:
                cost_basis, realized_pnl = await self.calculate_fifo(all_trades)
            elif method == CostBasisMethod.LIFO:
                cost_basis, realized_pnl = await self.calculate_lifo(all_trades)
            else:  # AVERAGE
                cost_basis, realized_pnl = await self.calculate_average(all_trades)

            # Calculate total sells
            sells = all_trades[all_trades['side'] == 'sell']
            total_sells = sells['total'].sum() if not sells.empty else 0.0

            # 7. Get current holdings and unrealized P&L
            current_holdings, avg_cost = await self.get_current_holdings()
            current_price = await self._get_current_price()

            unrealized_value = current_holdings * current_price
            unrealized_cost = current_holdings * avg_cost
            unrealized_pnl = unrealized_value - unrealized_cost

            # 8. Calculate net P&L
            net_pnl = realized_pnl + unrealized_pnl

            # 9. Get breakdown by exchange
            by_exchange = await self.get_by_exchange(all_trades, since)

            report = PnLReport(
                period_start=since,
                period_end=until,
                total_sells=total_sells,
                total_cost_basis=cost_basis,
                realized_pnl=realized_pnl,
                current_holdings=current_holdings,
                avg_cost_per_token=avg_cost,
                current_price=current_price,
                unrealized_pnl=unrealized_pnl,
                net_pnl=net_pnl,
                by_exchange=by_exchange,
                trade_count=len(all_trades)
            )

            logger.info(f"P&L calculated: Realized=${realized_pnl:,.2f}, Unrealized=${unrealized_pnl:,.2f}, Net=${net_pnl:,.2f}")
            return report

        except Exception as e:
            logger.error(f"Error calculating P&L: {e}")
            raise

    def _empty_report(self, since: datetime, until: datetime) -> PnLReport:
        """Return empty P&L report."""
        return PnLReport(
            period_start=since,
            period_end=until,
            total_sells=0.0,
            total_cost_basis=0.0,
            realized_pnl=0.0,
            current_holdings=0.0,
            avg_cost_per_token=0.0,
            current_price=0.0,
            unrealized_pnl=0.0,
            net_pnl=0.0,
            by_exchange={},
            trade_count=0
        )

    async def _get_exchange_trades(self) -> pd.DataFrame:
        """Get all trades from exchanges."""
        try:
            # This will call the data provider's get_all_trades method
            # Adjust based on your actual data provider interface
            if hasattr(self.data_provider, 'get_all_trades'):
                return await self.data_provider.get_all_trades()

            # Fallback: load from database directly
            conn = sqlite3.connect(self.data_provider.db_path if hasattr(self.data_provider, 'db_path') else 'data/trade_cache.db')
            df = pd.read_sql_query("""
                SELECT timestamp, exchange, account, side, amount, price, total, fee
                FROM trades
                ORDER BY timestamp
            """, conn)
            conn.close()

            if not df.empty:
                df['timestamp'] = pd.to_datetime(df['timestamp'])

            return df

        except Exception as e:
            logger.error(f"Error getting exchange trades: {e}")
            return pd.DataFrame()

    async def _get_current_price(self) -> float:
        """Get current ALKIMI price."""
        try:
            # Try to get from data provider
            if hasattr(self.data_provider, 'get_current_price'):
                price = await self.data_provider.get_current_price('ALKIMI')
                if price:
                    return price

            # Fallback to a default or fetch from API
            # This should be implemented based on your price data source
            logger.warning("Current price not available, using 0.0")
            return 0.0

        except Exception as e:
            logger.error(f"Error getting current price: {e}")
            return 0.0

    async def calculate_fifo(self, trades: pd.DataFrame) -> Tuple[float, float]:
        """
        Calculate realized P&L using FIFO (First In, First Out).
        Returns (cost_basis, realized_pnl).
        """
        try:
            # Queue of buy lots (oldest first)
            buy_lots = deque()
            total_cost_basis = 0.0
            total_proceeds = 0.0

            # Process trades chronologically
            for _, trade in trades.iterrows():
                if trade['side'] == 'buy':
                    # Add to buy queue
                    lot = TradeLot(
                        timestamp=trade['timestamp'],
                        amount=trade['amount'],
                        price=trade['price'],
                        exchange=trade.get('exchange', 'Unknown'),
                        remaining=trade['amount']
                    )
                    buy_lots.append(lot)

                elif trade['side'] == 'sell':
                    # Match against oldest buys
                    sell_amount = trade['amount']
                    sell_price = trade['price']

                    while sell_amount > 0 and buy_lots:
                        oldest_lot = buy_lots[0]

                        # How much can we take from this lot?
                        take_amount = min(sell_amount, oldest_lot.remaining)

                        # Calculate cost and proceeds for this portion
                        cost = take_amount * oldest_lot.price
                        proceeds = take_amount * sell_price

                        total_cost_basis += cost
                        total_proceeds += proceeds

                        # Update remaining
                        oldest_lot.remaining -= take_amount
                        sell_amount -= take_amount

                        # Remove lot if fully consumed
                        if oldest_lot.remaining <= 0:
                            buy_lots.popleft()

                    if sell_amount > 0:
                        logger.warning(f"Sold {sell_amount:,.0f} tokens with no cost basis (short sale?)")

            realized_pnl = total_proceeds - total_cost_basis
            return total_cost_basis, realized_pnl

        except Exception as e:
            logger.error(f"Error in FIFO calculation: {e}")
            raise

    async def calculate_lifo(self, trades: pd.DataFrame) -> Tuple[float, float]:
        """
        Calculate realized P&L using LIFO (Last In, First Out).
        Returns (cost_basis, realized_pnl).
        """
        try:
            # Stack of buy lots (newest first)
            buy_lots = []
            total_cost_basis = 0.0
            total_proceeds = 0.0

            # Process trades chronologically
            for _, trade in trades.iterrows():
                if trade['side'] == 'buy':
                    # Add to buy stack
                    lot = TradeLot(
                        timestamp=trade['timestamp'],
                        amount=trade['amount'],
                        price=trade['price'],
                        exchange=trade.get('exchange', 'Unknown'),
                        remaining=trade['amount']
                    )
                    buy_lots.append(lot)

                elif trade['side'] == 'sell':
                    # Match against newest buys
                    sell_amount = trade['amount']
                    sell_price = trade['price']

                    while sell_amount > 0 and buy_lots:
                        newest_lot = buy_lots[-1]  # Take from end (newest)

                        # How much can we take from this lot?
                        take_amount = min(sell_amount, newest_lot.remaining)

                        # Calculate cost and proceeds for this portion
                        cost = take_amount * newest_lot.price
                        proceeds = take_amount * sell_price

                        total_cost_basis += cost
                        total_proceeds += proceeds

                        # Update remaining
                        newest_lot.remaining -= take_amount
                        sell_amount -= take_amount

                        # Remove lot if fully consumed
                        if newest_lot.remaining <= 0:
                            buy_lots.pop()

                    if sell_amount > 0:
                        logger.warning(f"Sold {sell_amount:,.0f} tokens with no cost basis (short sale?)")

            realized_pnl = total_proceeds - total_cost_basis
            return total_cost_basis, realized_pnl

        except Exception as e:
            logger.error(f"Error in LIFO calculation: {e}")
            raise

    async def calculate_average(self, trades: pd.DataFrame) -> Tuple[float, float]:
        """
        Calculate realized P&L using average cost.
        Returns (cost_basis, realized_pnl).
        """
        try:
            total_holdings = 0.0
            total_cost = 0.0
            total_cost_basis = 0.0
            total_proceeds = 0.0

            # Process trades chronologically
            for _, trade in trades.iterrows():
                if trade['side'] == 'buy':
                    # Add to holdings and update average
                    total_holdings += trade['amount']
                    total_cost += trade['amount'] * trade['price']

                elif trade['side'] == 'sell':
                    # Calculate current average cost
                    avg_cost = total_cost / total_holdings if total_holdings > 0 else 0

                    sell_amount = trade['amount']
                    sell_price = trade['price']

                    # Calculate cost basis using average
                    cost = sell_amount * avg_cost
                    proceeds = sell_amount * sell_price

                    total_cost_basis += cost
                    total_proceeds += proceeds

                    # Update holdings and total cost
                    total_holdings -= sell_amount
                    total_cost -= cost

                    if total_holdings < 0:
                        logger.warning(f"Holdings went negative: {total_holdings:,.0f}")
                        total_holdings = 0
                        total_cost = 0

            realized_pnl = total_proceeds - total_cost_basis
            return total_cost_basis, realized_pnl

        except Exception as e:
            logger.error(f"Error in average cost calculation: {e}")
            raise

    async def get_by_exchange(self,
                              trades: pd.DataFrame,
                              since: datetime = None) -> Dict[str, float]:
        """Get P&L breakdown by exchange."""
        try:
            if trades.empty:
                return {}

            breakdown = {}

            # Group by exchange
            for exchange in trades['exchange'].unique():
                exchange_trades = trades[trades['exchange'] == exchange]

                # Calculate simple P&L for this exchange
                sells = exchange_trades[exchange_trades['side'] == 'sell']
                buys = exchange_trades[exchange_trades['side'] == 'buy']

                sell_total = sells['total'].sum() if not sells.empty else 0.0
                buy_total = buys['total'].sum() if not buys.empty else 0.0

                breakdown[exchange] = sell_total - buy_total

            return breakdown

        except Exception as e:
            logger.error(f"Error getting P&L by exchange: {e}")
            return {}

    async def get_current_holdings(self) -> Tuple[float, float]:
        """
        Get current holdings and average cost.
        Returns (total_alkimi, avg_cost_per_token).
        """
        try:
            # Get all trades (no date filter)
            exchange_trades = await self._get_exchange_trades()
            otc_trades = await self.otc.get_otc_trades_df()

            # Combine
            if not exchange_trades.empty and not otc_trades.empty:
                all_trades = pd.concat([exchange_trades, otc_trades], ignore_index=True)
            elif not exchange_trades.empty:
                all_trades = exchange_trades
            elif not otc_trades.empty:
                all_trades = otc_trades
            else:
                return 0.0, 0.0

            # Apply exclusions
            excluded = await self.config.get_excluded_accounts()
            if excluded:
                all_trades = all_trades[~all_trades['account'].isin(excluded)]

            # Calculate net position
            buys = all_trades[all_trades['side'] == 'buy']
            sells = all_trades[all_trades['side'] == 'sell']

            total_bought = buys['amount'].sum() if not buys.empty else 0.0
            total_sold = sells['amount'].sum() if not sells.empty else 0.0

            current_holdings = total_bought - total_sold

            # Calculate average cost of remaining holdings
            # Use current method to determine remaining lots
            method = await self.config.get_cost_basis_method()

            if method == CostBasisMethod.AVERAGE:
                # Simple average of all buys
                if not buys.empty:
                    total_cost = (buys['amount'] * buys['price']).sum()
                    avg_cost = total_cost / total_bought if total_bought > 0 else 0.0
                else:
                    avg_cost = 0.0
            else:
                # For FIFO/LIFO, need to track remaining lots
                avg_cost = await self._calculate_remaining_avg_cost(all_trades, method)

            return current_holdings, avg_cost

        except Exception as e:
            logger.error(f"Error getting current holdings: {e}")
            return 0.0, 0.0

    async def _calculate_remaining_avg_cost(self,
                                           trades: pd.DataFrame,
                                           method: CostBasisMethod) -> float:
        """Calculate average cost of remaining holdings using FIFO/LIFO."""
        try:
            trades = trades.sort_values('timestamp')

            if method == CostBasisMethod.FIFO:
                lots = deque()
            else:  # LIFO
                lots = []

            # Build up remaining lots
            for _, trade in trades.iterrows():
                if trade['side'] == 'buy':
                    lot = TradeLot(
                        timestamp=trade['timestamp'],
                        amount=trade['amount'],
                        price=trade['price'],
                        exchange=trade.get('exchange', 'Unknown'),
                        remaining=trade['amount']
                    )
                    if method == CostBasisMethod.FIFO:
                        lots.append(lot)
                    else:
                        lots.append(lot)

                elif trade['side'] == 'sell':
                    sell_amount = trade['amount']

                    while sell_amount > 0 and lots:
                        if method == CostBasisMethod.FIFO:
                            lot = lots[0]
                        else:
                            lot = lots[-1]

                        take_amount = min(sell_amount, lot.remaining)
                        lot.remaining -= take_amount
                        sell_amount -= take_amount

                        if lot.remaining <= 0:
                            if method == CostBasisMethod.FIFO:
                                lots.popleft()
                            else:
                                lots.pop()

            # Calculate weighted average of remaining lots
            if not lots:
                return 0.0

            total_value = sum(lot.remaining * lot.price for lot in lots)
            total_amount = sum(lot.remaining for lot in lots)

            return total_value / total_amount if total_amount > 0 else 0.0

        except Exception as e:
            logger.error(f"Error calculating remaining average cost: {e}")
            return 0.0


# Example usage and testing
if __name__ == "__main__":
    import asyncio

    async def main():
        # Initialize components
        config = PnLConfig()
        otc = OTCManager()

        # Set FIFO method
        await config.set_cost_basis_method(CostBasisMethod.FIFO, "admin")

        # Add sample OTC transaction
        otc_id = await otc.add(
            date=datetime(2025, 11, 15),
            alkimi_amount=3_000_000,
            usd_amount=82_000,
            side="buy",
            counterparty="RAMAN",
            notes="OTC purchase for market making",
            created_by="trader1"
        )
        print(f"Added OTC transaction #{otc_id}")

        # List OTC transactions
        otc_list = await otc.list_all()
        print(f"\nOTC Transactions: {len(otc_list)}")
        for txn in otc_list:
            print(f"  {txn}")

        # Display config
        cfg = await config.get_config()
        print(f"\nP&L Configuration:")
        for key, value in cfg.items():
            print(f"  {key}: {value}")

        print("\nP&L configuration module ready!")

    asyncio.run(main())
