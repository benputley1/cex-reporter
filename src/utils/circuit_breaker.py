"""
Circuit Breaker Pattern Module

Implements the circuit breaker pattern to prevent cascade failures when
exchanges or services are down. Automatically opens circuits after threshold
failures and allows recovery testing after timeout periods.

States:
- CLOSED: Normal operation, calls pass through
- OPEN: Service failing, calls rejected immediately
- HALF_OPEN: Testing if service recovered

Usage:
    circuit = CircuitBreaker("mexc_api", config=CircuitBreakerConfig(
        failure_threshold=5,
        recovery_timeout=60,
        success_threshold=2
    ))

    result = await circuit.call(exchange.get_balances)
"""

import asyncio
from datetime import datetime, timedelta
from typing import Callable, Optional, Dict, Any
from enum import Enum
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject all calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """
    Configuration for circuit breaker behavior.

    Attributes:
        failure_threshold: Number of consecutive failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery (OPEN -> HALF_OPEN)
        success_threshold: Number of successes needed to close from HALF_OPEN
        timeout: Optional timeout in seconds for individual calls
    """
    failure_threshold: int = 5       # Failures before opening
    recovery_timeout: int = 60       # Seconds before half-open
    success_threshold: int = 2       # Successes to close from half-open
    timeout: Optional[float] = None  # Call timeout in seconds


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open and call is rejected."""
    pass


class CircuitBreaker:
    """
    Circuit breaker pattern for exchange API calls.

    Protects against cascade failures by:
    1. Tracking failure rates
    2. Opening circuit after threshold failures
    3. Rejecting calls while open (fail-fast)
    4. Testing recovery after timeout period
    5. Closing circuit after successful recovery

    Example:
        circuit = CircuitBreaker("exchange_api")

        try:
            result = await circuit.call(api_function, arg1, arg2)
        except CircuitBreakerOpenError:
            # Circuit is open, service is down
            return fallback_value
    """

    def __init__(self, name: str, config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker.

        Args:
            name: Identifier for this circuit (e.g., "mexc_api", "kraken_trades")
            config: Configuration for circuit behavior
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.last_state_change: datetime = datetime.now()
        self._lock = asyncio.Lock()  # Thread-safe state updates

        logger.info(
            f"Circuit breaker '{name}' initialized: "
            f"failure_threshold={self.config.failure_threshold}, "
            f"recovery_timeout={self.config.recovery_timeout}s, "
            f"success_threshold={self.config.success_threshold}"
        )

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func execution

        Raises:
            CircuitBreakerOpenError: If circuit is OPEN and not ready for recovery
            Exception: Any exception raised by func (if circuit is not OPEN)
        """
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    self._transition_to_half_open()
                else:
                    elapsed = (datetime.now() - self.last_failure_time).seconds
                    remaining = self.config.recovery_timeout - elapsed
                    raise CircuitBreakerOpenError(
                        f"Circuit '{self.name}' is OPEN. "
                        f"Recovery attempt in {remaining}s."
                    )

        # Execute the function call
        try:
            # Apply timeout if configured
            if self.config.timeout:
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=self.config.timeout
                )
            else:
                result = await func(*args, **kwargs)

            await self._on_success()
            return result

        except asyncio.TimeoutError as e:
            await self._on_failure()
            raise Exception(f"Circuit '{self.name}': Call timeout after {self.config.timeout}s") from e

        except Exception as e:
            await self._on_failure()
            raise

    def _should_attempt_recovery(self) -> bool:
        """
        Check if recovery timeout has passed.

        Returns:
            True if enough time has passed to attempt recovery
        """
        if self.last_failure_time is None:
            return True

        elapsed = (datetime.now() - self.last_failure_time).seconds
        return elapsed >= self.config.recovery_timeout

    def _transition_to_half_open(self):
        """Transition from OPEN to HALF_OPEN state."""
        self.state = CircuitState.HALF_OPEN
        self.success_count = 0
        self.last_state_change = datetime.now()

        logger.info(
            f"Circuit '{self.name}': OPEN -> HALF_OPEN "
            f"(attempting recovery after {self.config.recovery_timeout}s)"
        )

    async def _on_success(self):
        """Handle successful call."""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                logger.debug(
                    f"Circuit '{self.name}': Success in HALF_OPEN "
                    f"({self.success_count}/{self.config.success_threshold})"
                )

                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    self.success_count = 0
                    self.last_state_change = datetime.now()

                    logger.info(
                        f"Circuit '{self.name}': HALF_OPEN -> CLOSED "
                        f"(recovered after {self.config.success_threshold} successes)"
                    )

            elif self.state == CircuitState.CLOSED:
                # Reset failure count on success in normal operation
                if self.failure_count > 0:
                    logger.debug(
                        f"Circuit '{self.name}': Resetting failure count "
                        f"(was {self.failure_count})"
                    )
                    self.failure_count = 0

    async def _on_failure(self):
        """Handle failed call."""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.now()

            if self.state == CircuitState.HALF_OPEN:
                # Failed during recovery test - back to OPEN
                self.state = CircuitState.OPEN
                self.success_count = 0
                self.last_state_change = datetime.now()

                logger.warning(
                    f"Circuit '{self.name}': HALF_OPEN -> OPEN "
                    f"(recovery failed, still unhealthy)"
                )

            elif self.state == CircuitState.CLOSED:
                logger.debug(
                    f"Circuit '{self.name}': Failure {self.failure_count}/"
                    f"{self.config.failure_threshold}"
                )

                if self.failure_count >= self.config.failure_threshold:
                    self.state = CircuitState.OPEN
                    self.last_state_change = datetime.now()

                    logger.warning(
                        f"Circuit '{self.name}': CLOSED -> OPEN "
                        f"(failure threshold {self.config.failure_threshold} reached)"
                    )

    def get_status(self) -> Dict[str, Any]:
        """
        Get current circuit breaker status.

        Returns:
            Dictionary with state, counts, and timing information
        """
        status = {
            'name': self.name,
            'state': self.state.value,
            'failure_count': self.failure_count,
            'success_count': self.success_count,
            'config': {
                'failure_threshold': self.config.failure_threshold,
                'recovery_timeout': self.config.recovery_timeout,
                'success_threshold': self.config.success_threshold,
            }
        }

        if self.last_failure_time:
            status['last_failure_time'] = self.last_failure_time.isoformat()
            status['seconds_since_failure'] = (
                datetime.now() - self.last_failure_time
            ).seconds

        if self.state == CircuitState.OPEN:
            elapsed = (datetime.now() - self.last_failure_time).seconds
            status['recovery_in_seconds'] = max(
                0,
                self.config.recovery_timeout - elapsed
            )

        status['last_state_change'] = self.last_state_change.isoformat()
        status['time_in_current_state'] = (
            datetime.now() - self.last_state_change
        ).seconds

        return status

    def reset(self):
        """
        Manually reset circuit breaker to CLOSED state.

        Use with caution - only reset if you're certain the service is healthy.
        """
        logger.info(f"Circuit '{self.name}': Manual reset to CLOSED")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.last_state_change = datetime.now()


class CircuitBreakerManager:
    """
    Manages circuit breakers for multiple exchanges/services.

    Provides centralized access to circuit breakers and status monitoring
    across all managed circuits.

    Example:
        manager = CircuitBreakerManager()

        # Get or create circuit for an exchange
        circuit = manager.get_circuit("mexc_api")

        # Check status of all circuits
        status = manager.get_status()
        print(f"Healthy circuits: {status['healthy_count']}")
    """

    def __init__(self):
        """Initialize circuit breaker manager."""
        self._circuits: Dict[str, CircuitBreaker] = {}
        self._default_config = CircuitBreakerConfig()
        logger.info("Circuit breaker manager initialized")

    def get_circuit(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        Get or create a circuit breaker.

        Args:
            name: Circuit identifier
            config: Optional configuration (uses default if not provided)

        Returns:
            CircuitBreaker instance
        """
        if name not in self._circuits:
            self._circuits[name] = CircuitBreaker(
                name,
                config or self._default_config
            )
        return self._circuits[name]

    def get_status(self) -> Dict[str, Any]:
        """
        Get status of all managed circuits.

        Returns:
            Dictionary with overall status and per-circuit details
        """
        circuits_status = {}
        states_count = {
            'closed': 0,
            'open': 0,
            'half_open': 0
        }

        for name, circuit in self._circuits.items():
            status = circuit.get_status()
            circuits_status[name] = status
            states_count[status['state']] += 1

        return {
            'total_circuits': len(self._circuits),
            'healthy_count': states_count['closed'],
            'failing_count': states_count['open'],
            'recovering_count': states_count['half_open'],
            'circuits': circuits_status
        }

    def get_open_circuits(self) -> list[str]:
        """
        Get list of circuits currently in OPEN state.

        Returns:
            List of circuit names that are OPEN
        """
        return [
            name for name, circuit in self._circuits.items()
            if circuit.state == CircuitState.OPEN
        ]

    def reset_circuit(self, name: str):
        """
        Manually reset a specific circuit.

        Args:
            name: Circuit identifier to reset

        Raises:
            KeyError: If circuit doesn't exist
        """
        if name not in self._circuits:
            raise KeyError(f"Circuit '{name}' not found")

        self._circuits[name].reset()

    def reset_all(self):
        """Reset all managed circuits to CLOSED state."""
        logger.info(f"Resetting all {len(self._circuits)} circuits")
        for circuit in self._circuits.values():
            circuit.reset()

    def set_default_config(self, config: CircuitBreakerConfig):
        """
        Set default configuration for new circuits.

        Args:
            config: Default configuration to use
        """
        self._default_config = config
        logger.info(
            f"Default circuit breaker config updated: "
            f"failure_threshold={config.failure_threshold}, "
            f"recovery_timeout={config.recovery_timeout}s"
        )
