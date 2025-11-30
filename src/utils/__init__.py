"""Shared utility modules for caching and logging"""

from .cache import Cache, cached, get_cache, clear_cache
from .logging import (
    setup_logging,
    get_logger,
    get_contextual_logger,
    setup_from_config,
    log_with_data,
    JSONFormatter,
    ConsoleFormatter,
)
from .trade_deduplication import deduplicate_trades, analyze_trade_duplication

__all__ = [
    # Cache utilities
    'Cache',
    'cached',
    'get_cache',
    'clear_cache',
    # Logging utilities
    'setup_logging',
    'get_logger',
    'get_contextual_logger',
    'setup_from_config',
    'log_with_data',
    'JSONFormatter',
    'ConsoleFormatter',
    # Trade deduplication
    'deduplicate_trades',
    'analyze_trade_duplication',
]
