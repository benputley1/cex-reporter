# Mock Data Module - Quick Reference

## Quick Start

```python
from datetime import datetime
from src.utils.mock_data import (
    get_mock_balances,
    get_mock_trades,
    get_mock_prices,
    get_portfolio_summary,
)

# Get balances
balances = get_mock_balances('mexc')  # {'USDT': 50000.0, 'ALKIMI': 1500000.0}

# Get trades
trades = get_mock_trades('mexc', datetime(2025, 8, 19))  # List[Trade]

# Get prices
prices = get_mock_prices(['USDT', 'ALKIMI'])  # {'USDT': 1.0, 'ALKIMI': 0.2}

# Get portfolio summary
portfolio = get_portfolio_summary()  # Total value: $900K
```

## Data Overview

### Exchanges & Balances
| Exchange | USDT | ALKIMI | Value |
|----------|------|--------|-------|
| MEXC | $50K | 1.5M | $350K |
| Kraken | $75K | 0 | $75K |
| KuCoin | $30K | 800K | $190K |
| Gate.io | $45K | 1.2M | $285K |

### Prices
- USDT: $1.00
- ALKIMI: $0.20

### Trades
- Total: ~90 trades since Aug 19, 2025
- MEXC: 30 trades
- Kraken: 10 trades (USDT only)
- KuCoin: 24 trades
- Gate.io: 26 trades

## Function Reference

### Balances
```python
get_mock_balances('mexc')           # Dict[str, float]
get_portfolio_summary()             # Dict with total stats
```

### Prices
```python
get_mock_prices(['USDT', 'ALKIMI']) # Dict[str, float]
```

### Trades
```python
get_mock_trades('mexc', since_date)              # List[Trade]
get_all_mock_trades(since_date)                  # Dict[str, List[Trade]]
get_cached_trades('mexc')                        # List[Trade] (consistent)
get_cached_trades('mexc', since=filter_date)     # Filtered trades
```

### Analysis
```python
get_mock_trade_summary(since_date)  # Dict with statistics per exchange
```

### Helper
```python
initialize_mock_trades(seed=42)     # Reinitialize with seed
```

## Common Patterns

### Pattern 1: Basic Trading Data
```python
from datetime import datetime
from src.utils.mock_data import get_mock_trades

trades = get_mock_trades('mexc', datetime(2025, 8, 19))
for trade in trades[:5]:
    print(f"{trade.symbol} {trade.side.value} {trade.amount} @ ${trade.price}")
```

### Pattern 2: Portfolio Value
```python
from src.utils.mock_data import get_portfolio_summary

portfolio = get_portfolio_summary()
print(f"Total Value: ${portfolio['total_value_usd']:,.2f}")
print(f"ALKIMI: {portfolio['total_alkimi']:,.0f} @ ${portfolio['alkimi_price']}")
```

### Pattern 3: Trade Statistics
```python
from datetime import datetime
from src.utils.mock_data import get_mock_trade_summary

stats = get_mock_trade_summary(datetime(2025, 8, 19))
for exchange, data in stats.items():
    print(f"{exchange}: {data['total_trades']} trades, "
          f"${data['net_volume_usd']:,.2f} net volume")
```

### Pattern 4: Date Filtering
```python
from datetime import datetime
from src.utils.mock_data import get_cached_trades

# Get September trades only
sept_start = datetime(2025, 9, 1)
trades = get_cached_trades('mexc', since=sept_start)
```

### Pattern 5: P&L Calculation
```python
from src.utils.mock_data import get_cached_trades

trades = get_cached_trades('mexc')
alkimi_trades = [t for t in trades if t.symbol == 'ALKIMI']

total_bought = sum(t.amount for t in alkimi_trades if t.side.value == 'buy')
total_sold = sum(t.amount for t in alkimi_trades if t.side.value == 'sell')
net_position = total_bought - total_sold
```

## Testing

```bash
# Run all tests
python3 -m unittest tests/test_mock_data.py -v

# Run demo
python3 -m src.utils.mock_data

# Run examples
PYTHONPATH=/Users/ben/Desktop/cex-reporter python3 examples/mock_data_usage.py
```

## Data Characteristics

### Trade Generation
- **Price Range**: USDT $0.90-$1.30, ALKIMI $0.13-$0.40
- **Trend**: Up to 20% increase over time
- **Volatility**: ±5% per trade
- **Fees**: 0.1% standard
- **Distribution**: ~50/50 buy/sell

### Timestamps
- **Start Date**: 2025-08-19
- **End Date**: Current time
- **Distribution**: Random across range
- **Ordering**: Chronological

### Trade Sizes
- **ALKIMI**: 1,000 - 50,000 tokens
- **USDT**: 100 - 10,000 units

## Edge Cases

### Kraken - No ALKIMI
```python
balances = get_mock_balances('kraken')
# {'USDT': 75000.0, 'ALKIMI': 0.0}

trades = get_mock_trades('kraken', since_date, ['ALKIMI'])
# Returns [] (empty list)
```

### Unknown Assets
```python
prices = get_mock_prices(['BTC', 'UNKNOWN'])
# {'BTC': 67500.0, 'UNKNOWN': 1.0}  # Default for unknown
```

## File Locations

```
/Users/ben/Desktop/cex-reporter/
├── src/
│   ├── exchanges/
│   │   └── base.py                    # Base models
│   └── utils/
│       ├── mock_data.py               # Main module
│       └── README_MOCK_DATA.md        # Full docs
├── tests/
│   └── test_mock_data.py              # Test suite
├── examples/
│   └── mock_data_usage.py             # Usage examples
└── MOCK_DATA_MODULE_SUMMARY.md        # This summary
```

## Integration Example

```python
from config.settings import settings
from src.utils.mock_data import get_mock_balances, get_mock_trades

class ExchangeClient:
    def __init__(self, exchange_name):
        self.exchange = exchange_name
        self.mock_mode = settings.mock_mode

    async def get_balances(self):
        if self.mock_mode:
            return get_mock_balances(self.exchange)
        else:
            return await self._fetch_real_balances()

    async def get_trades(self, since):
        if self.mock_mode:
            return get_mock_trades(self.exchange, since)
        else:
            return await self._fetch_real_trades(since)
```

## Tips

1. **Use cached trades** for consistency across multiple calls
2. **Filter by date** after fetching for better performance
3. **Check exchange** before querying ALKIMI (not on Kraken)
4. **Use portfolio_summary** for aggregate statistics
5. **Set PYTHONPATH** when running examples

## Support

- Full Documentation: `/src/utils/README_MOCK_DATA.md`
- Usage Examples: `/examples/mock_data_usage.py`
- Test Suite: `/tests/test_mock_data.py`
- Summary: `/MOCK_DATA_MODULE_SUMMARY.md`
