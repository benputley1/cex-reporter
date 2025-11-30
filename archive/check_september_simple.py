#!/usr/bin/env python3
"""Simple check for September trades"""
import sys
sys.path.insert(0, '.')
import asyncio
from datetime import datetime
from collections import defaultdict

async def main():
    from main import CEXReporter

    # Create reporter
    reporter = CEXReporter()

    # Initialize exchanges
    await reporter.initialize_exchanges()

    print("=" * 80)
    print(f"Checking for September 2025 trades across {len(reporter.exchanges)} accounts")
    print("=" * 80)

    sept_start = datetime(2025, 9, 1)
    sept_end = datetime(2025, 9, 30, 23, 59, 59)

    all_trades = []
    sept_trades = []

    for exchange in reporter.exchanges:
        try:
            trades = await exchange.get_trades(since=datetime(2025, 8, 15))
            all_trades.extend(trades)

            # Filter for September
            sept_only = [t for t in trades if sept_start <= t.timestamp <= sept_end]
            sept_trades.extend(sept_only)

            if sept_only:
                print(f"✓ {exchange.account_name}: {len(sept_only)} September trades (of {len(trades)} total)")
            else:
                print(f"  {exchange.account_name}: 0 September trades (of {len(trades)} total)")

        except Exception as e:
            print(f"✗ {exchange.account_name}: Error - {e}")

    # Close exchanges
    await reporter.cleanup()

    print("\n" + "=" * 80)
    print(f"TOTAL: {len(sept_trades)} September trades out of {len(all_trades)} total")
    print("=" * 80)

    if sept_trades:
        # Show date range
        first = min(t.timestamp for t in sept_trades)
        last = max(t.timestamp for t in sept_trades)
        print(f"September trades range: {first.date()} to {last.date()}")

        # Show some sample trades
        print(f"\nFirst 5 September trades:")
        for trade in sorted(sept_trades, key=lambda t: t.timestamp)[:5]:
            print(f"  {trade.timestamp} - {trade.side.value} {trade.amount:.2f} {trade.symbol} @ ${trade.price:.4f}")
    else:
        print("\n⚠️  NO SEPTEMBER TRADES FOUND IN ANY EXCHANGE API")
        print("This confirms September data is no longer available from the APIs.")

asyncio.run(main())
