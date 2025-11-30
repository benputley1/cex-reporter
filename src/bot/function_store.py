"""Function storage for saved Python analysis functions."""

from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
import sqlite3
import json
import logging
import aiosqlite

logger = logging.getLogger(__name__)


@dataclass
class SavedFunction:
    """A saved Python function."""
    id: int
    name: str
    description: str
    code: str
    created_by: str
    created_at: datetime
    last_used: Optional[datetime]
    use_count: int

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'code': self.code,
            'created_by': self.created_by,
            'created_at': self.created_at.isoformat(),
            'last_used': self.last_used.isoformat() if self.last_used else None,
            'use_count': self.use_count
        }


class FunctionStore:
    """CRUD operations for saved Python functions."""

    def __init__(self, db_path: str = "data/trade_cache.db"):
        """
        Initialize function store.

        Args:
            db_path: Path to SQLite database
        """
        self.db_path = db_path
        self._init_sync()

    def _init_sync(self):
        """Initialize database table synchronously."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS saved_functions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT UNIQUE NOT NULL,
                    description TEXT NOT NULL,
                    code TEXT NOT NULL,
                    created_by TEXT NOT NULL,
                    created_at TIMESTAMP NOT NULL,
                    last_used TIMESTAMP,
                    use_count INTEGER DEFAULT 0
                )
            ''')

            # Create indexes for performance
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_function_name
                ON saved_functions(name)
            ''')

            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_function_created_by
                ON saved_functions(created_by)
            ''')

            conn.commit()
            logger.info("Function store initialized")
        finally:
            conn.close()

    async def save(
        self,
        name: str,
        code: str,
        description: str,
        created_by: str
    ) -> bool:
        """
        Save a new function or update existing one.

        Args:
            name: Unique function name
            code: Python code
            description: Description of what the function does
            created_by: Slack user ID who created it

        Returns:
            True if successful, False otherwise
        """
        if not name or not code or not description:
            logger.error("Cannot save function: name, code, and description required")
            return False

        # Validate name (alphanumeric and underscores only)
        if not name.replace('_', '').isalnum():
            logger.error(f"Invalid function name: {name}")
            return False

        async with aiosqlite.connect(self.db_path) as db:
            try:
                # Check if function exists
                cursor = await db.execute(
                    'SELECT id FROM saved_functions WHERE name = ?',
                    (name,)
                )
                existing = await cursor.fetchone()

                if existing:
                    # Update existing function
                    await db.execute('''
                        UPDATE saved_functions
                        SET code = ?, description = ?, created_by = ?
                        WHERE name = ?
                    ''', (code, description, created_by, name))
                    logger.info(f"Updated function: {name}")
                else:
                    # Insert new function
                    await db.execute('''
                        INSERT INTO saved_functions
                        (name, code, description, created_by, created_at, use_count)
                        VALUES (?, ?, ?, ?, ?, 0)
                    ''', (name, code, description, created_by, datetime.now()))
                    logger.info(f"Saved new function: {name}")

                await db.commit()
                return True

            except sqlite3.IntegrityError as e:
                logger.error(f"Database integrity error saving function: {e}")
                return False
            except Exception as e:
                logger.error(f"Error saving function: {e}")
                return False

    async def get(self, name: str) -> Optional[SavedFunction]:
        """
        Get a function by name.

        Args:
            name: Function name

        Returns:
            SavedFunction or None if not found
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            cursor = await db.execute(
                'SELECT * FROM saved_functions WHERE name = ?',
                (name,)
            )
            row = await cursor.fetchone()

            if not row:
                return None

            return self._row_to_function(row)

    async def list_all(self, created_by: Optional[str] = None) -> List[SavedFunction]:
        """
        List all saved functions.

        Args:
            created_by: Optional filter by creator

        Returns:
            List of SavedFunction objects, sorted by use_count descending
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row

            if created_by:
                cursor = await db.execute(
                    'SELECT * FROM saved_functions WHERE created_by = ? ORDER BY use_count DESC, name ASC',
                    (created_by,)
                )
            else:
                cursor = await db.execute(
                    'SELECT * FROM saved_functions ORDER BY use_count DESC, name ASC'
                )

            rows = await cursor.fetchall()
            return [self._row_to_function(row) for row in rows]

    async def delete(self, name: str) -> bool:
        """
        Delete a function by name.

        Args:
            name: Function name

        Returns:
            True if deleted, False if not found
        """
        async with aiosqlite.connect(self.db_path) as db:
            cursor = await db.execute(
                'DELETE FROM saved_functions WHERE name = ?',
                (name,)
            )
            await db.commit()

            deleted = cursor.rowcount > 0
            if deleted:
                logger.info(f"Deleted function: {name}")
            else:
                logger.warning(f"Function not found for deletion: {name}")

            return deleted

    async def update_usage(self, name: str):
        """
        Update last_used timestamp and increment use_count.

        Args:
            name: Function name
        """
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute('''
                UPDATE saved_functions
                SET last_used = ?, use_count = use_count + 1
                WHERE name = ?
            ''', (datetime.now(), name))
            await db.commit()
            logger.debug(f"Updated usage for function: {name}")

    async def search(self, query: str) -> List[SavedFunction]:
        """
        Search functions by name or description.

        Args:
            query: Search query (case-insensitive)

        Returns:
            List of matching SavedFunction objects
        """
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            search_pattern = f'%{query}%'

            cursor = await db.execute('''
                SELECT * FROM saved_functions
                WHERE name LIKE ? OR description LIKE ?
                ORDER BY use_count DESC, name ASC
            ''', (search_pattern, search_pattern))

            rows = await cursor.fetchall()
            return [self._row_to_function(row) for row in rows]

    async def get_stats(self) -> Dict:
        """
        Get statistics about saved functions.

        Returns:
            Dictionary with stats (total_functions, total_uses, top_functions)
        """
        async with aiosqlite.connect(self.db_path) as db:
            # Total functions
            cursor = await db.execute('SELECT COUNT(*) FROM saved_functions')
            total_functions = (await cursor.fetchone())[0]

            # Total uses
            cursor = await db.execute('SELECT SUM(use_count) FROM saved_functions')
            total_uses = (await cursor.fetchone())[0] or 0

            # Top 5 functions by usage
            db.row_factory = aiosqlite.Row
            cursor = await db.execute('''
                SELECT name, use_count
                FROM saved_functions
                ORDER BY use_count DESC
                LIMIT 5
            ''')
            top_functions = [
                {'name': row['name'], 'use_count': row['use_count']}
                for row in await cursor.fetchall()
            ]

            return {
                'total_functions': total_functions,
                'total_uses': total_uses,
                'top_functions': top_functions
            }

    async def get_by_creator(self, created_by: str) -> List[SavedFunction]:
        """
        Get all functions created by a specific user.

        Args:
            created_by: Slack user ID

        Returns:
            List of SavedFunction objects
        """
        return await self.list_all(created_by=created_by)

    async def rename(self, old_name: str, new_name: str) -> bool:
        """
        Rename a function.

        Args:
            old_name: Current function name
            new_name: New function name

        Returns:
            True if successful, False otherwise
        """
        # Validate new name
        if not new_name.replace('_', '').isalnum():
            logger.error(f"Invalid new function name: {new_name}")
            return False

        async with aiosqlite.connect(self.db_path) as db:
            try:
                # Check if new name already exists
                cursor = await db.execute(
                    'SELECT id FROM saved_functions WHERE name = ?',
                    (new_name,)
                )
                if await cursor.fetchone():
                    logger.error(f"Function name already exists: {new_name}")
                    return False

                # Rename
                cursor = await db.execute(
                    'UPDATE saved_functions SET name = ? WHERE name = ?',
                    (new_name, old_name)
                )
                await db.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Renamed function: {old_name} -> {new_name}")
                    return True
                else:
                    logger.warning(f"Function not found for rename: {old_name}")
                    return False

            except sqlite3.IntegrityError:
                logger.error(f"Cannot rename to existing name: {new_name}")
                return False

    def _row_to_function(self, row: aiosqlite.Row) -> SavedFunction:
        """Convert database row to SavedFunction object."""
        return SavedFunction(
            id=row['id'],
            name=row['name'],
            description=row['description'],
            code=row['code'],
            created_by=row['created_by'],
            created_at=datetime.fromisoformat(row['created_at']),
            last_used=datetime.fromisoformat(row['last_used']) if row['last_used'] else None,
            use_count=row['use_count']
        )

    async def export_all(self) -> List[Dict]:
        """
        Export all functions as JSON-serializable dictionaries.

        Returns:
            List of function dictionaries
        """
        functions = await self.list_all()
        return [func.to_dict() for func in functions]

    async def import_function(self, func_dict: Dict) -> bool:
        """
        Import a function from dictionary.

        Args:
            func_dict: Dictionary with name, code, description, created_by

        Returns:
            True if successful
        """
        return await self.save(
            name=func_dict['name'],
            code=func_dict['code'],
            description=func_dict['description'],
            created_by=func_dict['created_by']
        )
