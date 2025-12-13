"""
Balance Repository Module

Handles balance-related operations including fetching current balances from snapshots.
"""

from datetime import date
from typing import Dict, Optional

from src.data.daily_snapshot import DailySnapshot
from src.utils import get_logger

logger = get_logger(__name__)


class BalanceRepository:
    """Repository for balance operations."""

    def __init__(self, snapshot_manager: DailySnapshot):
        """
        Initialize balance repository.

        Args:
            snapshot_manager: DailySnapshot instance for balance data
        """
        self.snapshot_manager = snapshot_manager

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

    async def get_balance_for_account(
        self,
        exchange: str,
        account: str
    ) -> Optional[Dict[str, float]]:
        """
        Get balances for a specific exchange/account.

        Args:
            exchange: Exchange name (e.g., 'mexc', 'kucoin')
            account: Account identifier (e.g., 'mm1', 'tm1')

        Returns:
            Dict of {asset: balance} or None if not found
        """
        all_balances = await self.get_balances()
        account_key = f"{exchange}_{account}".lower()
        return all_balances.get(account_key)

    async def get_total_balance(self, asset: str = 'USDT') -> float:
        """
        Get total balance across all accounts for a specific asset.

        Args:
            asset: Asset symbol (default: USDT)

        Returns:
            Total balance for the asset
        """
        all_balances = await self.get_balances()
        total = 0.0

        for account_balances in all_balances.values():
            if asset in account_balances:
                total += account_balances[asset]

        logger.debug(f"Total {asset} balance: {total}")
        return total

    def save_snapshot(
        self,
        balances: Dict[str, float],
        snapshot_date: Optional[date] = None
    ) -> None:
        """
        Save balance snapshot.

        Args:
            balances: Dictionary of asset balances
            snapshot_date: Date for snapshot (defaults to today)
        """
        self.snapshot_manager.save_snapshot(balances, snapshot_date)

    def load_snapshot(
        self,
        snapshot_date: Optional[date] = None
    ) -> Optional[Dict[str, float]]:
        """
        Load balance snapshot for a specific date.

        Args:
            snapshot_date: Date to load (defaults to today)

        Returns:
            Dictionary of balances, or None if not found
        """
        return self.snapshot_manager.load_snapshot(snapshot_date)

    def has_snapshot(self, snapshot_date: date) -> bool:
        """
        Check if snapshot exists for a date.

        Args:
            snapshot_date: Date to check

        Returns:
            True if snapshot exists
        """
        return self.snapshot_manager.has_snapshot(snapshot_date)
