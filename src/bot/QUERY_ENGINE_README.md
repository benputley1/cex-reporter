# Query Engine Documentation

## Overview

The `query_engine.py` module provides **safe SQL generation and execution** for the ALKIMI Slack bot. It enables users to query trade data using either direct SQL or natural language, with comprehensive security measures to prevent data corruption or unauthorized access.

## Key Features

### Security First
- **Read-only database access** - Uses SQLite URI mode with `mode=ro` flag
- **SQL validation** - Blocks DROP, DELETE, UPDATE, INSERT, ALTER, CREATE, etc.
- **Table whitelist** - Only allows queries on approved tables
- **Row limit enforcement** - Automatically adds/enforces LIMIT 100 on all queries
- **Query timeout** - Kills queries that run longer than 5 seconds
- **Multiple statement blocking** - Prevents SQL injection via semicolon chaining

### Natural Language Support
- Convert plain English to SQL using Claude API
- Automatically validates generated SQL before execution
- Provides schema context to improve SQL quality

### Developer-Friendly
- Returns results as pandas DataFrames
- Detailed error messages for debugging
- Query timing metrics
- Schema introspection utilities

## Quick Start

### Basic Usage

```python
from src.bot.query_engine import QueryEngine

# Initialize engine
engine = QueryEngine(db_path="data/trade_cache.db")

# Execute SQL directly
result = await engine.execute_sql("""
    SELECT exchange, COUNT(*) as trades
    FROM trades
    GROUP BY exchange
    LIMIT 10
""")

if result.success:
    print(f"Found {result.row_count} rows in {result.execution_time_ms}ms")
    print(result.data)
else:
    print(f"Error: {result.error}")
```

### Natural Language Queries

```python
from src.bot.prompts import ClaudeClient
from src.bot.query_engine import QueryEngine

# Initialize with Claude client for NL support
claude = ClaudeClient(api_key="sk-ant-...")
engine = QueryEngine(
    db_path="data/trade_cache.db",
    claude_client=claude
)

# Query in plain English
result = await engine.generate_and_execute(
    "Show me the top 10 largest trades by value"
)

if result.success:
    print(f"Generated SQL: {result.sql}")
    print(result.data)
```

## API Reference

### Classes

#### `QueryResult`

Dataclass containing query execution results:

```python
@dataclass
class QueryResult:
    success: bool                      # Whether query succeeded
    data: Optional[pd.DataFrame]       # Results as DataFrame (if success)
    row_count: int                     # Number of rows returned
    execution_time_ms: int             # Execution time in milliseconds
    error: Optional[str]               # Error message (if failed)
    sql: Optional[str]                 # Actual SQL executed
```

#### `SQLValidator`

Validates SQL queries for safety:

**Class Attributes:**
- `FORBIDDEN_KEYWORDS` - List of dangerous SQL keywords (DROP, DELETE, etc.)
- `ALLOWED_TABLES` - Set of tables users can query
- `ALLOWED_FUNCTIONS` - List of safe SQLite functions
- `MAX_ROWS` - Maximum rows per query (default: 100)

**Methods:**

```python
def validate(self, sql: str) -> Tuple[bool, str]:
    """
    Validate SQL query is safe to execute.

    Returns:
        (is_valid, error_message)

    Example:
        >>> validator = SQLValidator()
        >>> is_valid, error = validator.validate("SELECT * FROM trades")
        >>> assert is_valid
    """
```

```python
def sanitize(self, sql: str) -> str:
    """
    Sanitize SQL by adding/enforcing LIMIT clause.

    Example:
        >>> validator = SQLValidator()
        >>> sql = validator.sanitize("SELECT * FROM trades")
        >>> assert "LIMIT 100" in sql
    """
```

```python
def extract_tables(self, sql: str) -> List[str]:
    """
    Extract table names from SQL query.

    Returns:
        List of table names found in query
    """
```

#### `QueryEngine`

Main query execution engine:

**Constructor:**

```python
def __init__(
    self,
    db_path: str = "data/trade_cache.db",
    claude_client = None
):
    """
    Initialize query engine.

    Args:
        db_path: Path to SQLite database
        claude_client: Optional ClaudeClient for NL queries
    """
```

**Methods:**

```python
async def execute_sql(self, sql: str) -> QueryResult:
    """
    Execute a validated SQL query.

    Steps:
        1. Validates SQL for safety
        2. Sanitizes (adds LIMIT if needed)
        3. Executes with read-only connection
        4. Applies timeout protection
        5. Returns results as DataFrame

    Example:
        >>> result = await engine.execute_sql("SELECT * FROM trades LIMIT 5")
        >>> if result.success:
        ...     print(result.data)
    """
```

```python
async def generate_and_execute(self, natural_query: str) -> QueryResult:
    """
    Generate SQL from natural language and execute it.

    Args:
        natural_query: Plain English query

    Returns:
        QueryResult with data or error

    Example:
        >>> result = await engine.generate_and_execute(
        ...     "What were the top 5 largest trades?"
        ... )
        >>> print(f"Generated SQL: {result.sql}")
    """
```

```python
async def get_schema_info(self) -> Dict[str, List[str]]:
    """
    Get table schemas for context.

    Returns:
        Dict mapping table_name -> [column_names]

    Example:
        >>> schema = await engine.get_schema_info()
        >>> print(schema['trades'])
        ['id', 'trade_id', 'exchange', ...]
    """
```

```python
async def sample_data(self, table: str, limit: int = 5) -> pd.DataFrame:
    """
    Get sample data from a table.

    Args:
        table: Table name (must be in whitelist)
        limit: Number of rows (max 10)

    Returns:
        DataFrame with sample rows
    """
```

```python
async def get_table_stats(self, table: str) -> Dict[str, Any]:
    """
    Get statistics about a table.

    Returns:
        Dict with stats like row_count, date_range, etc.

    Example:
        >>> stats = await engine.get_table_stats('trades')
        >>> print(f"Total trades: {stats['row_count']}")
    """
```

### Helper Functions

```python
async def quick_query(sql: str, db_path: str = "data/trade_cache.db") -> QueryResult:
    """
    Quick helper to execute SQL without setting up engine.

    Example:
        >>> from src.bot.query_engine import quick_query
        >>> result = await quick_query("SELECT COUNT(*) FROM trades")
    """
```

```python
def validate_sql(sql: str) -> Tuple[bool, str]:
    """
    Quick helper to validate SQL without executing.

    Example:
        >>> from src.bot.query_engine import validate_sql
        >>> is_valid, error = validate_sql("SELECT * FROM trades")
    """
```

## Security Features

### 1. Read-Only Database Access

The engine uses SQLite's URI mode with the `mode=ro` flag:

```python
uri = f"file:{self.db_path}?mode=ro"
conn = sqlite3.connect(uri, uri=True)
```

This provides defense-in-depth - even if SQL validation is bypassed, the database connection itself prevents writes.

### 2. SQL Validation

All queries are validated before execution:

```python
# Forbidden keywords
FORBIDDEN_KEYWORDS = [
    'DROP', 'DELETE', 'UPDATE', 'INSERT', 'ALTER', 'CREATE',
    'TRUNCATE', 'REPLACE', 'ATTACH', 'DETACH', 'PRAGMA',
    'VACUUM', 'REINDEX', 'ANALYZE', 'EXPLAIN'
]

# Table whitelist
ALLOWED_TABLES = {
    'trades', 'query_history', 'saved_functions',
    'pnl_config', 'otc_transactions'
}
```

### 3. Row Limit Enforcement

All queries are limited to 100 rows maximum:

```python
# Query without LIMIT
sql = "SELECT * FROM trades"
# Becomes: "SELECT * FROM trades LIMIT 100"

# Query with excessive LIMIT
sql = "SELECT * FROM trades LIMIT 500"
# Becomes: "SELECT * FROM trades LIMIT 100"
```

### 4. Timeout Protection

Queries are killed after 5 seconds:

```python
# Uses asyncio.wait_for() with timeout
df = await asyncio.wait_for(task, timeout=5)
```

### 5. Multiple Statement Blocking

Prevents SQL injection via semicolon chaining:

```python
# This is rejected:
"SELECT * FROM trades; DROP TABLE trades"
# Error: Query contains multiple statements
```

## Database Schema

The engine can query these tables:

### `trades`
- `id` - Integer primary key
- `trade_id` - Exchange trade ID
- `exchange` - Exchange name (mexc, kraken, kucoin, gateio, cetus, etc.)
- `account_name` - Account identifier (MM1, MM2, MM3, TREASURY)
- `timestamp` - Trade timestamp (ISO format)
- `symbol` - Trading pair symbol (ALKIMI)
- `side` - Trade side (buy or sell)
- `amount` - Quantity traded
- `price` - USD price per unit
- `fee` - Trading fee in USD
- `fee_currency` - Fee currency
- `cached_at` - When trade was cached

### Other Tables
- `query_history` - Slack bot query history
- `saved_functions` - User-defined Python functions
- `pnl_config` - P&L calculation configuration
- `otc_transactions` - OTC trade records

## Common Query Patterns

### Trading Volume by Exchange

```sql
SELECT
    exchange,
    COUNT(*) as trade_count,
    SUM(amount * price) as total_volume_usd,
    AVG(amount * price) as avg_trade_size_usd
FROM trades
GROUP BY exchange
ORDER BY total_volume_usd DESC
LIMIT 10
```

### Recent Large Trades

```sql
SELECT
    timestamp,
    exchange,
    side,
    amount,
    price,
    (amount * price) as value_usd
FROM trades
WHERE (amount * price) > 1000
ORDER BY timestamp DESC
LIMIT 20
```

### Daily Trading Summary

```sql
SELECT
    date(timestamp) as trade_date,
    COUNT(*) as trades,
    SUM(CASE WHEN side='buy' THEN amount*price ELSE 0 END) as buy_volume,
    SUM(CASE WHEN side='sell' THEN amount*price ELSE 0 END) as sell_volume,
    SUM(amount * price) as total_volume
FROM trades
WHERE timestamp >= datetime('now', '-7 days')
GROUP BY date(timestamp)
ORDER BY trade_date DESC
LIMIT 7
```

### Top Trading Accounts

```sql
SELECT
    account_name,
    COUNT(*) as trade_count,
    SUM(amount * price) as total_volume_usd,
    MIN(timestamp) as first_trade,
    MAX(timestamp) as last_trade
FROM trades
GROUP BY account_name
ORDER BY total_volume_usd DESC
LIMIT 10
```

## Integration with Slack Bot

### Pattern 1: Direct SQL Execution

```python
# In slack_bot.py
from src.bot.query_engine import QueryEngine

engine = QueryEngine(db_path="data/trade_cache.db")

@app.event("message")
async def handle_message(event, say):
    query = event['text']

    # If user provides SQL directly
    if query.strip().upper().startswith('SELECT'):
        result = await engine.execute_sql(query)

        if result.success:
            # Format DataFrame for Slack
            response = f"```\n{result.data.to_string()}\n```"
            response += f"\n_({result.row_count} rows in {result.execution_time_ms}ms)_"
            await say(response)
        else:
            await say(f"❌ Error: {result.error}")
```

### Pattern 2: Natural Language Queries

```python
# With Claude integration
from src.bot.prompts import ClaudeClient
from src.bot.query_engine import QueryEngine

claude = ClaudeClient(api_key=os.getenv('ANTHROPIC_API_KEY'))
engine = QueryEngine(claude_client=claude)

@app.event("message")
async def handle_message(event, say):
    query = event['text']

    # Generate and execute SQL from natural language
    result = await engine.generate_and_execute(query)

    if result.success:
        response = f"*SQL Generated:*\n```sql\n{result.sql}\n```\n\n"
        response += f"*Results:*\n```\n{result.data.to_string()}\n```"
        await say(response)
    else:
        await say(f"❌ {result.error}")
```

### Pattern 3: Schema Help

```python
# Provide schema info to users
@app.command("/schema")
async def schema_command(ack, command, respond):
    await ack()

    schema = await engine.get_schema_info()

    response = "*Available Tables:*\n\n"
    for table, columns in schema.items():
        response += f"*{table}*\n"
        response += f"  Columns: {', '.join(columns)}\n\n"

    await respond(response)
```

## Error Handling

Always check `result.success` before accessing data:

```python
result = await engine.execute_sql(sql)

if result.success:
    # Safe to access result.data
    print(result.data)
    print(f"Query returned {result.row_count} rows")
else:
    # Handle error
    print(f"Query failed: {result.error}")

    # Common error types:
    # - "Invalid SQL: Query must start with SELECT..."
    # - "Invalid SQL: Query contains forbidden keyword: DROP"
    # - "Invalid SQL: Query references invalid table(s): ..."
    # - "Query exceeded timeout of 5s"
    # - "Database error: ..."
```

## Performance Considerations

### Query Timeout

- Default timeout: 5 seconds
- Adjustable via `engine.query_timeout`
- Complex aggregations may need longer timeout
- Use appropriate indexes for large queries

### Row Limits

- Default max rows: 100
- Adjustable via `SQLValidator.MAX_ROWS`
- Pagination recommended for large result sets
- Consider aggregate queries instead of raw data

### Connection Pooling

- Engine uses ThreadPoolExecutor for async operations
- Read-only connections are lightweight
- Each query gets fresh connection (no pooling needed)

## Testing

Run the test suite:

```bash
python3 test_query_engine.py
```

Run usage examples:

```bash
python3 example_query_engine_usage.py
```

## Troubleshooting

### "No module named 'anthropic'"

Natural language queries require the Claude API client:

```bash
pip install anthropic
```

### "Database is locked"

The database is read-only. If you need to write data, use the appropriate service (e.g., data_provider.py for caching trades).

### "Query exceeded timeout"

Optimize your query:
- Add WHERE clauses to filter data
- Use indexes effectively
- Reduce GROUP BY complexity
- Consider pre-aggregating data

### "Query references invalid table"

Check the `ALLOWED_TABLES` whitelist. If you need access to a new table, add it to `SQLValidator.ALLOWED_TABLES`.

## Future Enhancements

Potential improvements:

1. **Query caching** - Cache frequent queries for faster response
2. **Query history** - Track all queries for analytics
3. **Cost estimation** - Estimate query cost before execution
4. **Result pagination** - Support for large result sets
5. **Saved queries** - Allow users to save/name common queries
6. **Query templates** - Pre-built queries for common tasks
7. **Multi-table joins** - Better support for complex joins
8. **Subquery support** - Allow controlled subqueries

## License

Part of the ALKIMI CEX Reporter project.
