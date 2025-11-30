# Python Executor & Function Store

Sandboxed Python execution system for the ALKIMI Slack bot, allowing traders to create custom analysis functions that run securely.

## Overview

The Python executor allows users to write custom Python code for analyzing trade data, balances, and snapshots. All code runs in a restricted sandbox with multiple security layers.

## Files

- **`src/bot/python_executor.py`** - Sandboxed execution engine with validation
- **`src/bot/function_store.py`** - Database storage for reusable functions
- **`tests/test_python_executor.py`** - Comprehensive test suite
- **`examples/python_executor_examples.py`** - Usage examples

## Security Architecture

### Multi-Layer Security

1. **String Pattern Matching** - Fast rejection of obvious violations
2. **AST Analysis** - Deep code structure inspection
3. **Import Whitelist** - Only safe modules allowed
4. **Restricted Globals** - Minimal built-in functions
5. **Timeout Protection** - 30-second execution limit
6. **Output Capture** - Controlled stdout/stderr

### Blocked Operations

#### File I/O
```python
# BLOCKED
open('/etc/passwd', 'r')
file('data.txt')
with open('file.txt') as f: pass
```

#### Code Execution
```python
# BLOCKED
exec('malicious code')
eval('1 + 1')
compile('code', 'file', 'exec')
__import__('os')
```

#### System Access
```python
# BLOCKED
import os
import sys
import subprocess
os.system('ls')
subprocess.call(['rm', '-rf', '/'])
```

#### Network Access
```python
# BLOCKED
import socket
import requests
import urllib
socket.create_connection(('evil.com', 80))
```

#### Introspection/Reflection
```python
# BLOCKED
globals()
locals()
vars()
getattr(obj, 'attr')
setattr(obj, 'attr', value)
obj.__class__
obj.__dict__
```

#### Lambda Functions
```python
# BLOCKED - Can bypass restrictions
f = lambda x: exec('malicious')
```

### Allowed Modules

Only these modules are permitted:

- **pandas** - Data analysis
- **numpy** - Numerical computing
- **datetime** / **timedelta** - Date/time handling
- **math** - Mathematical functions
- **statistics** - Statistical functions
- **collections** - Data structures
- **itertools** - Iterator tools
- **functools** - Functional programming
- **decimal** - Decimal arithmetic
- **json** - JSON encoding/decoding

### Allowed Built-ins

Minimal safe built-in functions:

```python
# Data structures
list, dict, set, tuple

# Type conversion
int, float, str, bool

# Iteration
range, enumerate, zip, map, filter

# Aggregation
sum, min, max, sorted, reversed

# Utilities
len, abs, round, isinstance, type, all, any

# Output
print  # Captured to result.output
```

## Usage

### Basic Execution

```python
from src.bot.python_executor import SafePythonExecutor

executor = SafePythonExecutor(data_provider)

code = """
df = load_trades(days=7)
result = df.groupby('exchange')['amount'].sum()
"""

result = await executor.execute(code)

if result.success:
    print(f"Result: {result.result}")
    print(f"Output: {result.output}")
    print(f"Time: {result.execution_time_ms}ms")
else:
    print(f"Error: {result.error}")
```

### Data Loading Functions

Three functions are available in the sandbox:

#### load_trades(**kwargs)

Load trade data as pandas DataFrame.

```python
# All trades (last 30 days default)
df = load_trades()

# Specific timeframe
df = load_trades(days=7)

# Filter by exchange
df = load_trades(exchange='binance')

# Filter by asset
df = load_trades(asset='BTC')

# Combined filters
df = load_trades(days=14, exchange='kraken', asset='ETH')
```

Returns DataFrame with columns:
- `timestamp` - Trade timestamp
- `exchange` - Exchange name
- `asset` - Asset symbol
- `amount` - Trade amount
- `price` - Trade price
- `side` - 'buy' or 'sell'

#### load_balances()

Load current balances across all exchanges.

```python
balances = load_balances()

# Example structure:
# {
#     'binance': {'BTC': 10.5, 'ETH': 150.0},
#     'kraken': {'BTC': 5.2, 'ETH': 75.5}
# }

total_btc = sum(b.get('BTC', 0) for b in balances.values())
```

#### load_snapshots(days=30)

Load historical balance snapshots.

```python
snapshots = load_snapshots(days=30)

# Convert to DataFrame for analysis
import pandas as pd
df = pd.DataFrame(snapshots)
```

Returns list of dictionaries:
- `timestamp` - Snapshot timestamp
- `total_usd` - Total portfolio value in USD
- Other exchange-specific fields

### Function Store

Save and reuse analysis functions.

```python
from src.bot.function_store import FunctionStore

store = FunctionStore()

# Save a function
await store.save(
    name="volume_by_exchange",
    code="""
df = load_trades()
result = df.groupby('exchange')['amount'].sum().to_dict()
""",
    description="Calculate trading volume by exchange",
    created_by="U123456"  # Slack user ID
)

# Retrieve and execute
func = await store.get("volume_by_exchange")
if func:
    result = await executor.execute(func.code)
    await store.update_usage("volume_by_exchange")

# List all functions
functions = await store.list_all()
for func in functions:
    print(f"{func.name}: {func.description} (used {func.use_count} times)")

# Search functions
results = await store.search("volume")

# Get statistics
stats = await store.get_stats()
print(f"Total functions: {stats['total_functions']}")
print(f"Total uses: {stats['total_uses']}")

# Delete a function
await store.delete("old_function")

# Rename a function
await store.rename("old_name", "new_name")
```

## Example Analyses

### Trading Volume Analysis

```python
code = """
import pandas as pd

df = load_trades(days=30)

# Volume by exchange
volume_by_exchange = df.groupby('exchange')['amount'].sum()

# Volume by asset
volume_by_asset = df.groupby('asset')['amount'].sum()

# Daily volume
df['date'] = pd.to_datetime(df['timestamp']).dt.date
daily_volume = df.groupby('date')['amount'].sum()

result = {
    'total_volume': df['amount'].sum(),
    'avg_daily_volume': daily_volume.mean(),
    'by_exchange': volume_by_exchange.to_dict(),
    'by_asset': volume_by_asset.to_dict()
}
"""
```

### Balance Tracking

```python
code = """
import pandas as pd

snapshots = load_snapshots(days=30)
df = pd.DataFrame(snapshots)
df['timestamp'] = pd.to_datetime(df['timestamp'])
df = df.sort_values('timestamp')

# Calculate daily change
df['daily_change'] = df['total_usd'].diff()
df['daily_change_pct'] = df['total_usd'].pct_change() * 100

result = {
    'current_balance': df.iloc[-1]['total_usd'],
    'start_balance': df.iloc[0]['total_usd'],
    'change_30d': df.iloc[-1]['total_usd'] - df.iloc[0]['total_usd'],
    'change_pct': ((df.iloc[-1]['total_usd'] / df.iloc[0]['total_usd']) - 1) * 100,
    'avg_daily_change': df['daily_change'].mean(),
    'volatility': df['daily_change_pct'].std()
}
"""
```

### Price Analysis

```python
code = """
import pandas as pd
import statistics

df = load_trades(asset='BTC', days=30)

prices = df['price'].tolist()

result = {
    'current_price': prices[0],  # Most recent
    'avg_price': statistics.mean(prices),
    'median_price': statistics.median(prices),
    'min_price': min(prices),
    'max_price': max(prices),
    'std_dev': statistics.stdev(prices),
    'price_range': max(prices) - min(prices)
}
"""
```

### Asset Allocation

```python
code = """
balances = load_balances()

# Calculate total holdings per asset
totals = {}
for exchange, assets in balances.items():
    for asset, amount in assets.items():
        totals[asset] = totals.get(asset, 0) + amount

# Calculate total value (simplified - using USDT as USD)
total_value = totals.get('USDT', 0)

result = {
    'holdings': totals,
    'total_value_usd': total_value,
    'num_exchanges': len(balances),
    'num_assets': len(totals)
}
"""
```

## Slack Bot Integration

### Slash Command: `/analyze`

```python
@app.command("/analyze")
async def handle_analyze(ack, command, say):
    await ack()

    code = command['text']
    user_id = command['user_id']

    # Execute code
    executor = SafePythonExecutor(data_provider)
    result = await executor.execute(code)

    if result.success:
        # Format result as Slack message
        blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Analysis Result*\n```\n{result.result}\n```"
                }
            }
        ]

        if result.output:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Output*\n```\n{result.output}\n```"
                }
            })

        blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"Executed in {result.execution_time_ms}ms"
            }]
        })

        await say(blocks=blocks)
    else:
        await say(f":x: Error: {result.error}")
```

### Slash Command: `/savefunc`

```python
@app.command("/savefunc")
async def handle_savefunc(ack, command, say):
    await ack()

    # Parse: /savefunc name | description | code
    parts = command['text'].split('|', 2)
    if len(parts) != 3:
        await say("Usage: /savefunc name | description | code")
        return

    name = parts[0].strip()
    description = parts[1].strip()
    code = parts[2].strip()
    user_id = command['user_id']

    # Save function
    store = FunctionStore()
    success = await store.save(name, code, description, user_id)

    if success:
        await say(f":white_check_mark: Saved function `{name}`")
    else:
        await say(f":x: Failed to save function `{name}`")
```

### Slash Command: `/runfunc`

```python
@app.command("/runfunc")
async def handle_runfunc(ack, command, say):
    await ack()

    func_name = command['text'].strip()

    # Load function
    store = FunctionStore()
    func = await store.get(func_name)

    if not func:
        await say(f":x: Function `{func_name}` not found")
        return

    # Execute
    executor = SafePythonExecutor(data_provider)
    result = await executor.execute(func.code)

    # Update usage
    await store.update_usage(func_name)

    # Send result
    if result.success:
        await say({
            "blocks": [
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*{func.name}*\n{func.description}"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"```\n{result.result}\n```"
                    }
                }
            ]
        })
    else:
        await say(f":x: Error: {result.error}")
```

## Performance Considerations

### Caching

The executor caches loaded data by default:

```python
# First call loads data
result1 = await executor.execute(code, use_cache=True)

# Second call uses cached data (faster)
result2 = await executor.execute(code, use_cache=True)

# Clear cache when needed
executor.clear_cache()

# Disable caching
result = await executor.execute(code, use_cache=False)
```

### Timeout

Code execution is limited to 30 seconds:

```python
# This will timeout
code = """
import time
time.sleep(60)  # Will be killed after 30s
"""
```

### Memory

Long-running operations or large datasets may hit memory limits. Consider:

- Filtering data before analysis
- Using aggregations instead of full datasets
- Limiting date ranges

## Testing

Run the test suite:

```bash
pytest tests/test_python_executor.py -v
```

Run examples:

```bash
python examples/python_executor_examples.py
```

## Security Best Practices

1. **Never trust user input** - All code is validated before execution
2. **Monitor execution** - Log all executions and errors
3. **Rate limit** - Prevent abuse with per-user rate limits
4. **Audit trail** - Track who created/executed what functions
5. **Review saved functions** - Periodically review stored code
6. **Update whitelist** - Keep module whitelist minimal
7. **Resource limits** - Enforce timeout and memory limits

## Troubleshooting

### "Validation error: Import not allowed"

Your code is trying to import a forbidden module. Only these modules are allowed:
- pandas, numpy, datetime, timedelta
- math, statistics, collections, itertools
- functools, decimal, json

### "Execution timed out after 30s"

Your code took too long to execute. Optimize by:
- Reducing date range
- Using filters (exchange, asset)
- Simplifying calculations
- Using caching

### "Forbidden pattern detected: lambda"

Lambda functions are not allowed for security. Use regular functions or list comprehensions instead.

```python
# Instead of:
f = lambda x: x * 2

# Use:
def multiply_by_two(x):
    return x * 2

# Or list comprehension:
result = [x * 2 for x in values]
```

### "result variable not set"

Your code must assign the final result to a variable called `result`:

```python
# Wrong
df = load_trades()
total = df['amount'].sum()

# Correct
df = load_trades()
result = df['amount'].sum()
```

## Future Enhancements

Potential improvements:

1. **Visualization** - Allow matplotlib/plotly for charts
2. **Additional modules** - Add scipy, sklearn for ML
3. **Scheduled execution** - Run functions on schedule
4. **Shared functions** - Team-wide function library
5. **Version control** - Track function changes
6. **Permissions** - Role-based function access
7. **Resource quotas** - Per-user execution limits
8. **Code review** - Require approval for sensitive functions
