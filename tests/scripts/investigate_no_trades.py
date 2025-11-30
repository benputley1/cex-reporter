"""
Investigate why no trades were found in recent time range.
Check balances and recent trading activity across all accounts.
"""

import asyncio
import sys
import os
from datetime import datetime, timezone, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from config.settings import settings
from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient


async def investigate_trading_activity():
    """Investigate trading activity across all accounts."""

    print(f"\n{'='*80}")
    print("Investigation: Trading Activity Check")
    print(f"{'='*80}\n")

    # Create exchange instances with multi-account support
    exchange_classes = [
        ('mexc', 'MEXC', MEXCClient),
        ('kraken', 'Kraken', KrakenClient),
        ('kucoin', 'KuCoin', KuCoinClient),
        ('gateio', 'Gate.io', GateioClient),
    ]

    exchanges = []

    # Initialize all exchange accounts
    for exchange_key, display_name, exchange_class in exchange_classes:
        try:
            accounts = settings.get_exchange_accounts(exchange_key)
            if not accounts:
                continue

            for account_config in accounts:
                account_name = account_config['account_name']
                try:
                    exchange = exchange_class(
                        config=account_config,
                        account_name=account_name
                    )
                    await exchange.initialize()
                    exchanges.append((f"{display_name} ({account_name})", exchange))
                except Exception as e:
                    print(f"✗ Failed to initialize {display_name} ({account_name}): {e}")
        except Exception as e:
            print(f"✗ Failed to initialize {display_name} exchange: {e}")

    print(f"✓ Initialized {len(exchanges)} accounts\n")

    # Check each account
    for name, exchange in exchanges:
        print(f"\n{'='*80}")
        print(f"{name}")
        print(f"{'='*80}\n")

        try:
            # 1. Check current balances
            print("1. Current Balances:")
            try:
                balances = await exchange.get_balances()
                if balances:
                    for asset, amount in balances.items():
                        if amount > 0:
                            print(f"   {asset}: {amount:,.4f}")
                    if not any(amount > 0 for amount in balances.values()):
                        print("   (All balances are zero)")
                else:
                    print("   (No balances found)")
            except Exception as e:
                print(f"   ✗ Error fetching balances: {e}")

            # 2. Check last 7 days of trades
            print("\n2. Recent Trading Activity (Last 7 Days):")
            try:
                seven_days_ago = datetime.now(timezone.utc) - timedelta(days=7)
                trades = await exchange.get_trades(seven_days_ago)

                if trades:
                    print(f"   ✓ Found {len(trades)} trades in last 7 days")

                    # Get most recent trade
                    most_recent = max(trades, key=lambda t: t.timestamp)
                    hours_ago = (datetime.now(timezone.utc) - most_recent.timestamp).total_seconds() / 3600

                    print(f"   Most Recent Trade:")
                    print(f"     Time: {most_recent.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')} ({hours_ago:.1f} hours ago)")
                    print(f"     Symbol: {most_recent.symbol}")
                    print(f"     Side: {most_recent.side.value.upper()}")
                    print(f"     Amount: {most_recent.amount:,.2f}")
                    print(f"     Price: ${most_recent.price:.6f}")

                    # Show breakdown by day
                    from collections import defaultdict
                    by_date = defaultdict(int)
                    for t in trades:
                        date_key = t.timestamp.strftime('%Y-%m-%d')
                        by_date[date_key] += 1

                    print(f"\n   Daily Breakdown:")
                    for date in sorted(by_date.keys(), reverse=True):
                        print(f"     {date}: {by_date[date]} trades")
                else:
                    print("   ⚠️  No trades found in last 7 days")

                    # Try fetching ALL trades since Aug 19
                    print("\n   Checking all historical trades since Aug 19, 2025...")
                    all_trades = await exchange.get_trades(datetime(2025, 8, 19, tzinfo=timezone.utc))

                    if all_trades:
                        most_recent = max(all_trades, key=lambda t: t.timestamp)
                        days_ago = (datetime.now(timezone.utc) - most_recent.timestamp).total_seconds() / 86400

                        print(f"   ✓ Found {len(all_trades)} total trades since Aug 19")
                        print(f"   Most Recent Trade: {most_recent.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')} ({days_ago:.1f} days ago)")
                    else:
                        print(f"   ⚠️  No trades found since Aug 19, 2025")

            except Exception as e:
                print(f"   ✗ Error fetching trades: {e}")

            # 3. Check last 24 hours specifically
            print("\n3. Last 24 Hours Activity:")
            try:
                yesterday = datetime.now(timezone.utc) - timedelta(days=1)
                recent_trades = await exchange.get_trades(yesterday)

                if recent_trades:
                    print(f"   ✓ Found {len(recent_trades)} trades in last 24 hours")
                else:
                    print(f"   ⚠️  No trades in last 24 hours")
            except Exception as e:
                print(f"   ✗ Error: {e}")

        except Exception as e:
            print(f"✗ Error investigating account: {e}")
        finally:
            try:
                await exchange.close()
            except:
                pass

    print(f"\n{'='*80}")
    print("Investigation Complete")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    asyncio.run(investigate_trading_activity())
