# Python Executor Quick Reference

## Installation

```bash
pip install pandas numpy aiosqlite
```

## Basic Usage

```python
from src.bot.python_executor import SafePythonExecutor
from src.bot.function_store import FunctionStore

# Initialize
executor = SafePythonExecutor(data_provider)
store = FunctionStore()

# Execute code
result = await executor.execute("result = 1 + 1")

# Save function
await store.save("my_func", "result = 42", "Description", "U123")

# Run saved function
func = await store.get("my_func")
result = await executor.execute(func.code)
```

## Data Loading Functions

```python
# Load trades
df = load_trades()                      # All trades (30 days)
df = load_trades(days=7)                # Last 7 days
df = load_trades(exchange='binance')    # Specific exchange
df = load_trades(asset='BTC')           # Specific asset

# Load balances
balances = load_balances()
# Returns: {'binance': {'BTC': 10.5}, 'kraken': {...}}

# Load snapshots
snapshots = load_snapshots(days=30)
# Returns: [{'timestamp': ..., 'total_usd': ...}, ...]
```

## Available Modules

```python
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import math
import statistics
import json
```

## Common Patterns

### Volume Analysis
```python
df = load_trades(days=7)
result = df.groupby('exchange')['amount'].sum().to_dict()
```

### Balance Totals
```python
balances = load_balances()
result = {
    'btc': sum(b.get('BTC', 0) for b in balances.values()),
    'eth': sum(b.get('ETH', 0) for b in balances.values())
}
```

### Time Series
```python
import pandas as pd

snapshots = load_snapshots(days=30)
df = pd.DataFrame(snapshots)
df['timestamp'] = pd.to_datetime(df['timestamp'])

result = {
    'avg': df['total_usd'].mean(),
    'max': df['total_usd'].max(),
    'min': df['total_usd'].min()
}
```

### Price Statistics
```python
df = load_trades(asset='BTC')
result = {
    'avg_price': df['price'].mean(),
    'min_price': df['price'].min(),
    'max_price': df['price'].max(),
    'total_volume': df['amount'].sum()
}
```

## Slack Commands

```bash
# Execute code
/analyze df = load_trades(); result = df['amount'].sum()

# Save function
/savefunc total_volume | Calculate total volume | df = load_trades(); result = df['amount'].sum()

# Run saved function
/runfunc total_volume

# List functions
/listfuncs

# Search functions
/listfuncs volume

# Delete function
/delfunc old_function
```

## Security - Allowed

- pandas, numpy, datetime, math, statistics
- Basic types: int, float, str, bool, list, dict
- Iteration: range, enumerate, zip, map, filter
- Aggregation: sum, min, max, len
- print() for output

## Security - Blocked

- File I/O: open(), file()
- Network: requests, socket, urllib
- System: os, sys, subprocess
- Code execution: exec(), eval(), compile()
- Introspection: globals(), locals(), getattr()
- Lambda functions
- Async/await in user code

## Error Handling

```python
result = await executor.execute(code)

if result.success:
    print(f"Result: {result.result}")
    print(f"Output: {result.output}")
    print(f"Time: {result.execution_time_ms}ms")
else:
    print(f"Error: {result.error}")
```

## Validation

```python
from src.bot.python_executor import CodeValidator

validator = CodeValidator()
is_valid, error = validator.validate(code)

if not is_valid:
    print(f"Validation error: {error}")
```

## Function Store Operations

```python
# Save
await store.save(name, code, description, user_id)

# Get
func = await store.get(name)

# List all
functions = await store.list_all()

# Search
results = await store.search("volume")

# Delete
await store.delete(name)

# Update usage
await store.update_usage(name)

# Get stats
stats = await store.get_stats()
# Returns: {total_functions, total_uses, top_functions}

# Rename
await store.rename("old_name", "new_name")
```

## Tips

1. **Always set result**: `result = your_value`
2. **Use caching**: `execute(code, use_cache=True)` for repeated queries
3. **Filter data early**: Use parameters in `load_trades(days=7)` instead of filtering DataFrame
4. **Check timeout**: Complex operations must complete in 30s
5. **Test validation**: Use `/analyze` to test code before saving with `/savefunc`
6. **Use print()**: Debug with print statements (captured in `result.output`)

## Common Errors

### "result variable not set"
```python
# Wrong
df = load_trades()
total = df['amount'].sum()

# Correct
df = load_trades()
result = df['amount'].sum()
```

### "Validation error: Import not allowed"
```python
# Wrong
import requests

# Correct
import pandas as pd
```

### "Execution timed out"
```python
# Reduce data size
df = load_trades(days=7)  # Instead of days=365
```

## Testing

```bash
# Run tests
pytest tests/test_python_executor.py -v

# Run examples
python3 examples/python_executor_examples.py
```

## File Locations

- Implementation: `src/bot/python_executor.py`
- Storage: `src/bot/function_store.py`
- Tests: `tests/test_python_executor.py`
- Examples: `examples/python_executor_examples.py`
- Docs: `docs/PYTHON_EXECUTOR.md`
- Integration: `docs/PYTHON_EXECUTOR_INTEGRATION.md`
