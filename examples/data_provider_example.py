"""
Example usage of the DataProvider class.

Demonstrates how to use the unified data access layer for the ALKIMI trading bot.
"""

import asyncio
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add parent directory to path to import modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.bot.data_provider import DataProvider


async def main():
    """Demonstrate DataProvider functionality."""

    # Initialize DataProvider
    # For production, you would provide sui_config with wallet addresses
    provider = DataProvider(
        db_path="data/trade_cache.db",
        snapshots_dir="data/snapshots",
        sui_config=None  # Set to None to skip DEX features for this example
    )

    print("=" * 60)
    print("ALKIMI Trading Bot - DataProvider Examples")
    print("=" * 60)

    # Example 1: Get trades as DataFrame
    print("\n1. Getting trades from last 7 days...")
    since = datetime.now() - timedelta(days=7)
    trades_df = await provider.get_trades_df(since=since)

    if not trades_df.empty:
        print(f"   Found {len(trades_df)} trades")
        print(f"   Exchanges: {trades_df['exchange'].unique().tolist()}")
        print(f"   Total volume: ${(trades_df['amount'] * trades_df['price']).sum():.2f}")
    else:
        print("   No trades found")

    # Example 2: Get current balances
    print("\n2. Getting current balances from latest snapshot...")
    balances = await provider.get_balances()

    if balances:
        for account, assets in balances.items():
            print(f"   {account}:")
            for asset, amount in assets.items():
                print(f"     {asset}: {amount:,.2f}")
    else:
        print("   No balance snapshots found")

    # Example 3: Get snapshots over time
    print("\n3. Getting snapshots from last 30 days...")
    snapshots = await provider.get_snapshots(days=30)

    if snapshots:
        print(f"   Found {len(snapshots)} snapshots")
        print(f"   Date range: {snapshots[0]['date']} to {snapshots[-1]['date']}")
    else:
        print("   No snapshots found")

    # Example 4: Get current ALKIMI price
    print("\n4. Getting current ALKIMI price from CoinGecko...")
    price = await provider.get_current_price()

    if price:
        print(f"   Current ALKIMI price: ${price:.6f}")
    else:
        print("   Could not fetch price")

    # Example 5: Get trade summary
    print("\n5. Getting trade summary for last 30 days...")
    since = datetime.now() - timedelta(days=30)
    summary = await provider.get_trade_summary(since=since)

    print(f"   Total trades: {summary['trade_count']}")
    print(f"   Total volume: ${summary['total_volume']:.2f}")
    print(f"   Buy volume: ${summary['buy_volume']:.2f} ({summary['buy_count']} trades)")
    print(f"   Sell volume: ${summary['sell_volume']:.2f} ({summary['sell_count']} trades)")
    print(f"   Average price: ${summary['avg_price']:.6f}")
    print(f"   Total fees: ${summary['total_fees']:.4f}")

    if summary['by_exchange']:
        print("\n   By Exchange:")
        for exchange, stats in summary['by_exchange'].items():
            print(f"     {exchange}: {stats['trade_count']} trades, ${stats['volume']:.2f} volume")

    # Example 6: Get market data
    print("\n6. Getting comprehensive market data...")
    market_data = await provider.get_market_data()

    if market_data:
        print(f"   Current Price: ${market_data.get('current_price', 0):.6f}")
        print(f"   24h Volume: ${market_data.get('total_volume', 0):,.0f}")
        print(f"   Market Cap: ${market_data.get('market_cap', 0):,.0f}")
        print(f"   24h Change: {market_data.get('price_change_percentage_24h', 0):.2f}%")
    else:
        print("   Could not fetch market data")

    # Example 7: Save and retrieve functions
    print("\n7. Working with saved functions...")

    # Save a function
    success = await provider.save_function(
        name="daily_pnl",
        code="df['pnl'] = df['amount'] * df['price']",
        description="Calculate daily PnL",
        created_by="user123"
    )
    print(f"   Function saved: {success}")

    # List all functions
    functions = await provider.list_functions()
    print(f"   Total saved functions: {len(functions)}")
    for func in functions[:5]:  # Show first 5
        print(f"     - {func['name']}: {func['description']} (used {func['use_count']} times)")

    # Example 8: OTC transactions
    print("\n8. Working with OTC transactions...")

    # Save an OTC transaction
    otc_id = await provider.save_otc_transaction(
        date_str=datetime.now().date().isoformat(),
        alkimi_amount=100000,
        usd_amount=2700,
        price=0.027,
        side="buy",
        counterparty="Example Buyer",
        notes="Test transaction",
        created_by="user123"
    )
    print(f"   OTC transaction saved with ID: {otc_id}")

    # Get OTC transactions
    otc_df = await provider.get_otc_transactions(
        since=(datetime.now() - timedelta(days=30)).date().isoformat()
    )
    print(f"   Found {len(otc_df)} OTC transactions in last 30 days")

    # Example 9: Query history
    print("\n9. Saving query history...")
    query_id = await provider.save_query_history(
        user_id="user123",
        user_name="Test User",
        query_text="Show me trades from last week",
        query_type="trades",
        execution_time_ms=145,
        success=True
    )
    print(f"   Query saved with ID: {query_id}")

    # Get query history
    history = await provider.get_query_history(user_id="user123", limit=10)
    print(f"   User has {len(history)} queries in history")

    # Cleanup
    print("\n" + "=" * 60)
    print("Cleaning up...")
    await provider.close()
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
