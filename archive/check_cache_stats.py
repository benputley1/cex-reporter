"""
Check trade cache statistics
"""
from src.data.trade_cache import TradeCache

def check_cache():
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
    check_cache()
