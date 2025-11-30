# DataProvider API Documentation

The `DataProvider` class is a unified data access layer for the ALKIMI Slack bot, consolidating access to trade data, balance snapshots, DEX trades, and market prices.

## Overview

The DataProvider provides a clean async interface to:
- Query trade history from SQLite cache
- Access daily balance snapshots
- Fetch DEX trades from Sui blockchain
- Get current market prices from CoinGecko
- Store and retrieve analytics metadata (queries, functions, OTC trades)

## Initialization

```python
from src.bot.data_provider import DataProvider

# Basic initialization
provider = DataProvider(
    db_path="data/trade_cache.db",
    snapshots_dir="data/snapshots"
)

# With Sui DEX support
sui_config = {
    'token_contract': '0x...',
    'rpc_url': 'https://fullnode.mainnet.sui.io',
    'wallets': [
        {'address': '0x...', 'name': 'TREASURY'},
        {'address': '0x...', 'name': 'MM1'}
    ]
}

provider = DataProvider(
    db_path="data/trade_cache.db",
    snapshots_dir="data/snapshots",
    sui_config=sui_config
)

# Initialize async components
await provider.initialize()
```

## Core Methods

### Trade Data

#### `get_trades_df()`
Get trades as a pandas DataFrame with optional filtering.

```python
# Get all trades from last 7 days
since = datetime.now() - timedelta(days=7)
df = await provider.get_trades_df(since=since)

# Filter by exchange and account
df = await provider.get_trades_df(
    since=since,
    until=datetime.now(),
    exchange='mexc',
    account='MM1'
)

# DataFrame columns: timestamp, exchange, account_name, symbol,
#                    side, amount, price, fee, fee_currency, trade_id
```

#### `get_trade_summary()`
Get aggregated trade statistics.

```python
summary = await provider.get_trade_summary(since=since, until=until)

# Returns:
{
    'total_volume': 125000.50,
    'trade_count': 342,
    'buy_volume': 65000.25,
    'sell_volume': 60000.25,
    'buy_count': 178,
    'sell_count': 164,
    'avg_price': 0.0265,
    'min_price': 0.0245,
    'max_price': 0.0285,
    'total_fees': 125.50,
    'by_exchange': {
        'mexc': {'trade_count': 200, 'volume': 75000.0, ...},
        'kucoin': {'trade_count': 142, 'volume': 50000.5, ...}
    },
    'by_account': {...},
    'date_range': {'start': '2025-11-23T...', 'end': '2025-11-30T...'}
}
```

### Balance Data

#### `get_balances()`
Get current balances from the latest snapshot.

```python
balances = await provider.get_balances()

# Returns: {exchange_account: {asset: balance}}
{
    'mexc_mm1': {'USDT': 10000.0, 'ALKIMI': 50000.0},
    'kucoin_tm1': {'USDT': 5000.0, 'ALKIMI': 25000.0},
    'total': {'USDT': 15000.0, 'ALKIMI': 75000.0}
}
```

#### `get_snapshots()`
Get historical daily snapshots.

```python
snapshots = await provider.get_snapshots(days=30)

# Returns list of snapshot dicts
[
    {
        'date': '2025-11-01',
        'timestamp': '2025-11-01T00:00:00',
        'balances': {'USDT': 10000.0, 'ALKIMI': 50000.0}
    },
    ...
]
```

### DEX Data

#### `get_dex_trades()`
Get DEX trades from Sui blockchain.

```python
# Get DEX trades from last 7 days
dex_df = await provider.get_dex_trades(since=datetime.now() - timedelta(days=7))

# DataFrame columns: timestamp, exchange, symbol, side,
#                    amount, price, fee, fee_currency, trade_id
```

### Market Data

#### `get_current_price()`
Get current ALKIMI price from CoinGecko.

```python
price = await provider.get_current_price()
# Returns: 0.027 (float)
```

#### `get_market_data()`
Get comprehensive market data.

```python
data = await provider.get_market_data()

# Returns:
{
    'current_price': 0.027,
    'total_volume': 125000.0,
    'market_cap': 2700000.0,
    'price_change_24h': -0.001,
    'price_change_percentage_24h': -3.57
}
```

## Analytics & Metadata

### Query History

Track user queries for analytics and debugging.

```python
# Save a query
query_id = await provider.save_query_history(
    user_id='U12345',
    user_name='John Doe',
    channel_id='C67890',
    query_text='Show trades from last week',
    query_type='trades',
    generated_code='df = get_trades_df(...)',
    result_summary='Found 42 trades',
    execution_time_ms=125,
    success=True,
    error_message=None
)

# Retrieve history
history = await provider.get_query_history(user_id='U12345', limit=50)
```

### Saved Functions

Store and reuse custom analysis functions.

```python
# Save a function
success = await provider.save_function(
    name='calculate_daily_pnl',
    code='df.groupby(df["timestamp"].dt.date)["volume"].sum()',
    description='Calculate total PnL by day',
    created_by='U12345'
)

# Get a function
func = await provider.get_function('calculate_daily_pnl')
# Returns: {'name': '...', 'code': '...', 'description': '...', ...}

# List all functions
functions = await provider.list_functions()
```

### OTC Transactions

Track over-the-counter trades.

```python
# Save OTC transaction
otc_id = await provider.save_otc_transaction(
    date_str='2025-11-30',
    alkimi_amount=100000.0,
    usd_amount=2700.0,
    price=0.027,
    side='buy',
    counterparty='Investor ABC',
    notes='Quarterly purchase',
    created_by='U12345'
)

# Get OTC transactions
otc_df = await provider.get_otc_transactions(
    since='2025-11-01',
    until='2025-11-30'
)
```

## Database Schema

The DataProvider automatically creates and manages these tables:

### `trades`
Trade cache (created by TradeCache).
```sql
- id: INTEGER PRIMARY KEY
- trade_id: TEXT
- exchange: TEXT
- account_name: TEXT
- timestamp: TEXT
- symbol: TEXT
- side: TEXT
- amount: REAL
- price: REAL
- fee: REAL
- fee_currency: TEXT
- cached_at: TEXT
```

### `query_history`
User query tracking.
```sql
- id: INTEGER PRIMARY KEY
- user_id: TEXT
- user_name: TEXT
- channel_id: TEXT
- query_text: TEXT
- query_type: TEXT
- generated_code: TEXT
- result_summary: TEXT
- execution_time_ms: INTEGER
- success: BOOLEAN
- error_message: TEXT
- created_at: TIMESTAMP
```

### `saved_functions`
Reusable analysis functions.
```sql
- id: INTEGER PRIMARY KEY
- name: TEXT UNIQUE
- description: TEXT
- code: TEXT
- created_by: TEXT
- created_at: TIMESTAMP
- last_used: TIMESTAMP
- use_count: INTEGER
```

### `pnl_config`
Configuration for PnL calculations.
```sql
- id: INTEGER PRIMARY KEY
- key: TEXT UNIQUE
- value: TEXT
- updated_by: TEXT
- updated_at: TIMESTAMP
```

### `otc_transactions`
Over-the-counter trades.
```sql
- id: INTEGER PRIMARY KEY
- date: TEXT
- counterparty: TEXT
- alkimi_amount: REAL
- usd_amount: REAL
- price: REAL
- side: TEXT
- notes: TEXT
- created_by: TEXT
- created_at: TIMESTAMP
```

## Usage Patterns

### Context Manager Pattern
```python
async with DataProvider() as provider:
    trades = await provider.get_trades_df(since=datetime.now() - timedelta(days=7))
    price = await provider.get_current_price()
    # ... use provider
# Automatically closes connections
```

### Manual Cleanup
```python
provider = DataProvider()
await provider.initialize()

try:
    # ... use provider
    pass
finally:
    await provider.close()
```

### Slack Bot Integration
```python
# In your Slack bot handler
@app.command("/trades")
async def handle_trades_command(ack, command, respond):
    await ack()

    provider = DataProvider()
    await provider.initialize()

    try:
        # Get trade summary
        since = datetime.now() - timedelta(days=7)
        summary = await provider.get_trade_summary(since=since)

        # Save query history
        await provider.save_query_history(
            user_id=command['user_id'],
            user_name=command['user_name'],
            query_text=command['text'],
            query_type='trade_summary',
            success=True
        )

        # Send response
        await respond(
            f"Found {summary['trade_count']} trades\n"
            f"Total volume: ${summary['total_volume']:.2f}"
        )
    finally:
        await provider.close()
```

## Error Handling

All async methods handle errors gracefully and log them:

```python
# Returns empty DataFrame if error occurs
df = await provider.get_trades_df()
if df.empty:
    print("No trades or error occurred")

# Returns None if price fetch fails
price = await provider.get_current_price()
if price is None:
    print("Could not fetch price")

# Returns empty dict if snapshot not found
balances = await provider.get_balances()
if not balances:
    print("No snapshots available")
```

## Performance Considerations

1. **Connection Pooling**: SQLite connections are created per operation, optimized for concurrent access
2. **Caching**: CoinGecko client uses internal session caching
3. **Pagination**: DEX trade queries are paginated automatically
4. **Indexes**: Database has indexes on frequently queried columns
5. **Async Operations**: All I/O operations are async for better concurrency

## Dependencies

- `pandas`: DataFrame operations
- `sqlite3`: Database access
- `httpx`: HTTP client (via CoinGecko and Sui monitor)
- `src.data.trade_cache`: Trade cache management
- `src.data.daily_snapshot`: Snapshot management
- `src.data.coingecko_client`: Price data
- `src.exchanges.sui_monitor`: DEX trade monitoring

## Example: Complete Analysis Workflow

```python
from datetime import datetime, timedelta
from src.bot.data_provider import DataProvider

async def analyze_last_week():
    async with DataProvider() as provider:
        # Time range
        since = datetime.now() - timedelta(days=7)

        # Get all data
        trades_df = await provider.get_trades_df(since=since)
        dex_df = await provider.get_dex_trades(since=since)
        price = await provider.get_current_price()
        summary = await provider.get_trade_summary(since=since)

        # Analysis
        cex_volume = summary['total_volume']
        dex_volume = (dex_df['amount'] * dex_df['price']).sum() if not dex_df.empty else 0
        total_volume = cex_volume + dex_volume

        print(f"Last 7 days analysis:")
        print(f"  CEX volume: ${cex_volume:,.2f}")
        print(f"  DEX volume: ${dex_volume:,.2f}")
        print(f"  Total volume: ${total_volume:,.2f}")
        print(f"  Current price: ${price:.6f}")
        print(f"  Total trades: {summary['trade_count'] + len(dex_df)}")

        return {
            'cex_volume': cex_volume,
            'dex_volume': dex_volume,
            'total_volume': total_volume,
            'current_price': price
        }
```
