"""
Daily Snapshot Module

Saves daily balance snapshots to track day-over-day changes.
"""

import json
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Optional

from src.utils import get_logger

logger = get_logger(__name__)


class DailySnapshot:
    """Manages daily balance snapshots."""

    def __init__(self, snapshot_dir: str = "data/snapshots"):
        """
        Initialize daily snapshot manager.

        Args:
            snapshot_dir: Directory to store snapshot files
        """
        self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)

    def _get_snapshot_path(self, date_obj: date) -> Path:
        """Get file path for a specific date's snapshot."""
        return self.snapshot_dir / f"snapshot_{date_obj.isoformat()}.json"

    def save_snapshot(self, balances: Dict[str, float], snapshot_date: Optional[date] = None) -> None:
        """
        Save today's balance snapshot.

        Args:
            balances: Dictionary of asset balances (e.g., {'USDT': 1000.0, 'ALKIMI': 50000.0})
            snapshot_date: Date for snapshot (defaults to today)
        """
        if snapshot_date is None:
            snapshot_date = date.today()

        snapshot_path = self._get_snapshot_path(snapshot_date)

        snapshot_data = {
            'date': snapshot_date.isoformat(),
            'timestamp': datetime.now().isoformat(),
            'balances': balances
        }

        with open(snapshot_path, 'w') as f:
            json.dump(snapshot_data, f, indent=2)

        logger.info(f"Saved daily snapshot for {snapshot_date}: {balances}")

    def load_snapshot(self, snapshot_date: Optional[date] = None) -> Optional[Dict[str, float]]:
        """
        Load balance snapshot for a specific date.

        Args:
            snapshot_date: Date to load (defaults to today)

        Returns:
            Dictionary of balances, or None if not found
        """
        if snapshot_date is None:
            snapshot_date = date.today()

        snapshot_path = self._get_snapshot_path(snapshot_date)

        if not snapshot_path.exists():
            logger.debug(f"No snapshot found for {snapshot_date}")
            return None

        try:
            with open(snapshot_path, 'r') as f:
                snapshot_data = json.load(f)

            balances = snapshot_data.get('balances', {})
            logger.debug(f"Loaded snapshot for {snapshot_date}: {balances}")
            return balances

        except Exception as e:
            logger.error(f"Error loading snapshot for {snapshot_date}: {e}")
            return None

    def get_yesterday_snapshot(self) -> Optional[Dict[str, float]]:
        """Load yesterday's balance snapshot."""
        from datetime import timedelta
        yesterday = date.today() - timedelta(days=1)
        return self.load_snapshot(yesterday)

    def has_snapshot(self, snapshot_date: date) -> bool:
        """Check if snapshot exists for a date."""
        return self._get_snapshot_path(snapshot_date).exists()
