"""
Snapshot Repository Module

Handles daily balance snapshot operations including loading and querying historical snapshots.
"""

from datetime import date, datetime, timedelta
from typing import List, Dict, Optional

from src.data.daily_snapshot import DailySnapshot
from src.utils import get_logger

logger = get_logger(__name__)


class SnapshotRepository:
    """Repository for snapshot operations."""

    def __init__(self, snapshot_manager: DailySnapshot):
        """
        Initialize snapshot repository.

        Args:
            snapshot_manager: DailySnapshot instance for snapshot data
        """
        self.snapshot_manager = snapshot_manager

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

    async def get_snapshot(
        self,
        snapshot_date: Optional[date] = None
    ) -> Optional[Dict]:
        """
        Get a specific snapshot.

        Args:
            snapshot_date: Date to load (defaults to today)

        Returns:
            Snapshot dict with 'date', 'timestamp', and 'balances', or None if not found
        """
        if snapshot_date is None:
            snapshot_date = date.today()

        snapshot_data = self.snapshot_manager.load_snapshot(snapshot_date)

        if snapshot_data:
            return {
                'date': snapshot_date.isoformat(),
                'timestamp': datetime.combine(snapshot_date, datetime.min.time()).isoformat(),
                'balances': snapshot_data
            }

        return None

    async def save_snapshot(
        self,
        balances: Dict[str, float],
        snapshot_date: Optional[date] = None
    ) -> None:
        """
        Save a balance snapshot.

        Args:
            balances: Dictionary of asset balances
            snapshot_date: Date for snapshot (defaults to today)
        """
        self.snapshot_manager.save_snapshot(balances, snapshot_date)
        logger.info(f"Saved snapshot for {snapshot_date or date.today()}")

    async def get_latest_snapshot(self) -> Optional[Dict]:
        """
        Get the most recent available snapshot.

        Returns:
            Latest snapshot dict or None if no snapshots exist
        """
        # Try today first
        snapshot = await self.get_snapshot(date.today())
        if snapshot:
            return snapshot

        # Try yesterday
        snapshot_data = self.snapshot_manager.get_yesterday_snapshot()
        if snapshot_data:
            yesterday = date.today() - timedelta(days=1)
            return {
                'date': yesterday.isoformat(),
                'timestamp': datetime.combine(yesterday, datetime.min.time()).isoformat(),
                'balances': snapshot_data
            }

        # Try up to 7 days back
        for days_back in range(2, 8):
            check_date = date.today() - timedelta(days=days_back)
            snapshot_data = self.snapshot_manager.load_snapshot(check_date)
            if snapshot_data:
                return {
                    'date': check_date.isoformat(),
                    'timestamp': datetime.combine(check_date, datetime.min.time()).isoformat(),
                    'balances': snapshot_data
                }

        logger.warning("No snapshots found in the last 7 days")
        return None

    async def has_snapshot(self, snapshot_date: date) -> bool:
        """
        Check if snapshot exists for a date.

        Args:
            snapshot_date: Date to check

        Returns:
            True if snapshot exists
        """
        return self.snapshot_manager.has_snapshot(snapshot_date)

    async def get_snapshot_range(
        self,
        start_date: date,
        end_date: date
    ) -> List[Dict]:
        """
        Get snapshots within a date range.

        Args:
            start_date: Start date (inclusive)
            end_date: End date (inclusive)

        Returns:
            List of snapshot dicts in chronological order
        """
        snapshots = []
        current_date = start_date

        while current_date <= end_date:
            snapshot_data = self.snapshot_manager.load_snapshot(current_date)
            if snapshot_data:
                snapshots.append({
                    'date': current_date.isoformat(),
                    'timestamp': datetime.combine(current_date, datetime.min.time()).isoformat(),
                    'balances': snapshot_data
                })
            current_date += timedelta(days=1)

        logger.debug(
            f"Retrieved {len(snapshots)} snapshots from {start_date} to {end_date}"
        )
        return snapshots

    async def get_balance_history(
        self,
        asset: str,
        days: int = 30
    ) -> List[Dict]:
        """
        Get balance history for a specific asset over time.

        Args:
            asset: Asset symbol to track
            days: Number of days to look back

        Returns:
            List of {date, balance} dicts for the asset
        """
        snapshots = await self.get_snapshots(days)
        history = []

        for snapshot in snapshots:
            balances = snapshot['balances']
            total_balance = 0.0

            # Sum up the asset across all accounts
            for key, value in balances.items():
                if key == asset or key.endswith(f'_{asset}'):
                    total_balance += float(value)

            if total_balance > 0:
                history.append({
                    'date': snapshot['date'],
                    'balance': total_balance
                })

        logger.debug(f"Retrieved balance history for {asset}: {len(history)} data points")
        return history
