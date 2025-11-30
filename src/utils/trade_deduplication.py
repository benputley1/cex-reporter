"""
Trade Deduplication Utilities
Removes duplicate trades from linked sub-accounts.
"""

from typing import List, Set, Tuple
from src.exchanges.base import Trade
from src.utils import get_logger

logger = get_logger(__name__)


def deduplicate_trades(trades: List[Trade]) -> List[Trade]:
    """
    Remove duplicate trades from linked sub-accounts.

    Uses trade hash based on: (timestamp, symbol, side, amount, price)
    to identify duplicates. Keeps the first occurrence of each unique trade.

    Args:
        trades: List of Trade objects (may contain duplicates)

    Returns:
        List of unique Trade objects

    Example:
        >>> trades = fetch_all_trades()  # May have duplicates from sub-accounts
        >>> unique_trades = deduplicate_trades(trades)
        >>> print(f"Reduced from {len(trades)} to {len(unique_trades)} trades")
    """
    if not trades:
        return []

    seen: Set[Tuple] = set()
    unique_trades: List[Trade] = []
    duplicate_count = 0

    for trade in trades:
        # Create a hash of key trade attributes
        # Round to 8 decimal places to handle floating point precision issues
        trade_hash = (
            trade.timestamp.isoformat(),
            trade.symbol,
            trade.side.value,
            round(trade.amount, 8),
            round(trade.price, 8)
        )

        if trade_hash not in seen:
            seen.add(trade_hash)
            unique_trades.append(trade)
        else:
            duplicate_count += 1
            logger.debug(
                f"Duplicate trade detected: {trade.timestamp} {trade.side.value} "
                f"{trade.amount} {trade.symbol} @ {trade.price}"
            )

    if duplicate_count > 0:
        logger.info(
            f"Removed {duplicate_count} duplicate trades. "
            f"Original: {len(trades)}, Unique: {len(unique_trades)} "
            f"({duplicate_count / len(trades) * 100:.1f}% duplicates)"
        )
    else:
        logger.debug(f"No duplicate trades found in {len(trades)} trades")

    return unique_trades


def group_trades_by_exchange(trades: List[Trade]) -> dict:
    """
    Group trades by exchange for analysis.

    Args:
        trades: List of Trade objects

    Returns:
        Dictionary mapping exchange names to their trades
    """
    trades_by_exchange = {}

    for trade in trades:
        exchange = trade.exchange
        if exchange not in trades_by_exchange:
            trades_by_exchange[exchange] = []
        trades_by_exchange[exchange].append(trade)

    return trades_by_exchange


def analyze_trade_duplication(trades: List[Trade]) -> dict:
    """
    Analyze the level of trade duplication in the dataset.

    Args:
        trades: List of Trade objects

    Returns:
        Dictionary with duplication statistics
    """
    if not trades:
        return {
            'total_trades': 0,
            'unique_trades': 0,
            'duplicate_count': 0,
            'duplication_rate': 0.0
        }

    trade_hashes = set()
    duplicate_count = 0

    for trade in trades:
        trade_hash = (
            trade.timestamp.isoformat(),
            trade.symbol,
            trade.side.value,
            round(trade.amount, 8),
            round(trade.price, 8)
        )

        if trade_hash in trade_hashes:
            duplicate_count += 1
        else:
            trade_hashes.add(trade_hash)

    unique_count = len(trade_hashes)
    duplication_rate = (duplicate_count / len(trades) * 100) if trades else 0.0

    stats = {
        'total_trades': len(trades),
        'unique_trades': unique_count,
        'duplicate_count': duplicate_count,
        'duplication_rate': duplication_rate
    }

    logger.info(
        f"Trade duplication analysis: {unique_count} unique trades out of {len(trades)} total "
        f"({duplication_rate:.1f}% duplication rate)"
    )

    return stats
