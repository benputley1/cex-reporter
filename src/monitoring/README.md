# Health Monitoring System

Comprehensive health checks and monitoring for the cex-reporter application.

## Overview

The health monitoring system provides real-time status checks for all system components:
- **Database**: SQLite connectivity and query performance
- **Exchanges**: API connectivity and response times for all configured exchange accounts
- **CoinGecko API**: Price data availability
- **Sui Blockchain Monitor**: DEX data access (if configured)

## Features

- **Non-blocking async implementation** for efficient parallel health checks
- **Configurable thresholds** for status determination
- **Structured health data** for API/Slack formatting
- **Smart caching** (30-second cache duration)
- **Detailed error reporting** with latency metrics
- **Slack-formatted output** ready for notifications

## Usage

### Basic Health Check

```python
from src.bot.data_provider import DataProvider

# Initialize data provider
data_provider = DataProvider()
await data_provider.initialize()

# Perform basic health check (database + APIs)
health = await data_provider.health_check()

print(f"System Status: {health.overall_status.value}")
print(f"Components: {len(health.components)}")

for component in health.components:
    print(f"{component.name}: {component.status.value} ({component.latency_ms}ms)")
```

### Health Check with Exchanges

```python
# Create exchange clients
exchange_clients = {
    'mexc_mm1': mexc_client1,
    'mexc_mm2': mexc_client2,
    'kucoin_mm1': kucoin_client
}

# Perform comprehensive health check
health = await data_provider.health_check(
    exchange_clients=exchange_clients,
    use_cache=False  # Force fresh check
)
```

### Slack Formatting

```python
# Get health status
health = await data_provider.health_check()

# Format for Slack
slack_message = data_provider.format_health_for_slack(health)

# Post to Slack (using your Slack client)
await slack_client.chat_postMessage(
    channel="#monitoring",
    text=slack_message
)
```

### JSON Serialization

```python
# Get health status
health = await data_provider.health_check()

# Convert to dictionary for API responses
health_dict = health.to_dict()

# Returns:
{
    'overall_status': 'healthy',
    'timestamp': '2025-12-12T10:30:00',
    'components': [
        {
            'name': 'database',
            'status': 'healthy',
            'latency_ms': 15.3,
            'last_check': '2025-12-12T10:30:00',
            'error_message': None,
            'details': {'table_count': 8, 'recent_errors_1h': 0}
        },
        ...
    ],
    'summary': {
        'healthy': 5,
        'degraded': 1,
        'unhealthy': 0,
        'total': 6
    }
}
```

## Health Status Levels

### HEALTHY ✅
- Response time < 1 second
- No errors in the last hour
- All connections working

### DEGRADED ⚠️
- Response time 1-5 seconds
- Some recent errors but service operational
- API rate limits being approached

### UNHEALTHY ❌
- Response time > 5 seconds
- Connection failures
- Critical errors preventing operation

## Custom Thresholds

You can customize the health thresholds:

```python
from src.monitoring.health import HealthChecker, HealthThresholds

# Define custom thresholds
thresholds = HealthThresholds(
    healthy_latency_ms=500,     # 500ms for healthy
    unhealthy_latency_ms=2000,   # 2s for unhealthy
    error_rate_threshold=0.05    # 5% error rate
)

# Create health checker with custom thresholds
data_provider.health_checker = HealthChecker(data_provider, thresholds)

# Perform health check (will use custom thresholds)
health = await data_provider.health_check()
```

## Component Details

### Database Health Check

Tests:
- Connection establishment to SQLite database
- Query execution time
- Recent error count from query_history table

Details included:
- `table_count`: Number of tables in database
- `db_path`: Path to database file
- `recent_errors_1h`: Query errors in last hour

### Exchange Health Check

Tests:
- API connectivity
- Balance fetch operation
- Response time

Details included:
- `exchange`: Exchange name (mexc, kucoin, etc.)
- `account`: Account identifier (MM1, MM2, etc.)
- `mock_mode`: Whether using mock data
- `assets_tracked`: Number of assets with balances
- `has_balances`: Whether balances were fetched successfully

### CoinGecko Health Check

Tests:
- API connectivity
- Current price fetch
- Response time

Details included:
- `current_price`: Latest ALKIMI price
- `price_available`: Whether price was fetched successfully

### Sui Monitor Health Check

Tests:
- Blockchain RPC connectivity
- DEX trade data access
- Response time

Details included:
- `configured`: Whether Sui monitor is enabled
- `trades_24h`: Number of trades in last 24 hours

## Architecture

### Classes

#### `HealthStatus` (Enum)
- `HEALTHY`: All systems operational
- `DEGRADED`: Reduced performance but functional
- `UNHEALTHY`: Critical issues requiring attention

#### `ComponentHealth` (Dataclass)
Individual component health information:
- `name`: Component identifier
- `status`: HealthStatus enum value
- `latency_ms`: Response time in milliseconds
- `last_check`: Timestamp of this check
- `error_message`: Error details (if any)
- `details`: Component-specific metadata

#### `SystemHealth` (Dataclass)
Overall system health:
- `overall_status`: Aggregate status
- `components`: List of ComponentHealth objects
- `timestamp`: When check was performed

#### `HealthThresholds`
Configurable thresholds:
- `healthy_latency_ms`: Max latency for healthy (default: 1000ms)
- `unhealthy_latency_ms`: Min latency for unhealthy (default: 5000ms)
- `error_rate_threshold`: Error rate threshold (default: 0.1)

#### `HealthChecker`
Main health checking engine:
- `check_database()`: Check SQLite database
- `check_exchange()`: Check single exchange
- `check_all_exchanges()`: Check all exchanges in parallel
- `check_coingecko()`: Check CoinGecko API
- `check_sui_monitor()`: Check Sui blockchain monitor
- `get_system_health()`: Perform full system health check
- `format_health_for_slack()`: Format results for Slack

## Caching

Health checks are cached for 30 seconds to avoid excessive checking:

```python
# First call: performs actual checks
health1 = await data_provider.health_check(use_cache=True)

# Second call within 30 seconds: returns cached results
health2 = await data_provider.health_check(use_cache=True)

# Force fresh check (bypasses cache)
health3 = await data_provider.health_check(use_cache=False)
```

## Integration Examples

### Slack Bot Command

```python
async def handle_health_command(self, ack, say):
    await ack()

    # Perform health check
    health = await self.data_provider.health_check(
        exchange_clients=self.exchange_clients
    )

    # Format and send to Slack
    message = self.data_provider.format_health_for_slack(health)
    await say(message)
```

### REST API Endpoint

```python
from fastapi import FastAPI
from src.bot.data_provider import DataProvider

app = FastAPI()
data_provider = DataProvider()

@app.get("/health")
async def health_check():
    health = await data_provider.health_check()
    return health.to_dict()
```

### Scheduled Monitoring

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler

scheduler = AsyncIOScheduler()

async def monitor_health():
    health = await data_provider.health_check(
        exchange_clients=exchange_clients,
        use_cache=False
    )

    # Alert if unhealthy
    if health.overall_status == HealthStatus.UNHEALTHY:
        await send_slack_alert(
            data_provider.format_health_for_slack(health)
        )

# Check every 5 minutes
scheduler.add_job(monitor_health, 'interval', minutes=5)
scheduler.start()
```

## Error Handling

The health checker is designed to be fault-tolerant:

- Individual component failures don't crash the system
- Exceptions are caught and converted to UNHEALTHY status
- Detailed error messages are included in ComponentHealth
- Timeouts prevent hanging on unresponsive services

Example error handling:

```python
try:
    health = await data_provider.health_check()

    # Check for critical issues
    critical_components = ['database']

    for component in health.components:
        if component.name in critical_components:
            if component.status == HealthStatus.UNHEALTHY:
                logger.critical(
                    f"Critical component unhealthy: {component.name} - "
                    f"{component.error_message}"
                )
                await send_alert(component)

except Exception as e:
    logger.error(f"Health check failed: {e}")
    # Fallback to basic system check
```

## Testing

Run the test script to verify functionality:

```bash
python3 test_health_monitoring.py
```

This runs comprehensive tests:
1. Basic health check (database + APIs)
2. Health check with exchange clients
3. Custom threshold configuration
4. Caching behavior

## Performance

Typical performance metrics:

- **Database check**: 10-50ms
- **Exchange check**: 100-500ms per exchange
- **CoinGecko check**: 200-800ms
- **Sui monitor check**: 500-2000ms
- **Parallel exchange checks**: Max of all, not sum

With caching enabled, subsequent checks within 30 seconds return in < 1ms.

## Best Practices

1. **Use caching for frequent checks**: Enable `use_cache=True` for routine monitoring
2. **Bypass cache for critical checks**: Use `use_cache=False` when debugging
3. **Monitor all exchanges**: Include all exchange_clients for complete system view
4. **Set up alerts**: Monitor for UNHEALTHY status and send notifications
5. **Log health checks**: Record health check results for trend analysis
6. **Tune thresholds**: Adjust based on your network and API performance

## Future Enhancements

Potential improvements:
- Historical health metrics tracking
- Trend analysis and prediction
- Automated remediation actions
- Performance regression detection
- Health check dashboard UI
- Webhook notifications for status changes
