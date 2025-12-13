"""
OTC Repository Module

Handles OTC (Over-The-Counter) transaction operations.
"""

import aiosqlite
import pandas as pd
from pathlib import Path
from typing import Optional

from src.utils import get_logger

logger = get_logger(__name__)


class OTCRepository:
    """Repository for OTC transaction operations."""

    def __init__(self, db_path: Path):
        """
        Initialize OTC repository.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

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
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute("""
                INSERT INTO otc_transactions (
                    date, counterparty, alkimi_amount, usd_amount,
                    price, side, notes, created_by
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                date_str, counterparty, alkimi_amount, usd_amount,
                price, side, notes, created_by
            ))
            await conn.commit()
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

        # For async compatibility with pandas, we'll fetch rows and convert
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()

            # Get column names
            columns = [description[0] for description in cursor.description]

            # Convert to DataFrame
            if rows:
                df = pd.DataFrame(rows, columns=columns)
            else:
                df = pd.DataFrame(columns=columns)

        logger.debug(f"Retrieved {len(df)} OTC transactions")
        return df

    async def get_otc_transaction(self, transaction_id: int) -> Optional[dict]:
        """
        Get a specific OTC transaction by ID.

        Args:
            transaction_id: Transaction ID

        Returns:
            Transaction dict or None if not found
        """
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM otc_transactions WHERE id = ?",
                (transaction_id,)
            )
            row = await cursor.fetchone()
            return dict(row) if row else None

    async def update_otc_transaction(
        self,
        transaction_id: int,
        **fields
    ) -> bool:
        """
        Update an OTC transaction.

        Args:
            transaction_id: Transaction ID
            **fields: Fields to update

        Returns:
            True if updated, False if not found
        """
        if not fields:
            return False

        # Build update query dynamically
        set_clause = ", ".join([f"{key} = ?" for key in fields.keys()])
        values = list(fields.values()) + [transaction_id]

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                f"UPDATE otc_transactions SET {set_clause} WHERE id = ?",
                values
            )
            await conn.commit()
            updated = cursor.rowcount > 0

        if updated:
            logger.info(f"Updated OTC transaction {transaction_id}")
        return updated

    async def delete_otc_transaction(self, transaction_id: int) -> bool:
        """
        Delete an OTC transaction.

        Args:
            transaction_id: Transaction ID

        Returns:
            True if deleted, False if not found
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM otc_transactions WHERE id = ?",
                (transaction_id,)
            )
            await conn.commit()
            deleted = cursor.rowcount > 0

        if deleted:
            logger.info(f"Deleted OTC transaction {transaction_id}")
        return deleted

    async def get_otc_summary(
        self,
        since: Optional[str] = None,
        until: Optional[str] = None
    ) -> dict:
        """
        Get summary statistics for OTC transactions.

        Args:
            since: Start date (ISO format)
            until: End date (ISO format)

        Returns:
            Dict with summary statistics
        """
        df = await self.get_otc_transactions(since=since, until=until)

        if df.empty:
            return {
                'total_transactions': 0,
                'total_alkimi': 0,
                'total_usd': 0,
                'avg_price': 0,
                'buy_count': 0,
                'sell_count': 0,
                'buy_alkimi': 0,
                'sell_alkimi': 0
            }

        buys = df[df['side'] == 'buy']
        sells = df[df['side'] == 'sell']

        return {
            'total_transactions': len(df),
            'total_alkimi': float(df['alkimi_amount'].sum()),
            'total_usd': float(df['usd_amount'].sum()),
            'avg_price': float(df['price'].mean()),
            'min_price': float(df['price'].min()),
            'max_price': float(df['price'].max()),
            'buy_count': len(buys),
            'sell_count': len(sells),
            'buy_alkimi': float(buys['alkimi_amount'].sum()) if not buys.empty else 0,
            'sell_alkimi': float(sells['alkimi_amount'].sum()) if not sells.empty else 0,
            'buy_usd': float(buys['usd_amount'].sum()) if not buys.empty else 0,
            'sell_usd': float(sells['usd_amount'].sum()) if not sells.empty else 0
        }
