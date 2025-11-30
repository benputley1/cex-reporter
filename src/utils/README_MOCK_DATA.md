# Mock Data Module

The mock data module (`mock_data.py`) provides realistic test data for the CEX Reporter project, allowing development and testing without requiring API keys from exchanges.

## Overview

The module generates consistent, reproducible mock data for:
- Account balances across 4 exchanges
- Historical trade data since 2025-08-19
- Current market prices
- Portfolio summaries and statistics

## Exchange Configuration

### Balances

Mock balances are configured for 4 exchanges:

| Exchange | USDT Balance | ALKIMI Balance | Notes |
|----------|-------------|----------------|-------|
| MEXC | $50,000 | 1,500,000 | Primary market |
| Kraken | $75,000 | 0 | ALKIMI not listed |
| KuCoin | $30,000 | 800,000 | Secondary market |
| Gate.io | $45,000 | 1,200,000 | Secondary market |
| **Total** | **$200,000** | **3,500,000** | **$900K USD value** |

### Prices

Current mock prices:
- **USDT/USD**: $1.00 (stable)
- **ALKIMI/USD**: $0.20 (current)
- Historical ALKIMI range: $0.15 - $0.25

## Functions

### Balance Functions

#### `get_mock_balances(exchange: str) -> Dict[str, float]`
Returns balance dictionary for a specific exchange.

```python
from src.utils.mock_data import get_mock_balances

balances = get_mock_balances('mexc')
# Returns: {'USDT': 50000.00, 'ALKIMI': 1500000.00}
```

#### `get_portfolio_summary() -> Dict`
Returns aggregated portfolio statistics across all exchanges.

```python
from src.utils.mock_data import get_portfolio_summary

portfolio = get_portfolio_summary()
# Returns: {
#     'total_usdt': 200000.00,
#     'total_alkimi': 3500000.00,
#     'total_value_usd': 900000.00,
#     ...
# }
```

### Price Functions

#### `get_mock_prices(symbols: List[str]) -> Dict[str, float]`
Returns current prices for specified symbols.

```python
from src.utils.mock_data import get_mock_prices

prices = get_mock_prices(['USDT', 'ALKIMI'])
# Returns: {'USDT': 1.00, 'ALKIMI': 0.20}
```

### Trade Functions

#### `get_mock_trades(exchange: str, since: datetime, symbols: Optional[List[str]] = None) -> List[Trade]`
Returns mock trade history for an exchange.

```python
from datetime import datetime
from src.utils.mock_data import get_mock_trades

start_date = datetime(2025, 8, 19, 0, 0, 0)
trades = get_mock_trades('mexc', start_date)
# Returns: List of Trade objects (30 trades for MEXC)
```

#### `get_all_mock_trades(since: datetime, symbols: Optional[List[str]] = None) -> Dict[str, List[Trade]]`
Returns all trades across all exchanges.

```python
from datetime import datetime
from src.utils.mock_data import get_all_mock_trades

start_date = datetime(2025, 8, 19, 0, 0, 0)
all_trades = get_all_mock_trades(start_date)
# Returns: {'mexc': [...], 'kraken': [...], 'kucoin': [...], 'gateio': [...]}
```

#### `get_cached_trades(exchange: str, since: Optional[datetime] = None) -> List[Trade]`
Returns cached (consistent) trades for an exchange. Useful when you need the same trade data across multiple calls.

```python
from src.utils.mock_data import get_cached_trades

# Always returns the same trades for consistency
trades = get_cached_trades('mexc')
```

### Summary Functions

#### `get_mock_trade_summary(since: datetime) -> Dict[str, Dict]`
Returns aggregated trade statistics per exchange.

```python
from datetime import datetime
from src.utils.mock_data import get_mock_trade_summary

start_date = datetime(2025, 8, 19, 0, 0, 0)
summary = get_mock_trade_summary(start_date)
# Returns statistics for each exchange:
# {
#     'mexc': {
#         'total_trades': 30,
#         'buy_trades': 17,
#         'sell_trades': 13,
#         'buy_volume_usd': 86010.21,
#         'sell_volume_usd': 58762.34,
#         'net_volume_usd': 27247.87,
#         'total_fees_usdt': 144.77,
#         'avg_alkimi_price': 0.212976
#     },
#     ...
# }
```

### Helper Functions

#### `generate_random_trades(...) -> List[Trade]`
Low-level function to generate random trades with specific parameters. Used internally by other functions.

#### `initialize_mock_trades(seed: int = 42)`
Initializes the mock trade cache with a specific random seed for reproducibility.

## Trade Data Characteristics

The mock trade generator creates realistic data with:

### Volume Distribution
- **MEXC**: 15 trades per symbol (~30 total)
- **Kraken**: 10 trades (USDT only, no ALKIMI)
- **KuCoin**: 12 trades per symbol (~24 total)
- **Gate.io**: 13 trades per symbol (~26 total)

### Price Behavior
- **Base price ranges**: USDT $0.998-$1.002, ALKIMI $0.15-$0.25
- **Trend factor**: Up to 20% price increase over time period
- **Volatility**: ±5% random variation per trade
- **Final range**: USDT ~$0.95-$1.26, ALKIMI ~$0.14-$0.39

### Trade Sizes
- **ALKIMI trades**: 1,000 - 50,000 tokens
- **USDT trades**: 100 - 10,000 units

### Fees
- **Fee rate**: 0.1% (typical for most exchanges)
- **Fee currency**: USDT (standardized)

### Trade Distribution
- **Buy/Sell ratio**: Approximately 50/50 with some randomization
- **Timestamps**: Randomly distributed across date range
- **Chronological ordering**: All trades sorted by timestamp

## Reproducibility

The module uses a seeded random number generator (seed=42) to ensure consistent data across runs. This means:
- Same balances every time
- Same trade history every time
- Predictable for testing

To regenerate with different data:
```python
from src.utils.mock_data import initialize_mock_trades

initialize_mock_trades(seed=123)  # Use different seed
```

## Testing

Run the comprehensive test suite:
```bash
python3 -m unittest tests/test_mock_data.py -v
```

Run the demo:
```bash
python3 -m src.utils.mock_data
```

## Integration with CEX Reporter

The mock data module integrates with the exchange interface by providing an alternative to live API calls:

```python
from config.settings import settings
from src.utils.mock_data import get_mock_balances, get_mock_trades

if settings.mock_mode:
    # Use mock data
    balances = get_mock_balances('mexc')
    trades = get_mock_trades('mexc', since_date)
else:
    # Use real exchange API
    balances = await exchange.get_balances()
    trades = await exchange.get_trades(since_date)
```

## Special Cases

### Kraken - ALKIMI Not Listed
Kraken does not list ALKIMI token, so:
- ALKIMI balance is 0
- No ALKIMI trades are generated
- Only USDT trades available

This reflects real-world conditions where not all assets are available on all exchanges.

## Data Quality

The mock data is designed to be realistic:
- ✅ Prices within historical ranges
- ✅ Realistic trade volumes
- ✅ Proper fee calculations (0.1%)
- ✅ Chronological ordering
- ✅ Unique trade IDs
- ✅ Buy/sell balance
- ✅ Date-based filtering
- ✅ Exchange-specific characteristics

## Future Enhancements

Potential improvements:
- More sophisticated price models (mean reversion, momentum)
- Order book simulation
- Market depth data
- Withdrawal/deposit history
- Multiple trading pairs beyond USDT and ALKIMI
- Exchange-specific fee structures
- Slippage simulation
