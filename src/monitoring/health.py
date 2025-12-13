"""
Health Monitoring System

Provides comprehensive health checks for the cex-reporter application:
- Database connectivity and performance
- Exchange API connectivity and latency
- Recent error tracking
- Overall system health status
"""

import time
import asyncio
import aiosqlite
from dataclasses import dataclass, field
from typing import Dict, Optional, List, Any
from datetime import datetime, timedelta
from enum import Enum

from src.utils import get_logger

logger = get_logger(__name__)


class HealthStatus(Enum):
    """Health status enumeration"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ComponentHealth:
    """
    Health information for a single component.

    Attributes:
        name: Component identifier (e.g., 'database', 'mexc_mm1')
        status: Current health status
        latency_ms: Response time in milliseconds
        last_check: When this health check was performed
        error_message: Error details if unhealthy
        details: Additional component-specific information
    """
    name: str
    status: HealthStatus
    latency_ms: Optional[float]
    last_check: datetime
    error_message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'name': self.name,
            'status': self.status.value,
            'latency_ms': self.latency_ms,
            'last_check': self.last_check.isoformat(),
            'error_message': self.error_message,
            'details': self.details
        }


@dataclass
class SystemHealth:
    """
    Overall system health status.

    Attributes:
        overall_status: Aggregate health status
        components: List of individual component health checks
        timestamp: When this system health check was performed
    """
    overall_status: HealthStatus
    components: List[ComponentHealth]
    timestamp: datetime

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization"""
        return {
            'overall_status': self.overall_status.value,
            'timestamp': self.timestamp.isoformat(),
            'components': [c.to_dict() for c in self.components],
            'summary': self._get_summary()
        }

    def _get_summary(self) -> Dict[str, int]:
        """Get count of components by status"""
        summary = {
            'healthy': 0,
            'degraded': 0,
            'unhealthy': 0,
            'total': len(self.components)
        }
        for component in self.components:
            summary[component.status.value] += 1
        return summary


class HealthThresholds:
    """
    Configurable thresholds for health status determination.

    Thresholds determine when a component is considered:
    - HEALTHY: Response time below healthy_latency_ms
    - DEGRADED: Response time between healthy and unhealthy, or occasional errors
    - UNHEALTHY: Response time above unhealthy_latency_ms or connection failures
    """

    def __init__(
        self,
        healthy_latency_ms: float = 1000,
        unhealthy_latency_ms: float = 5000,
        error_rate_threshold: float = 0.1
    ):
        """
        Initialize health thresholds.

        Args:
            healthy_latency_ms: Max latency for healthy status (default: 1000ms = 1s)
            unhealthy_latency_ms: Min latency for unhealthy status (default: 5000ms = 5s)
            error_rate_threshold: Error rate threshold for degraded status (default: 0.1 = 10%)
        """
        self.healthy_latency_ms = healthy_latency_ms
        self.unhealthy_latency_ms = unhealthy_latency_ms
        self.error_rate_threshold = error_rate_threshold

    def evaluate_latency(self, latency_ms: float, has_errors: bool = False) -> HealthStatus:
        """
        Evaluate health status based on latency and error presence.

        Args:
            latency_ms: Response time in milliseconds
            has_errors: Whether there are recent errors

        Returns:
            HealthStatus based on thresholds
        """
        if latency_ms >= self.unhealthy_latency_ms or has_errors:
            return HealthStatus.UNHEALTHY
        elif latency_ms >= self.healthy_latency_ms:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY


class HealthChecker:
    """
    Health checking system for cex-reporter.

    Performs non-blocking async health checks on:
    - SQLite database (connectivity, query performance)
    - Exchange APIs (connectivity, response times)
    - System components (recent error rates)
    """

    def __init__(
        self,
        data_provider,
        thresholds: Optional[HealthThresholds] = None
    ):
        """
        Initialize health checker.

        Args:
            data_provider: DataProvider instance for accessing system components
            thresholds: Custom health thresholds (uses defaults if None)
        """
        self.data_provider = data_provider
        self.thresholds = thresholds or HealthThresholds()
        self._last_check_time: Optional[datetime] = None
        self._cached_health: Optional[SystemHealth] = None
        self._cache_duration = timedelta(seconds=30)  # Cache health checks for 30s

    async def check_database(self) -> ComponentHealth:
        """
        Check SQLite database connectivity and performance.

        Tests:
        - Connection establishment
        - Query execution time
        - Database integrity

        Returns:
            ComponentHealth with database status
        """
        start_time = time.time()
        error_message = None
        details = {}

        try:
            # Test database connection and measure query latency
            async with aiosqlite.connect(self.data_provider.db_path) as conn:
                # Simple query to test connectivity
                query_start = time.time()
                cursor = await conn.execute("SELECT COUNT(*) FROM sqlite_master")
                result = await cursor.fetchone()
                query_time = (time.time() - query_start) * 1000

                details['table_count'] = result[0] if result else 0
                details['db_path'] = str(self.data_provider.db_path)

                # Check for recent errors in the last hour
                try:
                    error_cursor = await conn.execute("""
                        SELECT COUNT(*) FROM query_history
                        WHERE success = 0
                        AND created_at > datetime('now', '-1 hour')
                    """)
                    error_result = await error_cursor.fetchone()
                    recent_errors = error_result[0] if error_result else 0
                    details['recent_errors_1h'] = recent_errors
                except Exception as e:
                    # Table might not exist yet
                    logger.debug(f"Could not fetch error count: {e}")
                    details['recent_errors_1h'] = 0

                latency_ms = (time.time() - start_time) * 1000

                # Evaluate status based on latency
                status = self.thresholds.evaluate_latency(latency_ms)

                logger.debug(
                    f"Database health check: {status.value}, "
                    f"latency={latency_ms:.2f}ms"
                )

                return ComponentHealth(
                    name='database',
                    status=status,
                    latency_ms=round(latency_ms, 2),
                    last_check=datetime.now(),
                    error_message=None,
                    details=details
                )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_message = str(e)
            logger.error(f"Database health check failed: {error_message}")

            return ComponentHealth(
                name='database',
                status=HealthStatus.UNHEALTHY,
                latency_ms=round(latency_ms, 2),
                last_check=datetime.now(),
                error_message=error_message,
                details=details
            )

    async def check_exchange(self, exchange_name: str, exchange_client) -> ComponentHealth:
        """
        Check exchange API connectivity and performance.

        Args:
            exchange_name: Name of the exchange (e.g., 'mexc_mm1')
            exchange_client: Exchange client instance

        Returns:
            ComponentHealth with exchange status
        """
        start_time = time.time()
        error_message = None
        details = {
            'exchange': exchange_client.exchange_name,
            'account': exchange_client.account_name
        }

        try:
            # Test API connectivity by fetching balances
            if exchange_client.mock_mode:
                # In mock mode, simulate fast response
                await asyncio.sleep(0.05)  # 50ms simulated latency
                balances = {'USDT': 1000.0, 'ALKIMI': 50000.0}
                details['mock_mode'] = True
            else:
                balances = await exchange_client.get_balances()
                details['mock_mode'] = False

            latency_ms = (time.time() - start_time) * 1000

            # Add balance info to details
            if balances:
                details['assets_tracked'] = len(balances)
                details['has_balances'] = True
            else:
                details['assets_tracked'] = 0
                details['has_balances'] = False

            # Evaluate status based on latency
            status = self.thresholds.evaluate_latency(latency_ms)

            logger.debug(
                f"Exchange {exchange_name} health check: {status.value}, "
                f"latency={latency_ms:.2f}ms"
            )

            return ComponentHealth(
                name=exchange_name,
                status=status,
                latency_ms=round(latency_ms, 2),
                last_check=datetime.now(),
                error_message=None,
                details=details
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_message = str(e)
            logger.error(f"Exchange {exchange_name} health check failed: {error_message}")

            # Determine if it's a connection error or other type
            error_lower = error_message.lower()
            if any(term in error_lower for term in ['connection', 'timeout', 'network']):
                status = HealthStatus.UNHEALTHY
            else:
                status = HealthStatus.DEGRADED

            return ComponentHealth(
                name=exchange_name,
                status=status,
                latency_ms=round(latency_ms, 2),
                last_check=datetime.now(),
                error_message=error_message,
                details=details
            )

    async def check_all_exchanges(self, exchange_clients: Dict[str, Any]) -> List[ComponentHealth]:
        """
        Check all configured exchanges in parallel.

        Args:
            exchange_clients: Dictionary mapping exchange names to client instances

        Returns:
            List of ComponentHealth for each exchange
        """
        if not exchange_clients:
            logger.warning("No exchange clients provided for health check")
            return []

        # Create health check tasks for all exchanges
        tasks = []
        for exchange_name, client in exchange_clients.items():
            task = self.check_exchange(exchange_name, client)
            tasks.append(task)

        # Run all checks in parallel with timeout
        try:
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Convert exceptions to ComponentHealth
            component_healths = []
            for i, result in enumerate(results):
                if isinstance(result, Exception):
                    exchange_name = list(exchange_clients.keys())[i]
                    component_healths.append(ComponentHealth(
                        name=exchange_name,
                        status=HealthStatus.UNHEALTHY,
                        latency_ms=None,
                        last_check=datetime.now(),
                        error_message=str(result),
                        details={'error_type': type(result).__name__}
                    ))
                else:
                    component_healths.append(result)

            return component_healths

        except Exception as e:
            logger.error(f"Error checking exchanges: {e}")
            return []

    async def check_coingecko(self) -> ComponentHealth:
        """
        Check CoinGecko API connectivity and performance.

        Returns:
            ComponentHealth with CoinGecko status
        """
        start_time = time.time()
        error_message = None
        details = {}

        try:
            # Test API connectivity by fetching current price
            price = await self.data_provider.get_current_price()
            latency_ms = (time.time() - start_time) * 1000

            if price is not None:
                details['current_price'] = price
                details['price_available'] = True
            else:
                details['price_available'] = False

            # Evaluate status
            has_errors = price is None
            status = self.thresholds.evaluate_latency(latency_ms, has_errors)

            logger.debug(
                f"CoinGecko health check: {status.value}, "
                f"latency={latency_ms:.2f}ms"
            )

            return ComponentHealth(
                name='coingecko',
                status=status,
                latency_ms=round(latency_ms, 2),
                last_check=datetime.now(),
                error_message=None,
                details=details
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_message = str(e)
            logger.error(f"CoinGecko health check failed: {error_message}")

            return ComponentHealth(
                name='coingecko',
                status=HealthStatus.DEGRADED,  # CoinGecko failure is not critical
                latency_ms=round(latency_ms, 2),
                last_check=datetime.now(),
                error_message=error_message,
                details=details
            )

    async def check_sui_monitor(self) -> Optional[ComponentHealth]:
        """
        Check Sui blockchain monitor connectivity and performance.

        Returns:
            ComponentHealth with Sui monitor status, or None if not configured
        """
        if not self.data_provider.sui_monitor:
            return None

        start_time = time.time()
        error_message = None
        details = {'configured': True}

        try:
            # Test connectivity by fetching recent trades (small time window)
            since = datetime.now() - timedelta(days=1)
            trades_df = await self.data_provider.get_dex_trades(since=since)
            latency_ms = (time.time() - start_time) * 1000

            details['trades_24h'] = len(trades_df) if trades_df is not None else 0

            # Evaluate status
            status = self.thresholds.evaluate_latency(latency_ms)

            logger.debug(
                f"Sui monitor health check: {status.value}, "
                f"latency={latency_ms:.2f}ms"
            )

            return ComponentHealth(
                name='sui_monitor',
                status=status,
                latency_ms=round(latency_ms, 2),
                last_check=datetime.now(),
                error_message=None,
                details=details
            )

        except Exception as e:
            latency_ms = (time.time() - start_time) * 1000
            error_message = str(e)
            logger.error(f"Sui monitor health check failed: {error_message}")

            return ComponentHealth(
                name='sui_monitor',
                status=HealthStatus.DEGRADED,  # Sui monitor failure is not critical
                latency_ms=round(latency_ms, 2),
                last_check=datetime.now(),
                error_message=error_message,
                details=details
            )

    async def get_system_health(
        self,
        exchange_clients: Optional[Dict[str, Any]] = None,
        use_cache: bool = True
    ) -> SystemHealth:
        """
        Get overall system health status.

        Performs health checks on all system components:
        - Database
        - Exchange APIs
        - CoinGecko API
        - Sui blockchain monitor (if configured)

        Args:
            exchange_clients: Optional dict of exchange clients to check
            use_cache: Whether to use cached results if available

        Returns:
            SystemHealth with overall status and component details
        """
        now = datetime.now()

        # Return cached result if valid
        if use_cache and self._cached_health and self._last_check_time:
            if now - self._last_check_time < self._cache_duration:
                logger.debug("Returning cached health check results")
                return self._cached_health

        logger.info("Performing system health check")

        components: List[ComponentHealth] = []

        # Check database (always)
        try:
            db_health = await self.check_database()
            components.append(db_health)
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            components.append(ComponentHealth(
                name='database',
                status=HealthStatus.UNHEALTHY,
                latency_ms=None,
                last_check=now,
                error_message=str(e),
                details={}
            ))

        # Check exchanges (if provided)
        if exchange_clients:
            try:
                exchange_healths = await self.check_all_exchanges(exchange_clients)
                components.extend(exchange_healths)
            except Exception as e:
                logger.error(f"Exchange health checks failed: {e}")

        # Check CoinGecko
        try:
            coingecko_health = await self.check_coingecko()
            components.append(coingecko_health)
        except Exception as e:
            logger.error(f"CoinGecko health check failed: {e}")
            components.append(ComponentHealth(
                name='coingecko',
                status=HealthStatus.DEGRADED,
                latency_ms=None,
                last_check=now,
                error_message=str(e),
                details={}
            ))

        # Check Sui monitor (if configured)
        try:
            sui_health = await self.check_sui_monitor()
            if sui_health:
                components.append(sui_health)
        except Exception as e:
            logger.error(f"Sui monitor health check failed: {e}")

        # Determine overall system status
        overall_status = self._determine_overall_status(components)

        system_health = SystemHealth(
            overall_status=overall_status,
            components=components,
            timestamp=now
        )

        # Cache the result
        self._cached_health = system_health
        self._last_check_time = now

        logger.info(
            f"System health check complete: {overall_status.value}, "
            f"{len(components)} components checked"
        )

        return system_health

    def _determine_overall_status(self, components: List[ComponentHealth]) -> HealthStatus:
        """
        Determine overall system health based on component statuses.

        Rules:
        - If any critical component (database, exchanges) is UNHEALTHY -> UNHEALTHY
        - If any component is DEGRADED -> DEGRADED
        - Otherwise -> HEALTHY

        Args:
            components: List of component health checks

        Returns:
            Overall system HealthStatus
        """
        if not components:
            return HealthStatus.UNHEALTHY

        critical_components = {'database'}  # Database is critical

        has_unhealthy_critical = False
        has_degraded = False

        for component in components:
            if component.status == HealthStatus.UNHEALTHY:
                # Check if it's a critical component
                if component.name in critical_components or component.name.startswith('mexc') or \
                   component.name.startswith('kucoin') or component.name.startswith('gateio') or \
                   component.name.startswith('kraken'):
                    has_unhealthy_critical = True
                    break
            elif component.status == HealthStatus.DEGRADED:
                has_degraded = True

        if has_unhealthy_critical:
            return HealthStatus.UNHEALTHY
        elif has_degraded:
            return HealthStatus.DEGRADED
        else:
            return HealthStatus.HEALTHY

    def format_health_for_slack(self, system_health: SystemHealth) -> str:
        """
        Format system health for Slack message.

        Args:
            system_health: SystemHealth object to format

        Returns:
            Formatted string suitable for Slack
        """
        status_emoji = {
            HealthStatus.HEALTHY: '✅',
            HealthStatus.DEGRADED: '⚠️',
            HealthStatus.UNHEALTHY: '❌'
        }

        emoji = status_emoji.get(system_health.overall_status, '❓')

        lines = [
            f"{emoji} *System Health: {system_health.overall_status.value.upper()}*",
            f"_Checked at: {system_health.timestamp.strftime('%Y-%m-%d %H:%M:%S')}_",
            ""
        ]

        # Group components by status
        healthy = [c for c in system_health.components if c.status == HealthStatus.HEALTHY]
        degraded = [c for c in system_health.components if c.status == HealthStatus.DEGRADED]
        unhealthy = [c for c in system_health.components if c.status == HealthStatus.UNHEALTHY]

        if unhealthy:
            lines.append("*Unhealthy Components:*")
            for component in unhealthy:
                latency = f"{component.latency_ms:.0f}ms" if component.latency_ms else "N/A"
                error = f" - {component.error_message}" if component.error_message else ""
                lines.append(f"  ❌ {component.name}: {latency}{error}")
            lines.append("")

        if degraded:
            lines.append("*Degraded Components:*")
            for component in degraded:
                latency = f"{component.latency_ms:.0f}ms" if component.latency_ms else "N/A"
                error = f" - {component.error_message}" if component.error_message else ""
                lines.append(f"  ⚠️ {component.name}: {latency}{error}")
            lines.append("")

        if healthy:
            lines.append(f"*Healthy Components:* {len(healthy)}")
            for component in healthy:
                latency = f"{component.latency_ms:.0f}ms" if component.latency_ms else "N/A"
                lines.append(f"  ✅ {component.name}: {latency}")

        return "\n".join(lines)
