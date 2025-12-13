"""
Retry Decorator Module

Provides exponential backoff retry logic for API calls with support for
rate limit headers and configurable retry behavior.
"""

import asyncio
import functools
import random
from typing import Callable, Any, Tuple, Type, Optional
from src.utils.logging import get_logger

logger = get_logger(__name__)


def retry_with_backoff(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    exponential_base: float = 2.0,
    max_delay: float = 60.0,
    retry_on: Optional[Tuple[Type[Exception], ...]] = None
):
    """
    Decorator for retrying async functions with exponential backoff.

    Retries on network errors and rate limit errors by default.
    Auth errors are NOT retried as they indicate configuration issues.
    Supports Retry-After headers from rate limit responses.

    Args:
        max_retries: Maximum number of retry attempts (default: 3)
        initial_delay: Initial delay in seconds before first retry (default: 1.0)
        exponential_base: Base for exponential backoff calculation (default: 2.0)
        max_delay: Maximum delay between retries in seconds (default: 60.0)
        retry_on: Tuple of exception types to retry on. If None, uses default exceptions.

    Returns:
        Decorated async function with retry logic

    Example:
        @retry_with_backoff(max_retries=3, initial_delay=1.0)
        async def fetch_data():
            return await exchange.get_balances()

    Retry Schedule (with default params):
        - Attempt 1 fails -> wait ~1s
        - Attempt 2 fails -> wait ~2s
        - Attempt 3 fails -> wait ~4s
        - Attempt 4 fails -> raise exception
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Import here to avoid circular dependency
            from src.exchanges.base import (
                ExchangeConnectionError,
                ExchangeRateLimitError,
                ExchangeAuthError
            )

            # Default exceptions to retry on
            if retry_on is None:
                default_retry_exceptions = (
                    ExchangeConnectionError,
                    ExchangeRateLimitError,
                )
            else:
                default_retry_exceptions = retry_on

            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)

                except ExchangeAuthError:
                    # Never retry auth errors - these indicate config issues
                    logger.error(
                        f"{func.__name__} failed with authentication error. "
                        "Check API credentials."
                    )
                    raise

                except default_retry_exceptions as e:
                    last_exception = e

                    if attempt < max_retries:
                        # Check for Retry-After header in rate limit errors
                        retry_after = _extract_retry_after(e)

                        if retry_after is not None:
                            # Use the Retry-After value from the server
                            actual_delay = min(retry_after, max_delay)
                            logger.warning(
                                f"{func.__name__} - Attempt {attempt + 1}/{max_retries} failed: {str(e)}. "
                                f"Server requested retry after {retry_after}s. "
                                f"Waiting {actual_delay:.2f}s..."
                            )
                        else:
                            # Calculate delay with exponential backoff
                            delay = min(
                                initial_delay * (exponential_base ** attempt),
                                max_delay
                            )

                            # Add jitter to prevent thundering herd
                            jitter = random.uniform(0, 0.1 * delay)
                            actual_delay = delay + jitter

                            logger.warning(
                                f"{func.__name__} - Attempt {attempt + 1}/{max_retries} failed: {str(e)}. "
                                f"Retrying in {actual_delay:.2f}s..."
                            )

                        await asyncio.sleep(actual_delay)
                    else:
                        # Max retries exceeded
                        logger.error(
                            f"Max retries ({max_retries}) exceeded for {func.__name__}. "
                            f"Last error: {str(e)}"
                        )
                        raise

                except Exception as e:
                    # Unexpected exception - don't retry
                    logger.error(
                        f"{func.__name__} failed with unexpected error: {str(e)}"
                    )
                    raise

            # Should never reach here, but just in case
            if last_exception:
                raise last_exception

        return wrapper
    return decorator


def _extract_retry_after(exception: Exception) -> Optional[float]:
    """
    Extract Retry-After value from exception if available.

    Checks for:
    1. Exception attributes containing retry_after or retryAfter
    2. HTTP response headers (if exception has response attribute)
    3. Error message parsing for common patterns

    Args:
        exception: Exception that may contain Retry-After information

    Returns:
        Number of seconds to wait, or None if not found
    """
    try:
        # Check exception attributes
        if hasattr(exception, 'retry_after'):
            return float(exception.retry_after)

        if hasattr(exception, 'retryAfter'):
            return float(exception.retryAfter)

        # Check HTTP response headers if available
        if hasattr(exception, 'response'):
            response = exception.response

            if hasattr(response, 'headers'):
                headers = response.headers

                # Check various header formats
                retry_after_keys = ['Retry-After', 'retry-after', 'X-Rate-Limit-Reset']

                for key in retry_after_keys:
                    if key in headers:
                        value = headers[key]

                        # Try to parse as float (seconds)
                        try:
                            return float(value)
                        except (ValueError, TypeError):
                            # Could be HTTP date format - ignore for now
                            pass

        # Check CCXT-specific rate limit info
        if hasattr(exception, 'args') and len(exception.args) > 0:
            error_msg = str(exception.args[0])

            # Try to extract number from common patterns
            # e.g., "Rate limit exceeded. Retry after 5 seconds"
            import re

            patterns = [
                r'retry after (\d+\.?\d*)',
                r'retry in (\d+\.?\d*)',
                r'wait (\d+\.?\d*) seconds',
            ]

            for pattern in patterns:
                match = re.search(pattern, error_msg.lower())
                if match:
                    return float(match.group(1))

    except Exception as e:
        # If we can't extract retry_after, just return None
        logger.debug(f"Could not extract Retry-After from exception: {e}")
        pass

    return None
