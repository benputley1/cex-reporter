"""
Thread Repository Module

Handles thread management operations for Slack bot thread tracking.
"""

import aiosqlite
import sqlite3
from pathlib import Path
from typing import Set, List

from src.utils import get_logger

logger = get_logger(__name__)


class ThreadRepository:
    """Repository for thread management operations."""

    def __init__(self, db_path: Path):
        """
        Initialize thread repository.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

    async def add_active_thread(self, thread_ts: str, channel_id: str) -> None:
        """
        Track a thread the bot is participating in.

        Args:
            thread_ts: Slack thread timestamp (primary identifier)
            channel_id: Channel ID where the thread is located
        """
        async with aiosqlite.connect(self.db_path) as conn:
            await conn.execute(
                "INSERT OR IGNORE INTO active_threads (thread_ts, channel_id) VALUES (?, ?)",
                (thread_ts, channel_id)
            )
            await conn.commit()
        logger.debug(f"Added active thread: {thread_ts} in channel {channel_id}")

    async def is_active_thread(self, thread_ts: str) -> bool:
        """
        Check if bot is participating in this thread.

        Args:
            thread_ts: Slack thread timestamp

        Returns:
            True if the bot is tracking this thread
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT 1 FROM active_threads WHERE thread_ts = ?",
                (thread_ts,)
            )
            result = await cursor.fetchone()
            return result is not None

    async def load_active_threads(self) -> Set[str]:
        """
        Load all active thread IDs (for startup).

        Returns:
            Set of thread_ts values the bot is participating in
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute("SELECT thread_ts FROM active_threads")
            rows = await cursor.fetchall()
            threads = {row[0] for row in rows}
        logger.info(f"Loaded {len(threads)} active threads from database")
        return threads

    def load_active_threads_sync(self) -> Set[str]:
        """
        Load all active thread IDs (synchronous version for startup).

        Returns:
            Set of thread_ts values the bot is participating in
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("SELECT thread_ts FROM active_threads")
            rows = cursor.fetchall()
            threads = {row[0] for row in rows}
        logger.info(f"Loaded {len(threads)} active threads from database")
        return threads

    async def cleanup_old_threads(self, days: int = 30) -> int:
        """
        Remove threads older than specified days to prevent unbounded growth.

        Args:
            days: Remove threads older than this many days

        Returns:
            Number of threads removed
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM active_threads WHERE created_at < datetime('now', ?)",
                (f'-{days} days',)
            )
            await conn.commit()
            removed = cursor.rowcount
        if removed > 0:
            logger.info(f"Cleaned up {removed} threads older than {days} days")
        return removed

    def cleanup_old_threads_sync(self, days: int = 30) -> int:
        """
        Remove threads older than specified days (synchronous version).

        Args:
            days: Remove threads older than this many days

        Returns:
            Number of threads removed
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM active_threads WHERE created_at < datetime('now', ?)",
                (f'-{days} days',)
            )
            conn.commit()
            removed = cursor.rowcount
        if removed > 0:
            logger.info(f"Cleaned up {removed} threads older than {days} days")
        return removed

    async def get_stale_threads(self, days: int = 7) -> List[str]:
        """
        Get list of thread IDs that are older than specified days.
        Used for periodic cleanup without deleting from database.

        Args:
            days: Get threads older than this many days

        Returns:
            List of thread_ts values that are stale
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "SELECT thread_ts FROM active_threads WHERE created_at < datetime('now', ?)",
                (f'-{days} days',)
            )
            rows = await cursor.fetchall()
            stale_threads = [row[0] for row in rows]

        if stale_threads:
            logger.debug(f"Found {len(stale_threads)} stale threads older than {days} days")
        return stale_threads

    def get_stale_threads_sync(self, days: int = 7) -> List[str]:
        """
        Get list of thread IDs that are older than specified days (synchronous version).

        Args:
            days: Get threads older than this many days

        Returns:
            List of thread_ts values that are stale
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT thread_ts FROM active_threads WHERE created_at < datetime('now', ?)",
                (f'-{days} days',)
            )
            stale_threads = [row[0] for row in cursor.fetchall()]

        if stale_threads:
            logger.debug(f"Found {len(stale_threads)} stale threads older than {days} days")
        return stale_threads

    async def remove_thread(self, thread_ts: str) -> bool:
        """
        Remove a specific thread from tracking.

        Args:
            thread_ts: Thread timestamp to remove

        Returns:
            True if removed, False if not found
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM active_threads WHERE thread_ts = ?",
                (thread_ts,)
            )
            await conn.commit()
            removed = cursor.rowcount > 0
        if removed:
            logger.debug(f"Removed thread: {thread_ts}")
        return removed

    async def get_thread_count(self) -> int:
        """
        Get total number of active threads.

        Returns:
            Number of active threads
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute("SELECT COUNT(*) FROM active_threads")
            row = await cursor.fetchone()
            return row[0] if row else 0
