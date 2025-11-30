#!/usr/bin/env python3
"""
Verify September 2025 Trading Activity
Checks all exchanges for trades during September 2025 to confirm if the month had zero activity.
"""

import sys
import os
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from config.settings import settings
from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient

async def main():
    """Check September 2025 trading activity across all exchanges."""

    # Define September 2025 date range (naive datetime like historical_start_date)
    start_date = datetime(2025, 9, 1, 0, 0, 0)
    end_date = datetime(2025, 9, 30, 23, 59, 59)

    print("=" * 70)
    print("SEPTEMBER 2025 TRADING ACTIVITY VERIFICATION")
    print("=" * 70)
    print(f"Date Range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    print("=" * 70)
    print()

    all_september_trades = []

    # MEXC Accounts
    print("📊 MEXC Accounts:")
    print("-" * 70)
    for account in settings.mexc_accounts:
        account_name = account['account_name']
        try:
            client = MEXCClient(account['apiKey'], account['secret'])
            trades = await client.get_trades(since=start_date)

            # Filter to September only
            september_trades = [
                t for t in trades
                if start_date <= t.timestamp <= end_date
            ]

            all_september_trades.extend(september_trades)

            if september_trades:
                print(f"  ✓ MEXC ({account_name}): {len(september_trades)} trades")
                # Show first and last trade dates
                dates = sorted([t.timestamp for t in september_trades])
                print(f"    First trade: {dates[0].strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"    Last trade:  {dates[-1].strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"  ○ MEXC ({account_name}): 0 trades")

            await client.close()
        except Exception as e:
            print(f"  ✗ MEXC ({account_name}): Error - {str(e)}")

    print()

    # Kraken Accounts
    print("📊 Kraken Accounts:")
    print("-" * 70)
    for account in settings.kraken_accounts:
        account_name = account['account_name']
        try:
            client = KrakenClient(account['apiKey'], account['secret'])
            trades = await client.get_trades(since=start_date)

            # Filter to September only
            september_trades = [
                t for t in trades
                if start_date <= t.timestamp <= end_date
            ]

            all_september_trades.extend(september_trades)

            if september_trades:
                print(f"  ✓ Kraken ({account_name}): {len(september_trades)} trades")
                dates = sorted([t.timestamp for t in september_trades])
                print(f"    First trade: {dates[0].strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"    Last trade:  {dates[-1].strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"  ○ Kraken ({account_name}): 0 trades")

            await client.close()
        except Exception as e:
            print(f"  ✗ Kraken ({account_name}): Error - {str(e)}")

    print()

    # KuCoin Accounts
    print("📊 KuCoin Accounts:")
    print("-" * 70)
    for account in settings.kucoin_accounts:
        account_name = account['account_name']
        try:
            client = KuCoinClient(
                account['apiKey'],
                account['secret'],
                account['password']
            )
            trades = await client.get_trades(since=start_date)

            # Filter to September only
            september_trades = [
                t for t in trades
                if start_date <= t.timestamp <= end_date
            ]

            all_september_trades.extend(september_trades)

            if september_trades:
                print(f"  ✓ KuCoin ({account_name}): {len(september_trades)} trades")
                dates = sorted([t.timestamp for t in september_trades])
                print(f"    First trade: {dates[0].strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"    Last trade:  {dates[-1].strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"  ○ KuCoin ({account_name}): 0 trades")

            await client.close()
        except Exception as e:
            print(f"  ✗ KuCoin ({account_name}): Error - {str(e)}")

    print()

    # Gate.io Accounts
    print("📊 Gate.io Accounts:")
    print("-" * 70)
    for account in settings.gateio_accounts:
        account_name = account['account_name']
        try:
            client = GateioClient(account['apiKey'], account['secret'])
            trades = await client.get_trades(since=start_date)

            # Filter to September only
            september_trades = [
                t for t in trades
                if start_date <= t.timestamp <= end_date
            ]

            all_september_trades.extend(september_trades)

            if september_trades:
                print(f"  ✓ Gate.io ({account_name}): {len(september_trades)} trades")
                dates = sorted([t.timestamp for t in september_trades])
                print(f"    First trade: {dates[0].strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"    Last trade:  {dates[-1].strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"  ○ Gate.io ({account_name}): 0 trades")

            await client.close()
        except Exception as e:
            print(f"  ✗ Gate.io ({account_name}): Error - {str(e)}")

    print()
    print("=" * 70)
    print("SUMMARY")
    print("=" * 70)
    print(f"Total September 2025 Trades: {len(all_september_trades)}")

    if all_september_trades:
        print(f"\n✓ SEPTEMBER HAD TRADING ACTIVITY")

        # Show buy/sell breakdown
        buys = [t for t in all_september_trades if t.side.value == 'buy']
        sells = [t for t in all_september_trades if t.side.value == 'sell']
        print(f"  Buys: {len(buys)}")
        print(f"  Sells: {len(sells)}")

        # Show date range
        dates = sorted([t.timestamp for t in all_september_trades])
        print(f"\n  Trading Period:")
        print(f"    First: {dates[0].strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"    Last:  {dates[-1].strftime('%Y-%m-%d %H:%M:%S')}")

        # Volume
        total_volume = sum(t.amount * t.price for t in all_september_trades)
        print(f"\n  Total Volume: ${total_volume:,.2f}")
    else:
        print(f"\n○ NO TRADING ACTIVITY IN SEPTEMBER 2025")
        print("  This confirms why September is missing from the monthly report.")

    print("=" * 70)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
