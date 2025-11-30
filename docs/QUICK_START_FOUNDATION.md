# Quick Start Guide - Foundation Modules

## Import Overview

```python
# Exchange base interface
from exchanges import (
    ExchangeInterface,
    Trade,
    TradeSide,
    ExchangeError,
    ExchangeConnectionError,
    ExchangeAuthError,
    ExchangeRateLimitError,
)

# Cache utilities
from utils import Cache, cached, get_cache, clear_cache

# Logging utilities
from utils import (
    setup_logging,
    get_logger,
    get_contextual_logger,
    setup_from_config,
    log_with_data,
)
```

## 1. Creating an Exchange Adapter

```python
from exchanges.base import ExchangeInterface, Trade, TradeSide
from datetime import datetime
from typing import Dict, List

class MyExchange(ExchangeInterface):
    """Example exchange implementation"""

    async def initialize(self) -> None:
        """Initialize exchange connection"""
        if self.mock_mode:
            self._initialized = True
            return

        # Setup real API client
        # self.client = ccxt.exchange(self.config)
        self._initialized = True

    async def get_balances(self) -> Dict[str, float]:
        """Get account balances"""
        if self.mock_mode:
            return self._generate_mock_balances()

        # Real implementation
        # balances = await self.client.fetch_balance()
        # return {asset: balances[asset]['free'] for asset in ['USDT', 'ALKIMI']}
        return {}

    async def get_trades(self, since: datetime) -> List[Trade]:
        """Get trade history"""
        if self.mock_mode:
            return self._generate_mock_trades(since)

        # Real implementation
        trades = []
        # raw_trades = await self.client.fetch_my_trades(since=since.timestamp())
        # for t in raw_trades:
        #     trades.append(Trade(
        #         timestamp=datetime.fromtimestamp(t['timestamp']/1000),
        #         symbol=t['symbol'].split('/')[0],
        #         side=TradeSide.BUY if t['side'] == 'buy' else TradeSide.SELL,
        #         amount=t['amount'],
        #         price=t['price'],
        #         fee=t['fee']['cost'],
        #         fee_currency=t['fee']['currency'],
        #         trade_id=t['id']
        #     ))
        return trades

    async def get_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices"""
        if self.mock_mode:
            return self._generate_mock_prices(symbols)

        # Real implementation
        # prices = {}
        # for symbol in symbols:
        #     ticker = await self.client.fetch_ticker(f"{symbol}/USDT")
        #     prices[symbol] = ticker['last']
        return {}

    async def close(self) -> None:
        """Close connection"""
        # await self.client.close()
        pass


# Usage
async def main():
    from config.settings import settings

    exchange = MyExchange(
        exchange_name='myexchange',
        config=settings.get_exchange_config('myexchange'),
        mock_mode=settings.mock_mode
    )

    async with exchange:
        balances = await exchange.get_balances()
        print(f"Balances: {balances}")
```

## 2. Using the Cache

### Basic Usage

```python
from utils import Cache

# Create cache with 60 second TTL
cache = Cache(default_ttl=60)

# Store value
cache.set("prices:ALKIMI", 0.025, ttl=300)

# Retrieve value
price = cache.get("prices:ALKIMI")

# Check if exists
if cache.has("prices:ALKIMI"):
    print("Price is cached")

# Delete specific key
cache.delete("prices:ALKIMI")

# Clear all
cache.clear()

# Get statistics
stats = cache.get_stats()
print(f"Cache has {stats['valid_entries']} valid entries")
```

### Using the Decorator

```python
from utils import cached
from typing import Dict, List

@cached(ttl=300)
async def fetch_prices_from_api(symbols: List[str]) -> Dict[str, float]:
    """
    This function result will be cached for 5 minutes.
    Subsequent calls with same arguments will return cached result.
    """
    # Expensive API call
    prices = await api.get_prices(symbols)
    return prices

# First call - hits API
prices1 = await fetch_prices_from_api(['USDT', 'ALKIMI'])

# Second call within 5 minutes - returns cached result
prices2 = await fetch_prices_from_api(['USDT', 'ALKIMI'])
```

### Global Cache Instance

```python
from utils import get_cache, clear_cache

# Get global cache
cache = get_cache()

# Use it anywhere in your application
cache.set("app:last_run", datetime.now())

# Clear when needed
clear_cache()
```

## 3. Setting Up Logging

### Basic Setup

```python
from utils import setup_logging, get_logger

# Initialize logging (call once at startup)
setup_logging(
    log_level="INFO",
    log_dir="logs",
    log_file="cex_reporter.log",
    max_bytes=10*1024*1024,  # 10MB
    backup_count=5,
    json_format=True,
    console_output=True
)

# Get logger for your module
logger = get_logger(__name__)

# Use logger
logger.info("Application started")
logger.warning("Low balance detected")
logger.error("API call failed", exc_info=True)
```

### Using Config Integration

```python
from utils import setup_from_config

# Automatically loads settings from config.settings
setup_from_config()
```

### Structured Logging

```python
from utils import get_logger, log_with_data

logger = get_logger(__name__)

# Log with structured data
log_with_data(
    logger,
    'info',
    'Trade executed successfully',
    exchange='mexc',
    symbol='ALKIMI',
    amount=1000.0,
    price=0.025,
    total_cost=25.0,
    fee=0.025
)

# This creates a JSON log entry with all fields
```

### Contextual Logging

```python
from utils import get_contextual_logger

# Create logger with context that's added to every log
logger = get_contextual_logger(
    __name__,
    exchange='mexc',
    process='trade_sync'
)

# All logs from this logger include exchange and process
logger.info("Starting sync")  # Includes exchange='mexc', process='trade_sync'
logger.info("Sync complete")  # Includes exchange='mexc', process='trade_sync'
```

## 4. Complete Application Example

```python
import asyncio
from datetime import datetime, timedelta
from config.settings import settings
from utils import setup_from_config, get_logger, cached
from exchanges import ExchangeInterface

# Initialize logging at startup
setup_from_config()
logger = get_logger(__name__)


class MEXCExchange(ExchangeInterface):
    # ... implementation ...
    pass


@cached(ttl=300)
async def get_all_balances(exchanges):
    """Get balances from all exchanges (cached for 5 minutes)"""
    all_balances = {}
    for exchange in exchanges:
        try:
            balances = await exchange.get_balances()
            all_balances[exchange.exchange_name] = balances
        except Exception as e:
            logger.error(f"Failed to get balances from {exchange.exchange_name}", exc_info=True)
    return all_balances


async def main():
    logger.info("CEX Reporter starting")

    # Create exchanges
    exchanges = [
        MEXCExchange('mexc', settings.mexc_config, settings.mock_mode),
        # Add other exchanges...
    ]

    # Initialize all exchanges
    for exchange in exchanges:
        try:
            await exchange.initialize()
            logger.info(f"Initialized {exchange.exchange_name}")
        except Exception as e:
            logger.error(f"Failed to initialize {exchange.exchange_name}", exc_info=True)

    # Get balances (will be cached)
    balances = await get_all_balances(exchanges)
    logger.info(f"Retrieved balances from {len(balances)} exchanges")

    # Get trades
    since = datetime.now() - timedelta(days=7)
    for exchange in exchanges:
        try:
            trades = await exchange.get_trades(since)
            logger.info(f"Retrieved {len(trades)} trades from {exchange.exchange_name}")
        except Exception as e:
            logger.error(f"Failed to get trades from {exchange.exchange_name}", exc_info=True)

    # Cleanup
    for exchange in exchanges:
        await exchange.close()

    logger.info("CEX Reporter completed")


if __name__ == "__main__":
    asyncio.run(main())
```

## 5. Error Handling

```python
from exchanges import (
    ExchangeError,
    ExchangeConnectionError,
    ExchangeAuthError,
    ExchangeRateLimitError
)

async def safe_fetch_balances(exchange):
    """Example of proper error handling"""
    try:
        balances = await exchange.get_balances()
        return balances

    except ExchangeAuthError as e:
        logger.error(f"Authentication failed: {e}")
        # Maybe refresh credentials?

    except ExchangeRateLimitError as e:
        logger.warning(f"Rate limit hit: {e}")
        # Wait and retry
        await asyncio.sleep(60)
        return await exchange.get_balances()

    except ExchangeConnectionError as e:
        logger.error(f"Connection failed: {e}")
        # Retry with backoff

    except ExchangeError as e:
        logger.error(f"Exchange error: {e}")
        # Handle generic exchange error

    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)

    return None
```

## 6. Testing with Mock Mode

```python
# In your .env file:
# MOCK_MODE=true

from config.settings import settings

# When mock_mode is enabled, all exchanges use mock data
exchange = MEXCExchange(
    'mexc',
    settings.mexc_config,
    mock_mode=settings.mock_mode  # True from .env
)

async with exchange:
    # Returns realistic mock data - no API keys needed!
    balances = await exchange.get_balances()
    # {'USDT': 2133.7, 'ALKIMI': 37129.72}

    trades = await exchange.get_trades(datetime.now() - timedelta(days=7))
    # [Trade(...), Trade(...), ...]

    prices = await exchange.get_prices(['USDT', 'ALKIMI'])
    # {'USDT': 1.0, 'ALKIMI': 0.0254}
```

## Key Points

1. **Always initialize logging first** - Call `setup_from_config()` or `setup_logging()` at application startup
2. **Use mock mode for testing** - Set `MOCK_MODE=true` in `.env` to test without API keys
3. **Cache expensive operations** - Use `@cached()` decorator for API calls
4. **Proper error handling** - Catch specific exchange exceptions
5. **Structured logging** - Use `log_with_data()` for rich log entries
6. **Context managers** - Use `async with exchange:` for automatic cleanup
7. **Type hints** - All modules are fully typed for better IDE support

## File Locations

- Exchange Base: `/Users/ben/Desktop/cex-reporter/src/exchanges/base.py`
- Cache Utility: `/Users/ben/Desktop/cex-reporter/src/utils/cache.py`
- Logging Utility: `/Users/ben/Desktop/cex-reporter/src/utils/logging.py`
- Documentation: `/Users/ben/Desktop/cex-reporter/FOUNDATION_MODULES_SUMMARY.md`
