#!/usr/bin/env python3
"""
Check Trade Date Ranges
See the actual date range of trades being fetched from each exchange.
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
    """Check the actual date range of trades from each exchange."""

    historical_start_date = datetime.fromisoformat(settings.historical_start_date)

    print("=" * 70)
    print("TRADE DATE RANGE CHECK")
    print("=" * 70)
    print(f"Historical start date (requested): {historical_start_date}")
    print("=" * 70)
    print()

    # MEXC MM2 (the one with 242 trades in main.py)
    print("📊 MEXC MM2:")
    try:
        account = next(a for a in settings.mexc_accounts if a['account_name'] == 'MM2')
        client = MEXCClient(account['apiKey'], account['secret'])
        trades = await client.get_trades(since=historical_start_date)

        if trades:
            sorted_trades = sorted(trades, key=lambda t: t.timestamp)
            print(f"  Total trades: {len(trades)}")
            print(f"  Earliest: {sorted_trades[0].timestamp} (requested: {historical_start_date})")
            print(f"  Latest:   {sorted_trades[-1].timestamp}")

            # Check if any trades are before historical_start_date
            before_start = [t for t in trades if t.timestamp < historical_start_date]
            if before_start:
                print(f"  ⚠️  WARNING: {len(before_start)} trades BEFORE historical_start_date!")
        else:
            print(f"  No trades returned")

        await client.close()
    except Exception as e:
        print(f"  ✗ Error: {str(e)}")

    print()

    # MEXC TM1 (the one with 500 trades in main.py)
    print("📊 MEXC TM1:")
    try:
        account = next(a for a in settings.mexc_accounts if a['account_name'] == 'TM1')
        client = MEXCClient(account['apiKey'], account['secret'])
        trades = await client.get_trades(since=historical_start_date)

        if trades:
            sorted_trades = sorted(trades, key=lambda t: t.timestamp)
            print(f"  Total trades: {len(trades)}")
            print(f"  Earliest: {sorted_trades[0].timestamp} (requested: {historical_start_date})")
            print(f"  Latest:   {sorted_trades[-1].timestamp}")

            # Check if any trades are before historical_start_date
            before_start = [t for t in trades if t.timestamp < historical_start_date]
            if before_start:
                print(f"  ⚠️  WARNING: {len(before_start)} trades BEFORE historical_start_date!")
                # Show the month distribution
                from collections import defaultdict
                monthly = defaultdict(int)
                for t in before_start:
                    month_key = t.timestamp.strftime('%Y-%m')
                    monthly[month_key] += 1
                print(f"  Months before start date:")
                for month in sorted(monthly.keys()):
                    print(f"    {month}: {monthly[month]} trades")
        else:
            print(f"  No trades returned")

        await client.close()
    except Exception as e:
        print(f"  ✗ Error: {str(e)}")

    print()
    print("=" * 70)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
