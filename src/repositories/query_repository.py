"""
Query Repository Module

Handles query history and saved functions operations.
"""

import aiosqlite
import json
from pathlib import Path
from typing import List, Dict, Any, Optional

from src.utils import get_logger

logger = get_logger(__name__)


class QueryRepository:
    """Repository for query history and saved functions operations."""

    def __init__(self, db_path: Path):
        """
        Initialize query repository.

        Args:
            db_path: Path to SQLite database file
        """
        self.db_path = db_path

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

        Args:
            user_id: User ID who made the query
            query_text: The query text
            query_type: Type of query
            user_name: User's display name (optional)
            channel_id: Channel ID where query was made (optional)
            generated_code: Generated code for the query (optional)
            result_summary: Summary of results (optional)
            execution_time_ms: Execution time in milliseconds (optional)
            success: Whether query succeeded (default: True)
            error_message: Error message if failed (optional)

        Returns:
            ID of the saved query record
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute("""
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
            await conn.commit()
            logger.debug(f"Saved query history for user {user_id}")
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
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row

            if user_id:
                query = """
                    SELECT * FROM query_history
                    WHERE user_id = ?
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                cursor = await conn.execute(query, (user_id, limit))
            else:
                query = """
                    SELECT * FROM query_history
                    ORDER BY created_at DESC
                    LIMIT ?
                """
                cursor = await conn.execute(query, (limit,))

            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

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
        tools_json = json.dumps(tools_used) if tools_used else None

        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute("""
                INSERT INTO conversation_logs (
                    thread_ts, user_id, user_message, assistant_response,
                    tools_used, model, processing_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                thread_ts, user_id, user_message, assistant_response,
                tools_json, model, processing_time_ms
            ))
            await conn.commit()
            logger.debug(f"Saved conversation log for user {user_id}")
            return cursor.lastrowid

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
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    INSERT INTO saved_functions (name, description, code, created_by)
                    VALUES (?, ?, ?, ?)
                """, (name, description, code, created_by))
                await conn.commit()
                logger.info(f"Saved function '{name}' by {created_by}")
                return True
        except aiosqlite.IntegrityError:
            logger.warning(f"Function '{name}' already exists")
            return False

    async def get_function(self, name: str) -> Optional[Dict[str, Any]]:
        """
        Get a saved function by name.

        Args:
            name: Function name

        Returns:
            Function dict or None if not found
        """
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute(
                "SELECT * FROM saved_functions WHERE name = ?",
                (name,)
            )
            row = await cursor.fetchone()

            if row:
                # Update usage stats
                await conn.execute("""
                    UPDATE saved_functions
                    SET last_used = CURRENT_TIMESTAMP,
                        use_count = use_count + 1
                    WHERE name = ?
                """, (name,))
                await conn.commit()

                return dict(row)
            return None

    async def list_functions(self) -> List[Dict[str, Any]]:
        """
        List all saved functions.

        Returns:
            List of function metadata (without code)
        """
        async with aiosqlite.connect(self.db_path) as conn:
            conn.row_factory = aiosqlite.Row
            cursor = await conn.execute("""
                SELECT name, description, created_by, created_at, last_used, use_count
                FROM saved_functions
                ORDER BY use_count DESC, name ASC
            """)
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

    async def delete_function(self, name: str) -> bool:
        """
        Delete a saved function.

        Args:
            name: Function name

        Returns:
            True if deleted, False if not found
        """
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "DELETE FROM saved_functions WHERE name = ?",
                (name,)
            )
            await conn.commit()
            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted function '{name}'")
            return deleted
