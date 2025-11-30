"""
Query Engine Module for ALKIMI Slack Bot

This module provides safe SQL generation and execution capabilities:
1. SQL query validation and sanitization
2. Read-only database access with timeout protection
3. Natural language to SQL conversion via Claude API
4. Schema introspection and sample data retrieval
"""

from typing import Tuple, List, Dict, Any, Optional
from dataclasses import dataclass
import sqlite3
import pandas as pd
import asyncio
import re
import time
from datetime import datetime
import logging
from concurrent.futures import ThreadPoolExecutor, TimeoutError

logger = logging.getLogger(__name__)


@dataclass
class QueryResult:
    """Result of a SQL query execution."""
    success: bool
    data: Optional[pd.DataFrame] = None
    row_count: int = 0
    execution_time_ms: int = 0
    error: Optional[str] = None
    sql: Optional[str] = None


class SQLValidator:
    """Validate SQL queries for safety."""

    # Keywords that can modify or destroy data
    FORBIDDEN_KEYWORDS = [
        'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE',
        'TRUNCATE', 'REPLACE', 'ATTACH', 'DETACH', 'PRAGMA',
        'VACUUM', 'REINDEX', 'ANALYZE', 'EXPLAIN'
    ]

    # Only allow queries on these tables
    ALLOWED_TABLES = {
        'trades',
        'query_history',
        'saved_functions',
        'pnl_config',
        'otc_transactions'
    }

    # SQLite functions safe for read-only queries
    ALLOWED_FUNCTIONS = [
        'SUM', 'AVG', 'COUNT', 'MIN', 'MAX', 'ABS', 'ROUND',
        'strftime', 'date', 'time', 'datetime', 'julianday',
        'UPPER', 'LOWER', 'LENGTH', 'SUBSTR', 'TRIM',
        'COALESCE', 'IFNULL', 'NULLIF', 'CASE', 'CAST',
        'GROUP_CONCAT', 'TOTAL', 'DISTINCT', 'LIKE', 'GLOB',
        'REPLACE'  # String REPLACE function is safe
    ]

    # Maximum rows to return (for safety and performance)
    MAX_ROWS = 100

    def validate(self, sql: str) -> Tuple[bool, str]:
        """
        Validate SQL query is safe to execute.

        Args:
            sql: SQL query string to validate

        Returns:
            Tuple of (is_valid: bool, error_message: str)
            If valid, error_message is empty string.

        Example:
            >>> validator = SQLValidator()
            >>> is_valid, error = validator.validate("SELECT * FROM trades LIMIT 10")
            >>> assert is_valid
            >>> is_valid, error = validator.validate("DROP TABLE trades")
            >>> assert not is_valid
            >>> assert "forbidden keyword" in error.lower()
        """
        sql_stripped = sql.strip()

        # Must be non-empty
        if not sql_stripped:
            return False, "SQL query is empty"

        # Must start with SELECT (case-insensitive)
        sql_upper = sql_stripped.upper()
        if not sql_upper.startswith('SELECT'):
            return False, "Query must start with SELECT (read-only queries only)"

        # Check for forbidden keywords
        for keyword in self.FORBIDDEN_KEYWORDS:
            # Use word boundaries to avoid false positives
            # e.g., "UPDATE" keyword should not match "UPDATED_AT" column
            pattern = r'\b' + keyword + r'\b'
            if re.search(pattern, sql_upper):
                return False, f"Query contains forbidden keyword: {keyword}"

        # Extract and validate table names
        try:
            tables = self.extract_tables(sql)
            invalid_tables = [t for t in tables if t not in self.ALLOWED_TABLES]

            if invalid_tables:
                return False, f"Query references invalid table(s): {', '.join(invalid_tables)}. Allowed tables: {', '.join(sorted(self.ALLOWED_TABLES))}"
        except Exception as e:
            logger.warning(f"Could not extract tables from SQL: {e}")
            # Continue with validation - table extraction is best-effort

        # Check for multiple statements (basic check - no semicolons except at end)
        semicolons = sql_stripped.count(';')
        if semicolons > 1 or (semicolons == 1 and not sql_stripped.endswith(';')):
            return False, "Query contains multiple statements (only single SELECT allowed)"

        return True, ""

    def sanitize(self, sql: str) -> str:
        """
        Sanitize SQL by adding LIMIT if missing.

        Args:
            sql: Valid SQL query (should be validated first)

        Returns:
            Sanitized SQL with LIMIT clause enforced

        Example:
            >>> validator = SQLValidator()
            >>> sql = validator.sanitize("SELECT * FROM trades")
            >>> assert "LIMIT" in sql.upper()
            >>> sql = validator.sanitize("SELECT * FROM trades LIMIT 50")
            >>> assert "LIMIT 50" in sql
        """
        sql_stripped = sql.strip().rstrip(';')
        sql_upper = sql_stripped.upper()

        # Check if LIMIT already exists
        if 'LIMIT' not in sql_upper:
            logger.info(f"Adding LIMIT {self.MAX_ROWS} to query")
            sql_stripped += f" LIMIT {self.MAX_ROWS}"
        else:
            # Verify existing LIMIT doesn't exceed MAX_ROWS
            limit_match = re.search(r'\bLIMIT\s+(\d+)', sql_upper)
            if limit_match:
                limit_value = int(limit_match.group(1))
                if limit_value > self.MAX_ROWS:
                    logger.warning(f"Reducing LIMIT from {limit_value} to {self.MAX_ROWS}")
                    # Replace the limit value
                    sql_stripped = re.sub(
                        r'\bLIMIT\s+\d+',
                        f'LIMIT {self.MAX_ROWS}',
                        sql_stripped,
                        flags=re.IGNORECASE
                    )

        return sql_stripped

    def extract_tables(self, sql: str) -> List[str]:
        """
        Extract table names from SQL query.

        This is a best-effort extraction using regex patterns.
        May not catch all edge cases but works for common queries.

        Args:
            sql: SQL query string

        Returns:
            List of table names found in query

        Example:
            >>> validator = SQLValidator()
            >>> tables = validator.extract_tables("SELECT * FROM trades WHERE id=1")
            >>> assert 'trades' in tables
            >>> tables = validator.extract_tables("SELECT * FROM trades JOIN pnl_config")
            >>> assert 'trades' in tables and 'pnl_config' in tables
        """
        tables = []
        sql_upper = sql.upper()

        # Pattern 1: FROM <table>
        from_pattern = r'\bFROM\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        for match in re.finditer(from_pattern, sql_upper, re.IGNORECASE):
            tables.append(match.group(1).lower())

        # Pattern 2: JOIN <table>
        join_pattern = r'\bJOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)'
        for match in re.finditer(join_pattern, sql_upper, re.IGNORECASE):
            tables.append(match.group(1).lower())

        return list(set(tables))  # Remove duplicates


class QueryEngine:
    """Safe SQL execution engine with natural language support."""

    def __init__(
        self,
        db_path: str = "data/trade_cache.db",
        claude_client = None
    ):
        """
        Initialize the query engine.

        Args:
            db_path: Path to SQLite database file
            claude_client: Optional ClaudeClient instance for NL->SQL generation

        Example:
            >>> from src.bot.prompts import ClaudeClient
            >>> claude = ClaudeClient(api_key="sk-...")
            >>> engine = QueryEngine(claude_client=claude)
            >>> result = await engine.execute_sql("SELECT * FROM trades LIMIT 5")
        """
        self.db_path = db_path
        self.claude_client = claude_client
        self.validator = SQLValidator()
        self.query_timeout = 5  # seconds

        # Thread pool for running blocking database operations
        self._executor = ThreadPoolExecutor(max_workers=2)

        logger.info(f"QueryEngine initialized with db_path={db_path}")

    async def execute_sql(self, sql: str) -> QueryResult:
        """
        Execute a validated SQL query.

        This method:
        1. Validates the SQL for safety
        2. Sanitizes it (adds LIMIT if needed)
        3. Executes with read-only connection
        4. Applies timeout protection
        5. Returns results as DataFrame

        Args:
            sql: SQL SELECT query to execute

        Returns:
            QueryResult with data or error information

        Example:
            >>> engine = QueryEngine()
            >>> result = await engine.execute_sql("SELECT * FROM trades LIMIT 5")
            >>> if result.success:
            ...     print(f"Got {result.row_count} rows")
            ...     print(result.data.head())
            ... else:
            ...     print(f"Error: {result.error}")
        """
        start_time = time.time()

        # Step 1: Validate SQL
        is_valid, error_msg = self.validator.validate(sql)
        if not is_valid:
            logger.warning(f"SQL validation failed: {error_msg}")
            return QueryResult(
                success=False,
                error=f"Invalid SQL: {error_msg}",
                sql=sql
            )

        # Step 2: Sanitize (add/enforce LIMIT)
        sanitized_sql = self.validator.sanitize(sql)
        logger.info(f"Executing SQL: {sanitized_sql}")

        # Step 3: Execute with timeout
        try:
            df = await self._execute_with_timeout(sanitized_sql, self.query_timeout)

            execution_time_ms = int((time.time() - start_time) * 1000)
            row_count = len(df)

            logger.info(f"Query succeeded: {row_count} rows in {execution_time_ms}ms")

            return QueryResult(
                success=True,
                data=df,
                row_count=row_count,
                execution_time_ms=execution_time_ms,
                sql=sanitized_sql
            )

        except TimeoutError:
            error_msg = f"Query exceeded timeout of {self.query_timeout}s"
            logger.error(error_msg)
            return QueryResult(
                success=False,
                error=error_msg,
                sql=sanitized_sql
            )

        except sqlite3.Error as e:
            error_msg = f"Database error: {str(e)}"
            logger.error(error_msg)
            return QueryResult(
                success=False,
                error=error_msg,
                sql=sanitized_sql
            )

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return QueryResult(
                success=False,
                error=error_msg,
                sql=sanitized_sql
            )

    async def generate_and_execute(self, natural_query: str) -> QueryResult:
        """
        Generate SQL from natural language and execute it.

        This method:
        1. Uses Claude API to convert natural language to SQL
        2. Validates the generated SQL
        3. Executes it safely
        4. Returns results

        Args:
            natural_query: Natural language query (e.g., "show today's trades")

        Returns:
            QueryResult with data or error information

        Example:
            >>> engine = QueryEngine(claude_client=claude)
            >>> result = await engine.generate_and_execute("What were the top 5 largest trades?")
            >>> if result.success:
            ...     print(result.data)
            >>> # The generated SQL is included in result.sql
        """
        if not self.claude_client:
            return QueryResult(
                success=False,
                error="No Claude client configured - cannot generate SQL from natural language"
            )

        logger.info(f"Generating SQL for natural query: {natural_query}")

        try:
            # Step 1: Generate SQL using Claude API
            generated_sql = await self.claude_client.generate_sql(natural_query)
            logger.info(f"Generated SQL: {generated_sql}")

            # Step 2: Execute the generated SQL
            # (execute_sql handles validation and sanitization)
            result = await self.execute_sql(generated_sql)

            return result

        except Exception as e:
            error_msg = f"Failed to generate SQL: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return QueryResult(
                success=False,
                error=error_msg
            )

    async def _execute_with_timeout(
        self,
        sql: str,
        timeout: int
    ) -> pd.DataFrame:
        """
        Execute SQL with timeout protection.

        Uses ThreadPoolExecutor to run blocking database operation
        with asyncio timeout wrapper.

        Args:
            sql: SQL query to execute
            timeout: Timeout in seconds

        Returns:
            DataFrame with query results

        Raises:
            asyncio.TimeoutError: If query exceeds timeout
            sqlite3.Error: If database error occurs
        """
        loop = asyncio.get_event_loop()

        # Run blocking database operation in thread pool
        task = loop.run_in_executor(
            self._executor,
            self._execute_query_sync,
            sql
        )

        # Apply timeout
        df = await asyncio.wait_for(task, timeout=timeout)
        return df

    def _execute_query_sync(self, sql: str) -> pd.DataFrame:
        """
        Synchronous query execution (runs in thread pool).

        Args:
            sql: SQL query to execute

        Returns:
            DataFrame with query results

        Raises:
            sqlite3.Error: If database error occurs
        """
        conn = self._get_readonly_connection()
        try:
            df = pd.read_sql_query(sql, conn)
            return df
        finally:
            conn.close()

    def _get_readonly_connection(self) -> sqlite3.Connection:
        """
        Get a read-only SQLite connection.

        Uses URI mode with 'ro' flag to ensure no writes possible.
        This provides additional safety beyond SQL validation.

        Returns:
            Read-only SQLite connection

        Raises:
            sqlite3.Error: If database cannot be opened
        """
        # Use URI mode with read-only flag
        # This prevents any write operations at the database level
        uri = f"file:{self.db_path}?mode=ro"
        conn = sqlite3.connect(uri, uri=True, check_same_thread=False)

        # Set additional safety pragmas
        conn.execute("PRAGMA query_only = ON")  # SQLite 3.8.0+

        return conn

    async def get_schema_info(self) -> Dict[str, List[str]]:
        """
        Get table schemas for context.

        Returns dict mapping table_name -> list of column names.
        Useful for providing context to Claude when generating SQL.

        Returns:
            Dict of table_name -> [column_names]

        Example:
            >>> engine = QueryEngine()
            >>> schema = await engine.get_schema_info()
            >>> print(schema['trades'])
            ['id', 'trade_id', 'exchange', 'account_name', 'timestamp', ...]
        """
        schema = {}

        # Query to get all table names and their columns
        sql = """
            SELECT m.name as table_name, p.name as column_name
            FROM sqlite_master m
            JOIN pragma_table_info(m.name) p
            WHERE m.type = 'table'
            AND m.name NOT LIKE 'sqlite_%'
            ORDER BY m.name, p.cid
        """

        try:
            conn = self._get_readonly_connection()
            try:
                cursor = conn.execute(sql)

                for row in cursor:
                    table_name, column_name = row

                    if table_name not in schema:
                        schema[table_name] = []

                    schema[table_name].append(column_name)

                logger.info(f"Retrieved schema for {len(schema)} tables")
                return schema

            finally:
                conn.close()

        except Exception as e:
            logger.error(f"Failed to get schema info: {e}", exc_info=True)
            return {}

    async def sample_data(
        self,
        table: str,
        limit: int = 5
    ) -> pd.DataFrame:
        """
        Get sample data from a table for context.

        Useful for showing examples to users or providing context to Claude.

        Args:
            table: Table name to sample from
            limit: Number of rows to return (default 5, max 10)

        Returns:
            DataFrame with sample rows

        Example:
            >>> engine = QueryEngine()
            >>> sample = await engine.sample_data('trades', limit=3)
            >>> print(sample)
        """
        # Validate table name
        if table not in self.validator.ALLOWED_TABLES:
            logger.warning(f"Requested sample from invalid table: {table}")
            return pd.DataFrame()

        # Cap limit at 10
        limit = min(limit, 10)

        # Simple SELECT with LIMIT
        sql = f"SELECT * FROM {table} LIMIT {limit}"

        result = await self.execute_sql(sql)

        if result.success:
            return result.data
        else:
            logger.error(f"Failed to get sample data: {result.error}")
            return pd.DataFrame()

    async def get_table_stats(self, table: str) -> Dict[str, Any]:
        """
        Get statistics about a table.

        Args:
            table: Table name

        Returns:
            Dict with stats like row_count, date_range, etc.

        Example:
            >>> engine = QueryEngine()
            >>> stats = await engine.get_table_stats('trades')
            >>> print(f"Trades table has {stats['row_count']} rows")
        """
        if table not in self.validator.ALLOWED_TABLES:
            return {}

        stats = {}

        # Get row count
        count_sql = f"SELECT COUNT(*) as count FROM {table}"
        result = await self.execute_sql(count_sql)

        if result.success and not result.data.empty:
            stats['row_count'] = int(result.data.iloc[0]['count'])

        # For trades table, get additional stats
        if table == 'trades':
            stats_sql = """
                SELECT
                    MIN(timestamp) as earliest_trade,
                    MAX(timestamp) as latest_trade,
                    COUNT(DISTINCT exchange) as exchange_count,
                    COUNT(DISTINCT account_name) as account_count
                FROM trades
            """
            result = await self.execute_sql(stats_sql)

            if result.success and not result.data.empty:
                row = result.data.iloc[0]
                stats['earliest_trade'] = row['earliest_trade']
                stats['latest_trade'] = row['latest_trade']
                stats['exchange_count'] = int(row['exchange_count'])
                stats['account_count'] = int(row['account_count'])

        return stats

    def __del__(self):
        """Cleanup thread pool on deletion."""
        try:
            self._executor.shutdown(wait=False)
        except:
            pass


# =============================================================================
# Helper Functions
# =============================================================================

async def quick_query(sql: str, db_path: str = "data/trade_cache.db") -> QueryResult:
    """
    Quick helper function to execute a SQL query without setting up engine.

    Args:
        sql: SQL SELECT query
        db_path: Path to database file

    Returns:
        QueryResult

    Example:
        >>> result = await quick_query("SELECT COUNT(*) FROM trades")
        >>> if result.success:
        ...     print(result.data)
    """
    engine = QueryEngine(db_path=db_path)
    return await engine.execute_sql(sql)


def validate_sql(sql: str) -> Tuple[bool, str]:
    """
    Quick helper to validate SQL without executing.

    Args:
        sql: SQL query to validate

    Returns:
        Tuple of (is_valid, error_message)

    Example:
        >>> is_valid, error = validate_sql("SELECT * FROM trades")
        >>> assert is_valid
    """
    validator = SQLValidator()
    return validator.validate(sql)
