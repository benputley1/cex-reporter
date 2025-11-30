#!/usr/bin/env python3
"""
Debug Monthly Grouping
Fetch all trades and show which months are represented.
"""

import sys
import os
from datetime import datetime
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from config.settings import settings
from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient

async def main():
    """Fetch all trades and group them by month to see what's available."""

    historical_start_date = datetime.fromisoformat(settings.historical_start_date)

    print("=" * 70)
    print("MONTHLY GROUPING DEBUG")
    print("=" * 70)
    print(f"Historical start date: {historical_start_date}")
    print("=" * 70)
    print()

    all_trades = []

    # MEXC Accounts (skip MM1 due to auth failure)
    print("📊 Fetching MEXC trades...")
    for account in settings.mexc_accounts:
        if account['account_name'] == 'MM1':
            print(f"  Skipping MEXC MM1 (auth failure)")
            continue

        account_name = account['account_name']
        try:
            client = MEXCClient(account['apiKey'], account['secret'])
            trades = await client.get_trades(since=historical_start_date)
            all_trades.extend(trades)
            print(f"  ✓ MEXC ({account_name}): {len(trades)} trades")
            await client.close()
        except Exception as e:
            print(f"  ✗ MEXC ({account_name}): Error - {str(e)}")

    # Kraken Accounts
    print("\n📊 Fetching Kraken trades...")
    for account in settings.kraken_accounts:
        account_name = account['account_name']
        try:
            client = KrakenClient(account['apiKey'], account['secret'])
            trades = await client.get_trades(since=historical_start_date)
            all_trades.extend(trades)
            print(f"  ✓ Kraken ({account_name}): {len(trades)} trades")
            await client.close()
        except Exception as e:
            print(f"  ✗ Kraken ({account_name}): Error - {str(e)}")

    # KuCoin Accounts
    print("\n📊 Fetching KuCoin trades...")
    for account in settings.kucoin_accounts:
        account_name = account['account_name']
        try:
            client = KuCoinClient(
                account['apiKey'],
                account['secret'],
                account['password']
            )
            trades = await client.get_trades(since=historical_start_date)
            all_trades.extend(trades)
            print(f"  ✓ KuCoin ({account_name}): {len(trades)} trades")
            await client.close()
        except Exception as e:
            print(f"  ✗ KuCoin ({account_name}): Error - {str(e)}")

    # Gate.io Accounts
    print("\n📊 Fetching Gate.io trades...")
    for account in settings.gateio_accounts:
        account_name = account['account_name']
        try:
            client = GateioClient(account['apiKey'], account['secret'])
            trades = await client.get_trades(since=historical_start_date)
            all_trades.extend(trades)
            print(f"  ✓ Gate.io ({account_name}): {len(trades)} trades")
            await client.close()
        except Exception as e:
            print(f"  ✗ Gate.io ({account_name}): Error - {str(e)}")

    print("\n" + "=" * 70)
    print(f"TOTAL TRADES: {len(all_trades)}")
    print("=" * 70)
    print()

    # Group trades by month
    monthly_trades = defaultdict(list)
    for trade in all_trades:
        month_key = trade.timestamp.strftime('%Y-%m')
        monthly_trades[month_key].append(trade)

    # Sort months
    sorted_months = sorted(monthly_trades.keys(), reverse=True)

    print("MONTHLY BREAKDOWN:")
    print("-" * 70)
    for month_key in sorted_months:
        trades = monthly_trades[month_key]
        month_trades_sorted = sorted(trades, key=lambda t: t.timestamp)
        first = month_trades_sorted[0].timestamp
        last = month_trades_sorted[-1].timestamp
        print(f"  {month_key}: {len(trades):4d} trades  ({first.strftime('%Y-%m-%d')} to {last.strftime('%Y-%m-%d')})")

    print("\n" + "=" * 70)
    print("LAST 3 MONTHS (what gets shown in report):")
    print("=" * 70)
    for i, month_key in enumerate(sorted_months[:3], 1):
        trades_count = len(monthly_trades[month_key])
        print(f"  {i}. {month_key}: {trades_count} trades")

    # Check specifically for September
    print("\n" + "=" * 70)
    print("SEPTEMBER 2025 CHECK:")
    print("=" * 70)
    sept_key = '2025-09'
    if sept_key in monthly_trades:
        print(f"✓ September IS in monthly_trades with {len(monthly_trades[sept_key])} trades")
        if sept_key in sorted_months[:3]:
            print(f"✓ September IS in the last 3 months")
        else:
            print(f"✗ September is NOT in the last 3 months")
            print(f"  Position in sorted list: {sorted_months.index(sept_key) + 1} of {len(sorted_months)}")
    else:
        print(f"✗ September is NOT in monthly_trades")

    print("=" * 70)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
