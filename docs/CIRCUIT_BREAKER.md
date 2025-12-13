# Circuit Breaker Pattern Implementation

## Overview

The Circuit Breaker pattern is implemented to prevent cascade failures when exchanges or external services are temporarily unavailable. It automatically detects failures, stops making requests to failing services, and tests for recovery.

## Architecture

### Components

1. **CircuitBreaker** (`src/utils/circuit_breaker.py`)
   - Core implementation of the circuit breaker pattern
   - Manages state transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
   - Tracks failure/success counts
   - Provides automatic recovery testing

2. **CircuitBreakerManager** (`src/utils/circuit_breaker.py`)
   - Manages multiple circuit breakers
   - Provides centralized status monitoring
   - Supports bulk operations (reset all, get status)

3. **Integration with CCXTExchangeClient** (`src/exchanges/base.py`)
   - Each exchange client has its own circuit breaker
   - Automatic protection for all API calls
   - Configurable thresholds per exchange

## Circuit States

### CLOSED (Normal Operation)
- All requests pass through normally
- Failures are counted
- Transitions to OPEN when failure threshold is reached

```
Normal Operation → Failures accumulate → Threshold reached → OPEN
```

### OPEN (Failing)
- All requests are immediately rejected (fast-fail)
- No requests are sent to the failing service
- After recovery timeout, transitions to HALF_OPEN

```
OPEN → Recovery timeout expires → HALF_OPEN
```

### HALF_OPEN (Testing Recovery)
- Limited requests are allowed to test if service recovered
- Success: count successes, transition to CLOSED after threshold
- Failure: immediately return to OPEN

```
HALF_OPEN → Successes reach threshold → CLOSED
HALF_OPEN → Any failure → OPEN
```

## Configuration

### CircuitBreakerConfig

```python
from src.utils.circuit_breaker import CircuitBreakerConfig

config = CircuitBreakerConfig(
    failure_threshold=5,      # Failures before opening circuit
    recovery_timeout=60,      # Seconds before testing recovery
    success_threshold=2,      # Successes needed to close circuit
    timeout=30.0             # Optional timeout per call (seconds)
)
```

### Default Configuration

```python
CircuitBreakerConfig(
    failure_threshold=5,
    recovery_timeout=60,
    success_threshold=2,
    timeout=None
)
```

## Usage

### Basic Usage

```python
from src.utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig

# Create circuit breaker
circuit = CircuitBreaker("my_service", config=CircuitBreakerConfig(
    failure_threshold=3,
    recovery_timeout=30
))

# Use circuit breaker
try:
    result = await circuit.call(api_function, arg1, arg2)
    print(f"Success: {result}")
except CircuitBreakerOpenError:
    print("Service is down, using fallback")
    result = get_fallback_data()
except Exception as e:
    print(f"API error: {e}")
```

### Integration with Exchanges

The circuit breaker is automatically integrated into all exchange clients:

```python
from src.exchanges.mexc import MEXCClient

# Circuit breaker is initialized automatically
client = MEXCClient(config, mock_mode=False)

try:
    # All API calls are protected by circuit breaker
    balances = await client.get_balances()
except CircuitBreakerOpenError:
    logger.warning("MEXC is down, skipping...")
```

### Monitoring Circuit Status

```python
# Get status of a specific exchange
status = exchange_client.get_circuit_status()
print(f"State: {status['state']}")
print(f"Failures: {status['failure_count']}")
print(f"Time in state: {status['time_in_current_state']}s")

# If circuit is OPEN
if status['state'] == 'open':
    print(f"Recovery in: {status['recovery_in_seconds']}s")
```

### Using CircuitBreakerManager

```python
from src.utils.circuit_breaker import CircuitBreakerManager

manager = CircuitBreakerManager()

# Get circuits for different services
mexc_circuit = manager.get_circuit("mexc_api")
kraken_circuit = manager.get_circuit("kraken_api")

# Get overall status
status = manager.get_status()
print(f"Total circuits: {status['total_circuits']}")
print(f"Healthy: {status['healthy_count']}")
print(f"Failing: {status['failing_count']}")

# Get circuits that are open
open_circuits = manager.get_open_circuits()
print(f"Down services: {open_circuits}")

# Reset a specific circuit
manager.reset_circuit("mexc_api")

# Reset all circuits
manager.reset_all()
```

## Benefits

### 1. Fast Fail
When an exchange is down, requests fail immediately without waiting for timeouts:

```
Without Circuit Breaker: Each request waits 30s timeout = 300s for 10 requests
With Circuit Breaker:    First 5 requests fail, rest fast-fail = ~150s total
```

### 2. Automatic Recovery
Circuits automatically test for recovery without manual intervention:

```
OPEN (60s) → HALF_OPEN (test) → CLOSED (if successful)
```

### 3. Prevents Cascade Failures
Failing fast prevents:
- Thread pool exhaustion
- Memory buildup from queued requests
- Timeout-induced delays cascading to other services

### 4. Improved User Experience
- Faster error responses
- Predictable failure behavior
- Graceful degradation

## Configuration Guidelines

### Conservative (Production)
```python
CircuitBreakerConfig(
    failure_threshold=5,     # Allow some failures
    recovery_timeout=120,    # Wait 2 minutes
    success_threshold=3      # Need multiple successes
)
```

### Aggressive (High-Traffic)
```python
CircuitBreakerConfig(
    failure_threshold=3,     # Open quickly
    recovery_timeout=30,     # Test recovery sooner
    success_threshold=2      # Recover faster
)
```

### Testing/Development
```python
CircuitBreakerConfig(
    failure_threshold=2,     # Open quickly
    recovery_timeout=5,      # Short recovery window
    success_threshold=1      # Close quickly
)
```

## Error Handling

### CircuitBreakerOpenError

When a circuit is OPEN, calls raise `CircuitBreakerOpenError`:

```python
from src.utils.circuit_breaker import CircuitBreakerOpenError

try:
    result = await exchange.get_balances()
except CircuitBreakerOpenError as e:
    # Circuit is open - service is known to be down
    logger.warning(f"Exchange unavailable: {e}")
    # Use cached data or skip this exchange
    return cached_balances
except Exception as e:
    # Actual API error - circuit will track this
    logger.error(f"API error: {e}")
    raise
```

### Best Practices

1. **Always catch CircuitBreakerOpenError separately**
   ```python
   try:
       data = await circuit.call(api_func)
   except CircuitBreakerOpenError:
       # Handle known outage
       return fallback_data
   except Exception:
       # Handle unexpected errors
       raise
   ```

2. **Don't reset circuits manually unless necessary**
   - Let automatic recovery work
   - Manual resets can cause repeated failures

3. **Monitor circuit states in production**
   - Log state transitions
   - Alert on prolonged OPEN states
   - Track recovery success rates

4. **Use appropriate timeouts**
   ```python
   CircuitBreakerConfig(
       timeout=10.0  # Fail fast on slow responses
   )
   ```

## Testing

Run the circuit breaker tests:

```bash
python3 test_circuit_breaker_standalone.py
```

This tests:
- State transitions (CLOSED → OPEN → HALF_OPEN → CLOSED)
- Failure threshold detection
- Recovery timeout behavior
- Fast-fail while OPEN
- Timeout protection
- Automatic recovery

## Metrics and Monitoring

### Key Metrics to Track

1. **Circuit State Duration**
   - How long circuits stay in each state
   - Long OPEN periods indicate persistent issues

2. **State Transition Frequency**
   - Frequent CLOSED→OPEN→CLOSED indicates flaky services
   - Should investigate root cause

3. **Fast-Fail Count**
   - Number of requests rejected while OPEN
   - Indicates protection effectiveness

4. **Recovery Success Rate**
   - How often HALF_OPEN → CLOSED (successful recovery)
   - vs HALF_OPEN → OPEN (failed recovery)

### Logging

All state transitions are automatically logged:

```
INFO - Circuit 'mexc_main': CLOSED -> OPEN (threshold reached)
INFO - Circuit 'mexc_main': OPEN -> HALF_OPEN (attempting recovery)
INFO - Circuit 'mexc_main': HALF_OPEN -> CLOSED (recovered)
```

## Integration Points

### Current Integrations

1. **CCXTExchangeClient** (`src/exchanges/base.py`)
   - All CCXT-based exchanges (MEXC, Kraken, KuCoin, Gate.io)
   - Automatic protection for:
     - `get_balances()`
     - `get_trades()`
     - `get_deposits()`
     - `get_withdrawals()`
     - `get_prices()`

### Future Integration Opportunities

1. **Database connections**
2. **External API services** (price feeds, etc.)
3. **File system operations** (for network drives)
4. **Third-party integrations**

## Troubleshooting

### Circuit keeps opening

**Problem:** Circuit frequently transitions to OPEN

**Solutions:**
1. Increase `failure_threshold`
2. Check if exchange is actually having issues
3. Verify network connectivity
4. Check rate limits aren't being exceeded

### Circuit won't close after recovery

**Problem:** Circuit stays OPEN even though service is up

**Solutions:**
1. Wait for full `recovery_timeout` period
2. Check `success_threshold` isn't too high
3. Manually reset circuit if confident service is healthy:
   ```python
   exchange_client.reset_circuit()
   ```

### Too many fast-fails

**Problem:** Circuit is too sensitive

**Solutions:**
1. Increase `failure_threshold`
2. Increase `recovery_timeout`
3. Review what constitutes a "failure" in your context

## Performance Impact

### Memory Usage
- Minimal: ~1KB per circuit breaker
- State tracking: O(1) memory

### CPU Impact
- Negligible: Simple state checks and counters
- No background threads or polling

### Latency
- CLOSED: No additional latency
- OPEN: Saves time by failing fast (no network call)
- HALF_OPEN: Normal latency for test requests

## References

- [Martin Fowler - Circuit Breaker](https://martinfowler.com/bliki/CircuitBreaker.html)
- [Microsoft - Circuit Breaker Pattern](https://docs.microsoft.com/en-us/azure/architecture/patterns/circuit-breaker)
- [Release It! - Michael Nygard](https://pragprog.com/titles/mnee2/release-it-second-edition/)
