# DataProvider Architecture

## System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      ALKIMI Slack Bot                       │
│                    (User Interface)                         │
└────────────────────────┬────────────────────────────────────┘
                         │
                         │ Uses
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                     DataProvider                            │
│              (Unified Data Access Layer)                    │
│                                                             │
│  • get_trades_df()        • get_balances()                 │
│  • get_dex_trades()       • get_current_price()            │
│  • get_trade_summary()    • get_snapshots()                │
│  • save_query_history()   • save_otc_transaction()         │
│  • save_function()        • get_market_data()              │
└──────┬────────┬──────────┬──────────┬──────────────────────┘
       │        │          │          │
       │        │          │          │
       ▼        ▼          ▼          ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐
│  Trade   │ │  Daily   │ │ CoinGecko│ │  SuiToken       │
│  Cache   │ │ Snapshot │ │  Client  │ │  Monitor        │
│          │ │          │ │          │ │                 │
│ SQLite   │ │   JSON   │ │   HTTP   │ │  GraphQL/RPC    │
│   DB     │ │  Files   │ │   API    │ │  (Blockchain)   │
└──────────┘ └──────────┘ └──────────┘ └─────────────────┘
     │            │             │              │
     ▼            ▼             ▼              ▼
┌──────────┐ ┌──────────┐ ┌──────────┐ ┌─────────────────┐
│  trades  │ │ snapshot │ │CoinGecko │ │  Sui Blockchain │
│  table   │ │  _date.  │ │   API    │ │  (DEX Trades)   │
│          │ │  json    │ │          │ │                 │
└──────────┘ └──────────┘ └──────────┘ └─────────────────┘
```

## Component Responsibilities

### DataProvider (Main Class)
**Purpose**: Unified interface for all data access operations

**Responsibilities**:
- Orchestrate data retrieval from multiple sources
- Transform data into consistent formats (DataFrames)
- Apply database migrations
- Manage component lifecycle
- Handle errors gracefully

**Key Features**:
- Async/await for non-blocking I/O
- Context manager support
- Comprehensive logging
- Safe defaults on errors

### TradeCache (Dependency)
**Purpose**: Persistent storage for CEX trades

**Data Source**: SQLite database (`data/trade_cache.db`)

**Responsibilities**:
- Store trades beyond API retention limits
- Deduplicate incoming trades
- Query with filters (date, exchange, account)

**Table**: `trades`

### DailySnapshot (Dependency)
**Purpose**: Daily balance tracking

**Data Source**: JSON files (`data/snapshots/snapshot_YYYY-MM-DD.json`)

**Responsibilities**:
- Save daily balance snapshots
- Load snapshots by date
- Track balance changes over time

**Format**: `{date, timestamp, balances: {asset: amount}}`

### CoinGeckoClient (Dependency)
**Purpose**: Market price data

**Data Source**: CoinGecko API (HTTPS)

**Responsibilities**:
- Get current ALKIMI price
- Get historical prices
- Get market data (volume, market cap)

**Endpoints**:
- `/simple/price` - Current price
- `/coins/{id}/history` - Historical price
- `/coins/{id}` - Market data

### SuiTokenMonitor (Dependency)
**Purpose**: DEX trade monitoring on Sui blockchain

**Data Source**: Sui GraphQL API + RPC

**Responsibilities**:
- Query ALKIMI coin objects
- Parse DEX swap transactions
- Track wallet balances
- Get pool analytics

**Methods**:
- GraphQL for transaction history
- RPC for balance queries

## Data Flow

### Trade Query Flow
```
User Request
    ↓
DataProvider.get_trades_df()
    ↓
TradeCache.get_trades()
    ↓
SQLite Query (SELECT with filters)
    ↓
Convert Trade objects → DataFrame
    ↓
Return to User
```

### DEX Trade Flow
```
User Request
    ↓
DataProvider.get_dex_trades()
    ↓
SuiTokenMonitor.get_trades()
    ↓
GraphQL: Get coin objects
    ↓
GraphQL: Get transaction details
    ↓
Parse balance changes → Trade objects
    ↓
Convert to DataFrame
    ↓
Return to User
```

### Balance Snapshot Flow
```
User Request
    ↓
DataProvider.get_balances()
    ↓
DailySnapshot.load_snapshot(today)
    ↓
Read JSON file
    ↓
Parse balances by exchange/account
    ↓
Return nested dict
```

### Price Data Flow
```
User Request
    ↓
DataProvider.get_current_price()
    ↓
CoinGeckoClient.get_current_price()
    ↓
HTTP GET to CoinGecko API
    ↓
Parse JSON response
    ↓
Return price (float)
```

## Database Schema

### SQLite Database: `data/trade_cache.db`

#### Existing Table: `trades`
```sql
CREATE TABLE trades (
    id INTEGER PRIMARY KEY,
    trade_id TEXT,
    exchange TEXT NOT NULL,
    account_name TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    amount REAL NOT NULL,
    price REAL NOT NULL,
    fee REAL NOT NULL,
    fee_currency TEXT,
    cached_at TEXT NOT NULL,
    UNIQUE(exchange, account_name, trade_id, timestamp, symbol, side, amount, price)
);
CREATE INDEX idx_timestamp ON trades(timestamp DESC);
CREATE INDEX idx_exchange_account ON trades(exchange, account_name);
```

#### New Table: `query_history`
```sql
CREATE TABLE query_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id TEXT NOT NULL,
    user_name TEXT,
    channel_id TEXT,
    query_text TEXT NOT NULL,
    query_type TEXT NOT NULL,
    generated_code TEXT,
    result_summary TEXT,
    execution_time_ms INTEGER,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_query_history_user ON query_history(user_id, created_at DESC);
CREATE INDEX idx_query_history_type ON query_history(query_type, created_at DESC);
```

#### New Table: `saved_functions`
```sql
CREATE TABLE saved_functions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    code TEXT NOT NULL,
    created_by TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_used TIMESTAMP,
    use_count INTEGER DEFAULT 0
);
```

#### New Table: `pnl_config`
```sql
CREATE TABLE pnl_config (
    id INTEGER PRIMARY KEY,
    key TEXT UNIQUE NOT NULL,
    value TEXT NOT NULL,
    updated_by TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

#### New Table: `otc_transactions`
```sql
CREATE TABLE otc_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    counterparty TEXT,
    alkimi_amount REAL NOT NULL,
    usd_amount REAL NOT NULL,
    price REAL NOT NULL,
    side TEXT NOT NULL,
    notes TEXT,
    created_by TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX idx_otc_date ON otc_transactions(date DESC);
```

## File Structure

```
cex-reporter/
├── src/
│   ├── bot/
│   │   ├── __init__.py
│   │   ├── data_provider.py          ← Main implementation
│   │   ├── DATA_PROVIDER_README.md   ← Full documentation
│   │   ├── QUICK_REFERENCE.md        ← Quick reference
│   │   ├── ARCHITECTURE.md           ← This file
│   │   └── slack_bot.py              ← Uses DataProvider
│   │
│   ├── data/
│   │   ├── trade_cache.py            ← TradeCache dependency
│   │   ├── daily_snapshot.py         ← DailySnapshot dependency
│   │   └── coingecko_client.py       ← CoinGeckoClient dependency
│   │
│   └── exchanges/
│       ├── base.py                   ← Trade models
│       └── sui_monitor.py            ← SuiTokenMonitor dependency
│
├── data/
│   ├── trade_cache.db                ← SQLite database
│   └── snapshots/
│       └── snapshot_YYYY-MM-DD.json  ← Daily snapshots
│
├── examples/
│   └── data_provider_example.py      ← Usage examples
│
├── tests/
│   └── test_data_provider.py         ← Unit tests
│
└── IMPLEMENTATION_SUMMARY.md         ← Implementation summary
```

## API Methods by Category

### Trade Data
```python
get_trades_df(since, until, exchange, account) → DataFrame
get_trade_summary(since, until) → Dict[str, Any]
```

### Balance Data
```python
get_balances() → Dict[str, Dict[str, float]]
get_snapshots(days) → List[Dict]
```

### DEX Data
```python
get_dex_trades(since) → DataFrame
```

### Market Data
```python
get_current_price() → Optional[float]
get_market_data() → Optional[Dict[str, Any]]
```

### Analytics Metadata
```python
save_query_history(...) → int
get_query_history(user_id, limit) → List[Dict]
save_function(name, code, created_by, description) → bool
get_function(name) → Optional[Dict]
list_functions() → List[Dict]
```

### OTC Transactions
```python
save_otc_transaction(...) → int
get_otc_transactions(since, until) → DataFrame
```

### Lifecycle
```python
initialize() → None
close() → None
__aenter__() → DataProvider
__aexit__() → None
```

## Error Handling Strategy

### Defensive Returns
- **DataFrames**: Return empty DataFrame with correct schema
- **Dicts**: Return empty dict `{}`
- **Lists**: Return empty list `[]`
- **Single values**: Return `None`

### Exception Handling
```python
try:
    # Operation
except SpecificError as e:
    logger.error(f"Context: {e}")
    return safe_default
```

### Logging Levels
- **DEBUG**: Query details, row counts
- **INFO**: Major operations (init, close, summaries)
- **WARNING**: Degraded functionality (missing snapshots)
- **ERROR**: Failures with full context

## Performance Characteristics

### Time Complexity
- Trade queries: O(n) where n = matching trades
- Snapshots: O(1) per file read
- DEX trades: O(n) where n = transactions to process
- Price fetch: O(1) API call

### Space Complexity
- DataFrame memory: ~100 bytes per trade row
- SQLite indexes: ~10% of data size
- Snapshot files: < 10KB each

### Scalability Limits
- SQLite: Tested to 100M+ rows
- DataFrames: Limited by RAM (~10M rows typical)
- API calls: Rate limited by external services
- Disk I/O: Snapshot count grows linearly with days

## Security Considerations

### SQL Injection Protection
All queries use parameterized statements:
```python
cursor.execute("SELECT * FROM trades WHERE exchange = ?", (exchange,))
```

### Input Validation
Type hints enforce contracts:
```python
async def get_trades_df(
    since: Optional[datetime] = None,  # Enforced
    exchange: Optional[str] = None      # Enforced
) -> pd.DataFrame:                      # Return type guaranteed
```

### No Code Execution
Saved functions are stored as strings, not executed automatically.

### Logging Safety
Sensitive data (API keys, user tokens) never logged.

## Extension Points

### Adding New Data Sources
1. Import client in `__init__()`
2. Create getter method
3. Transform to DataFrame/Dict
4. Handle errors
5. Add to `close()`

### Adding New Tables
1. Add CREATE TABLE in `_apply_migrations()`
2. Add save/get methods
3. Update tests
4. Document schema

### Adding New Aggregations
1. Create method in DataProvider
2. Use existing data sources
3. Return consistent format
4. Add tests

## Testing Strategy

### Unit Tests
- Isolated database (tempfile)
- Mock external APIs
- Test each method independently
- Verify error handling

### Integration Tests
- Use real database (test data)
- Test full workflows
- Verify data consistency
- Performance benchmarks

### Example-Based Testing
- Example script serves as smoke test
- Demonstrates real usage patterns
- Validates documentation

## Dependencies Graph

```
DataProvider
├── pandas (DataFrame operations)
├── sqlite3 (Database access)
├── src.data.trade_cache
│   └── sqlite3
├── src.data.daily_snapshot
│   ├── json
│   └── pathlib
├── src.data.coingecko_client
│   └── aiohttp (HTTP client)
└── src.exchanges.sui_monitor
    ├── httpx (HTTP client)
    └── src.exchanges.base
```

## Best Practices Implemented

1. **Async First**: All I/O operations are async
2. **Type Hints**: Full type annotations
3. **Context Managers**: Support `async with`
4. **Logging**: Comprehensive, structured logging
5. **Safe Defaults**: Never crash on errors
6. **Documentation**: Docstrings on all public methods
7. **Testing**: Unit and integration tests
8. **Migration Strategy**: Automatic, idempotent
9. **Error Recovery**: Graceful degradation
10. **Performance**: Indexed, optimized queries

## Monitoring & Observability

### Metrics to Track
- Query execution time (via `query_history`)
- Error rates (via logs)
- Data freshness (snapshot timestamps)
- API success rates (CoinGecko, Sui)

### Health Checks
```python
# Check database connectivity
await provider.get_trades_df()  # Should not raise

# Check snapshot freshness
balances = await provider.get_balances()
# If empty, snapshots may be stale

# Check price API
price = await provider.get_current_price()
# If None, API may be down
```

## Conclusion

The DataProvider architecture provides a clean separation of concerns with:
- **Single Responsibility**: Each component has one job
- **Open/Closed**: Extensible without modifying core
- **Dependency Inversion**: Depends on abstractions
- **Interface Segregation**: Clear, focused API
- **DRY**: No duplicate data access code

This design supports the ALKIMI Slack bot's current needs while remaining flexible for future requirements.
