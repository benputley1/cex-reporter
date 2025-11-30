# DataProvider Quick Reference

## Import
```python
from src.bot.data_provider import DataProvider
```

## Initialization
```python
provider = DataProvider(
    db_path="data/trade_cache.db",
    snapshots_dir="data/snapshots",
    sui_config=None  # Optional: Sui DEX configuration
)
await provider.initialize()
```

## Common Operations

### Get Trades (Last 7 Days)
```python
from datetime import datetime, timedelta

since = datetime.now() - timedelta(days=7)
df = await provider.get_trades_df(since=since)
```

### Get Current Price
```python
price = await provider.get_current_price()
print(f"ALKIMI: ${price:.6f}")
```

### Get Balances
```python
balances = await provider.get_balances()
for account, assets in balances.items():
    for asset, amount in assets.items():
        print(f"{account} - {asset}: {amount:,.2f}")
```

### Get Trade Summary
```python
summary = await provider.get_trade_summary(since=since)
print(f"Total volume: ${summary['total_volume']:,.2f}")
print(f"Trade count: {summary['trade_count']}")
```

### Get DEX Trades
```python
dex_df = await provider.get_dex_trades(since=since)
print(f"Found {len(dex_df)} DEX trades")
```

### Get Snapshots
```python
snapshots = await provider.get_snapshots(days=30)
# Returns list of daily balance snapshots
```

### Save Query History
```python
await provider.save_query_history(
    user_id='U12345',
    query_text='Show trades',
    query_type='trades',
    success=True
)
```

### Save OTC Transaction
```python
await provider.save_otc_transaction(
    date_str='2025-11-30',
    alkimi_amount=100000,
    usd_amount=2700,
    price=0.027,
    side='buy'
)
```

### Save & Use Functions
```python
# Save
await provider.save_function(
    name='my_func',
    code='df["pnl"] = df["amount"] * df["price"]',
    created_by='user123'
)

# Get
func = await provider.get_function('my_func')
exec(func['code'])  # Execute the saved code
```

## Cleanup
```python
await provider.close()
```

## Context Manager (Recommended)
```python
async with DataProvider() as provider:
    df = await provider.get_trades_df()
    price = await provider.get_current_price()
    # ... your code
# Automatically closes
```

## DataFrame Schemas

### Trades DataFrame
| Column | Type | Description |
|--------|------|-------------|
| timestamp | datetime | Trade timestamp |
| exchange | str | Exchange name |
| account_name | str | Account identifier |
| symbol | str | Asset symbol |
| side | str | 'buy' or 'sell' |
| amount | float | Trade amount |
| price | float | Trade price |
| fee | float | Fee amount |
| fee_currency | str | Fee currency |
| trade_id | str | Unique trade ID |

### DEX Trades DataFrame
| Column | Type | Description |
|--------|------|-------------|
| timestamp | datetime | Trade timestamp |
| exchange | str | DEX name (e.g., 'cetus') |
| symbol | str | Token symbol |
| side | str | 'buy' or 'sell' |
| amount | float | Trade amount |
| price | float | Trade price |
| fee | float | DEX fee |
| fee_currency | str | Fee currency |
| trade_id | str | Transaction digest |

### OTC Transactions DataFrame
| Column | Type | Description |
|--------|------|-------------|
| id | int | Record ID |
| date | str | Transaction date |
| counterparty | str | Counterparty name |
| alkimi_amount | float | ALKIMI amount |
| usd_amount | float | USD value |
| price | float | Price per ALKIMI |
| side | str | 'buy' or 'sell' |
| notes | str | Additional notes |
| created_by | str | User who created |
| created_at | timestamp | Creation timestamp |

## Common Patterns

### Weekly Analysis
```python
async def weekly_analysis():
    async with DataProvider() as provider:
        week_ago = datetime.now() - timedelta(days=7)

        # Get data
        trades = await provider.get_trades_df(since=week_ago)
        dex_trades = await provider.get_dex_trades(since=week_ago)
        summary = await provider.get_trade_summary(since=week_ago)

        # Calculate
        cex_vol = summary['total_volume']
        dex_vol = (dex_trades['amount'] * dex_trades['price']).sum()

        return {
            'cex_volume': cex_vol,
            'dex_volume': dex_vol,
            'total_trades': summary['trade_count'] + len(dex_trades)
        }
```

### Compare Exchanges
```python
async def compare_exchanges():
    async with DataProvider() as provider:
        since = datetime.now() - timedelta(days=30)
        summary = await provider.get_trade_summary(since=since)

        for exchange, stats in summary['by_exchange'].items():
            print(f"{exchange}:")
            print(f"  Trades: {stats['trade_count']}")
            print(f"  Volume: ${stats['volume']:,.2f}")
```

### Track Price Changes
```python
async def track_prices():
    async with DataProvider() as provider:
        snapshots = await provider.get_snapshots(days=7)

        for snapshot in snapshots:
            date = snapshot['date']
            alkimi = snapshot['balances'].get('ALKIMI', 0)
            print(f"{date}: {alkimi:,.2f} ALKIMI")
```

## Error Handling

All methods return safe defaults on error:
- DataFrames: Empty DataFrame with correct schema
- Price: `None`
- Balances: Empty dict `{}`
- Summary: Dict with zero values

Always check return values:
```python
price = await provider.get_current_price()
if price is None:
    print("Could not fetch price")
else:
    print(f"Price: ${price}")
```
