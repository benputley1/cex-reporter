# Query Engine - Quick Start Guide

## 5-Minute Quick Start

### Import and Initialize

```python
from src.bot.query_engine import QueryEngine

# Basic usage (SQL only)
engine = QueryEngine(db_path="data/trade_cache.db")

# With natural language support
from src.bot.prompts import ClaudeClient
claude = ClaudeClient(api_key=os.getenv('ANTHROPIC_API_KEY'))
engine = QueryEngine(db_path="data/trade_cache.db", claude_client=claude)
```

### Execute SQL Query

```python
result = await engine.execute_sql("""
    SELECT exchange, COUNT(*) as trades, SUM(amount * price) as volume
    FROM trades
    GROUP BY exchange
    ORDER BY volume DESC
    LIMIT 10
""")

if result.success:
    print(result.data)  # pandas DataFrame
    print(f"{result.row_count} rows in {result.execution_time_ms}ms")
else:
    print(f"Error: {result.error}")
```

### Natural Language Query

```python
result = await engine.generate_and_execute(
    "Show me the top 10 largest trades by value"
)

if result.success:
    print(f"Generated SQL: {result.sql}")
    print(result.data)
```

### Get Schema Info

```python
# All tables and columns
schema = await engine.get_schema_info()
for table, columns in schema.items():
    print(f"{table}: {columns}")

# Sample data
sample = await engine.sample_data('trades', limit=5)
print(sample)

# Table statistics
stats = await engine.get_table_stats('trades')
print(stats)  # {'row_count': 3970, 'earliest_trade': '...', ...}
```

## Common Queries

### Recent Trades

```python
result = await engine.execute_sql("""
    SELECT timestamp, exchange, side, amount, price, (amount * price) as value
    FROM trades
    ORDER BY timestamp DESC
    LIMIT 20
""")
```

### Volume by Exchange

```python
result = await engine.execute_sql("""
    SELECT
        exchange,
        COUNT(*) as trades,
        SUM(amount * price) as volume,
        AVG(amount * price) as avg_trade_size
    FROM trades
    GROUP BY exchange
    ORDER BY volume DESC
""")
```

### Trades Above Threshold

```python
result = await engine.execute_sql("""
    SELECT timestamp, exchange, amount, price, (amount * price) as value
    FROM trades
    WHERE (amount * price) > 1000
    ORDER BY value DESC
    LIMIT 50
""")
```

### Daily Summary

```python
result = await engine.execute_sql("""
    SELECT
        date(timestamp) as day,
        COUNT(*) as trades,
        SUM(CASE WHEN side='buy' THEN amount*price ELSE 0 END) as buy_volume,
        SUM(CASE WHEN side='sell' THEN amount*price ELSE 0 END) as sell_volume
    FROM trades
    WHERE timestamp >= datetime('now', '-7 days')
    GROUP BY day
    ORDER BY day DESC
""")
```

## Error Handling

Always check `result.success`:

```python
result = await engine.execute_sql(your_sql)

if result.success:
    # Safe to use result.data
    df = result.data
    print(f"Got {result.row_count} rows")
else:
    # Handle error
    print(f"Query failed: {result.error}")
    # Common errors:
    # - "Invalid SQL: Query must start with SELECT"
    # - "Invalid SQL: Query contains forbidden keyword: DROP"
    # - "Invalid SQL: Query references invalid table(s): ..."
    # - "Query exceeded timeout of 5s"
```

## Security Features

What's automatically protected:

1. Read-only database access (cannot modify data)
2. SQL keyword blacklist (no DROP, DELETE, UPDATE, etc.)
3. Table whitelist (only approved tables: trades, query_history, saved_functions, pnl_config, otc_transactions)
4. Row limit enforcement (max 100 rows, auto-added if missing)
5. Query timeout (5 seconds maximum)
6. Multiple statement blocking (no SQL injection)

## Available Tables

### trades
- `id`, `trade_id`, `exchange`, `account_name`, `timestamp`
- `symbol`, `side`, `amount`, `price`, `fee`, `fee_currency`, `cached_at`

### Other tables
- `query_history` - Bot query log
- `saved_functions` - User Python functions
- `pnl_config` - P&L settings
- `otc_transactions` - OTC trades

## Helper Functions

### Quick Query

```python
from src.bot.query_engine import quick_query

# One-liner for simple queries
result = await quick_query("SELECT COUNT(*) FROM trades")
```

### Validate SQL

```python
from src.bot.query_engine import validate_sql

# Check if SQL is valid without executing
is_valid, error = validate_sql("SELECT * FROM trades LIMIT 10")
if not is_valid:
    print(f"Invalid SQL: {error}")
```

## Performance Tips

- Add WHERE clauses to filter data
- Use indexes (timestamp, exchange, account_name are indexed)
- Aggregate when possible instead of returning raw data
- Keep LIMIT reasonable (default max is 100)

## Troubleshooting

**"No module named 'anthropic'"**
- Natural language requires: `pip install anthropic`
- Or use direct SQL without NL support

**"Database is locked"**
- Database is read-only by design
- Use data_provider.py to write/cache data

**"Query exceeded timeout"**
- Optimize your query (add WHERE, reduce GROUP BY complexity)
- Query is too expensive (check EXPLAIN QUERY PLAN)

**"Query references invalid table"**
- Table not in whitelist
- Check ALLOWED_TABLES in SQLValidator

## Full Documentation

See `/Users/ben/Desktop/cex-reporter/src/bot/QUERY_ENGINE_README.md` for complete API reference.

## Examples

Run examples:
```bash
python3 example_query_engine_usage.py
python3 test_query_engine.py
```

## Key Files

- `/Users/ben/Desktop/cex-reporter/src/bot/query_engine.py` - Main module
- `/Users/ben/Desktop/cex-reporter/src/bot/QUERY_ENGINE_README.md` - Full docs
- `/Users/ben/Desktop/cex-reporter/example_query_engine_usage.py` - Examples
- `/Users/ben/Desktop/cex-reporter/test_query_engine.py` - Tests
