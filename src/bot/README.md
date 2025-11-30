# ALKIMI Slack Bot - Data Provider Module

## Summary

Successfully created `data_provider.py` - a unified data access layer for the ALKIMI trading bot that consolidates access to:
- Trade data from SQLite (`data/trade_cache.db`)
- Daily balance snapshots from JSON files (`data/snapshots/`)
- DEX trades from Sui blockchain
- Current prices from CoinGecko

## Files Created

1. **`data_provider.py`** (706 lines) - Main implementation
2. **`DATA_PROVIDER_README.md`** - Complete API documentation
3. **`QUICK_REFERENCE.md`** - Quick reference guide
4. **`ARCHITECTURE.md`** - System architecture diagram
5. **`../examples/data_provider_example.py`** - Usage examples
6. **`../tests/test_data_provider.py`** - Unit tests
7. **`../IMPLEMENTATION_SUMMARY.md`** - Implementation details

## Quick Start

```python
from src.bot.data_provider import DataProvider
from datetime import datetime, timedelta

# Use context manager (recommended)
async with DataProvider() as provider:
    # Get trades from last 7 days
    since = datetime.now() - timedelta(days=7)
    trades_df = await provider.get_trades_df(since=since)

    # Get current price
    price = await provider.get_current_price()

    # Get trade summary
    summary = await provider.get_trade_summary(since=since)

    print(f"Found {len(trades_df)} trades")
    print(f"Current price: ${price}")
    print(f"Total volume: ${summary['total_volume']}")
```

## Core Methods

### Trade Data
- `get_trades_df(since, until, exchange, account)` - Query trades as DataFrame
- `get_trade_summary(since, until)` - Get aggregated statistics

### Balance Data
- `get_balances()` - Get current balances from latest snapshot
- `get_snapshots(days)` - Get historical daily snapshots

### DEX Data
- `get_dex_trades(since)` - Get DEX trades from Sui blockchain

### Market Data
- `get_current_price()` - Get ALKIMI price from CoinGecko
- `get_market_data()` - Get comprehensive market data

### Analytics
- `save_query_history(...)` - Track user queries
- `get_query_history(user_id, limit)` - Retrieve query history
- `save_function(name, code, created_by)` - Save reusable functions
- `get_function(name)` - Get saved function
- `list_functions()` - List all saved functions

### OTC Transactions
- `save_otc_transaction(...)` - Record OTC trades
- `get_otc_transactions(since, until)` - Query OTC trades

## Database Tables

The DataProvider automatically creates these tables in `data/trade_cache.db`:

1. **`trades`** - CEX trade cache (existing)
2. **`query_history`** - User query tracking (new)
3. **`saved_functions`** - Reusable analysis functions (new)
4. **`pnl_config`** - PnL configuration (new)
5. **`otc_transactions`** - Over-the-counter trades (new)

## Data Locations

- **Trade Cache**: `/Users/ben/Desktop/cex-reporter/data/trade_cache.db`
- **Snapshots**: `/Users/ben/Desktop/cex-reporter/data/snapshots/`
- **Exchange Data**: `/Users/ben/Desktop/cex-reporter/Exchange Data /` (exported reports)

## Testing

```bash
# Run unit tests
pytest tests/test_data_provider.py -v

# Run example script
python3 examples/data_provider_example.py
```

## Documentation

- **DATA_PROVIDER_README.md** - Full API documentation with examples
- **QUICK_REFERENCE.md** - Quick reference for common operations
- **ARCHITECTURE.md** - System architecture and design decisions
- **IMPLEMENTATION_SUMMARY.md** - Complete implementation details

## Integration with Slack Bot

```python
from src.bot.data_provider import DataProvider

@app.command("/trades")
async def handle_trades_command(ack, command, respond):
    await ack()

    async with DataProvider() as provider:
        # Get trade summary
        since = datetime.now() - timedelta(days=7)
        summary = await provider.get_trade_summary(since=since)

        # Save query for analytics
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
            f"Total volume: ${summary['total_volume']:,.2f}"
        )
```

## Features

- ✅ Async/await for non-blocking I/O
- ✅ Context manager support (`async with`)
- ✅ Comprehensive error handling
- ✅ Safe defaults (empty DataFrames, not errors)
- ✅ Full type hints
- ✅ Extensive logging
- ✅ Database migrations
- ✅ Unit tests
- ✅ Complete documentation

## Dependencies

- `pandas` - DataFrame operations
- `sqlite3` - Database access (built-in)
- `src.data.trade_cache` - Trade cache management
- `src.data.daily_snapshot` - Snapshot management
- `src.data.coingecko_client` - Price data
- `src.exchanges.sui_monitor` - DEX monitoring (optional)

## Next Steps

1. Integrate DataProvider into Slack bot handlers
2. Add custom query types to query_history
3. Create saved functions for common analyses
4. Set up monitoring for query performance
5. Implement caching layer if needed

## Support

For questions or issues:
1. Check DATA_PROVIDER_README.md for detailed documentation
2. Review examples/data_provider_example.py for usage patterns
3. Run tests to verify functionality
4. Check logs for debugging information

---

**Implementation Date**: November 30, 2025
**Version**: 1.0.0
**Status**: Production Ready
