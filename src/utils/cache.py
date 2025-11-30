"""
Cache Utility Module

Provides in-memory caching with TTL expiration and thread-safe operations.
Includes decorator for easy caching of function results.
"""

import time
import threading
from typing import Any, Optional, Callable, Dict
from functools import wraps
from datetime import datetime


class CacheEntry:
    """
    Represents a single cache entry with value and expiration time.

    Attributes:
        value: The cached value
        expires_at: Timestamp when this entry expires
    """

    def __init__(self, value: Any, ttl: int):
        """
        Initialize cache entry.

        Args:
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        self.value = value
        self.expires_at = time.time() + ttl

    def is_expired(self) -> bool:
        """Check if this cache entry has expired"""
        return time.time() > self.expires_at


class Cache:
    """
    Thread-safe in-memory cache with TTL expiration.

    Provides methods for getting, setting, and managing cached values
    with automatic expiration based on time-to-live (TTL).
    """

    def __init__(self, default_ttl: int = 60):
        """
        Initialize cache instance.

        Args:
            default_ttl: Default time-to-live for cache entries in seconds
        """
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = threading.Lock()
        self.default_ttl = default_ttl
        self._last_cleanup = time.time()
        self._cleanup_interval = 60  # Run cleanup every 60 seconds

    def get(self, key: str) -> Optional[Any]:
        """
        Get value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if exists and not expired, None otherwise
        """
        with self._lock:
            # Check if cleanup is needed
            self._maybe_cleanup()

            if key not in self._cache:
                return None

            entry = self._cache[key]

            # Check if expired
            if entry.is_expired():
                del self._cache[key]
                return None

            return entry.value

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set value in cache.

        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds (uses default_ttl if not specified)
        """
        if ttl is None:
            ttl = self.default_ttl

        with self._lock:
            self._cache[key] = CacheEntry(value, ttl)

    def has(self, key: str) -> bool:
        """
        Check if key exists in cache and is not expired.

        Args:
            key: Cache key

        Returns:
            True if key exists and is valid, False otherwise
        """
        return self.get(key) is not None

    def delete(self, key: str) -> bool:
        """
        Delete specific key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if key was deleted, False if key didn't exist
        """
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def clear(self) -> None:
        """Clear all entries from cache"""
        with self._lock:
            self._cache.clear()

    def size(self) -> int:
        """
        Get number of entries in cache (including expired).

        Returns:
            Number of cache entries
        """
        with self._lock:
            return len(self._cache)

    def cleanup(self) -> int:
        """
        Remove all expired entries from cache.

        Returns:
            Number of entries removed
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                del self._cache[key]

            self._last_cleanup = time.time()
            return len(expired_keys)

    def _maybe_cleanup(self) -> None:
        """
        Internal method to periodically cleanup expired entries.
        Called automatically during get operations.
        """
        if time.time() - self._last_cleanup > self._cleanup_interval:
            # Release lock temporarily to avoid blocking other operations
            expired_keys = [
                key for key, entry in self._cache.items()
                if entry.is_expired()
            ]

            for key in expired_keys:
                del self._cache[key]

            self._last_cleanup = time.time()

    def get_stats(self) -> Dict[str, Any]:
        """
        Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        with self._lock:
            total_entries = len(self._cache)
            expired_entries = sum(
                1 for entry in self._cache.values()
                if entry.is_expired()
            )
            valid_entries = total_entries - expired_entries

            return {
                'total_entries': total_entries,
                'valid_entries': valid_entries,
                'expired_entries': expired_entries,
                'default_ttl': self.default_ttl,
                'last_cleanup': datetime.fromtimestamp(self._last_cleanup).isoformat(),
            }


# Global cache instance
_global_cache = Cache()


def cached(ttl: int = 60, key_prefix: str = "") -> Callable:
    """
    Decorator to cache function results.

    Args:
        ttl: Time-to-live for cached result in seconds
        key_prefix: Optional prefix for cache key

    Returns:
        Decorated function with caching

    Example:
        @cached(ttl=300)
        async def get_prices(symbols):
            # Expensive API call
            return prices
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = _generate_cache_key(func, key_prefix, args, kwargs)

            # Try to get from cache
            cached_result = _global_cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Call function and cache result
            result = await func(*args, **kwargs)
            _global_cache.set(cache_key, result, ttl)

            return result

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            # Generate cache key from function name and arguments
            cache_key = _generate_cache_key(func, key_prefix, args, kwargs)

            # Try to get from cache
            cached_result = _global_cache.get(cache_key)
            if cached_result is not None:
                return cached_result

            # Call function and cache result
            result = func(*args, **kwargs)
            _global_cache.set(cache_key, result, ttl)

            return result

        # Return appropriate wrapper based on whether function is async
        import inspect
        if inspect.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


def _generate_cache_key(func: Callable, prefix: str, args: tuple, kwargs: dict) -> str:
    """
    Generate cache key from function and arguments.

    Args:
        func: Function being cached
        prefix: Key prefix
        args: Positional arguments
        kwargs: Keyword arguments

    Returns:
        Cache key string
    """
    import hashlib
    import json

    # Build key components
    func_name = func.__name__

    # Convert args and kwargs to string representation
    try:
        args_str = json.dumps(args, sort_keys=True, default=str)
        kwargs_str = json.dumps(kwargs, sort_keys=True, default=str)
    except (TypeError, ValueError):
        # Fallback to repr if JSON serialization fails
        args_str = repr(args)
        kwargs_str = repr(kwargs)

    # Create hash of arguments for compact key
    args_hash = hashlib.md5(f"{args_str}{kwargs_str}".encode()).hexdigest()[:8]

    # Combine components
    if prefix:
        return f"{prefix}:{func_name}:{args_hash}"
    else:
        return f"{func_name}:{args_hash}"


def get_cache() -> Cache:
    """
    Get the global cache instance.

    Returns:
        Global Cache instance
    """
    return _global_cache


def clear_cache() -> None:
    """Clear the global cache"""
    _global_cache.clear()
