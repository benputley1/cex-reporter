"""
Display trade cache statistics

Usage:
  python scripts/cache_stats.py
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.trade_cache import TradeCache


def show_cache_stats():
    """Display detailed cache statistics"""

    cache = TradeCache()
    stats = cache.get_stats()

    print("=" * 80)
    print("TRADE CACHE STATISTICS")
    print("=" * 80)
    print(f"\nTotal trades cached: {stats['total_trades']:,}")
    print(f"Oldest trade: {stats['oldest_trade']}")
    print(f"Newest trade: {stats['newest_trade']}")
    print(f"Accounts tracked: {stats['account_count']}")
    print("\n" + "=" * 80)


if __name__ == "__main__":
    show_cache_stats()
