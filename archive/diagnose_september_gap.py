#!/usr/bin/env python3
"""
Diagnostic script to investigate the September trade gap.
Shows detailed date distribution to identify where trades are missing.
"""
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
    print(f"DIAGNOSTIC: Investigating September 2025 trade gap")
    print(f"Fetching trades since August 15, 2025 from {len(reporter.exchanges)} accounts")
    print("=" * 80)

    # Collect all trades by exchange
    trades_by_exchange = {}
    all_trades = []

    for exchange in reporter.exchanges:
        try:
            trades = await exchange.get_trades(since=datetime(2025, 8, 15))
            trades_by_exchange[exchange.account_name] = trades
            all_trades.extend(trades)

            if trades:
                first_date = min(t.timestamp for t in trades)
                last_date = max(t.timestamp for t in trades)
                print(f"\n{exchange.account_name}:")
                print(f"  Total trades: {len(trades)}")
                print(f"  Date range: {first_date} to {last_date}")

                # Group by date
                by_date = defaultdict(int)
                for t in trades:
                    date_key = t.timestamp.strftime('%Y-%m-%d')
                    by_date[date_key] += 1

                # Show daily distribution
                print(f"  Daily distribution:")
                for date in sorted(by_date.keys()):
                    print(f"    {date}: {by_date[date]} trades")
            else:
                print(f"\n{exchange.account_name}: No trades found")

        except Exception as e:
            print(f"\n{exchange.account_name}: Error - {e}")

    # Close exchanges
    await reporter.cleanup()

    # Overall analysis
    print("\n" + "=" * 80)
    print("OVERALL ANALYSIS")
    print("=" * 80)
    print(f"Total trades across all exchanges: {len(all_trades)}")

    if all_trades:
        # Find date gaps
        by_month = defaultdict(list)
        by_day = defaultdict(int)

        for trade in all_trades:
            month_key = trade.timestamp.strftime('%Y-%m')
            by_month[month_key].append(trade)

            day_key = trade.timestamp.strftime('%Y-%m-%d')
            by_day[day_key] += 1

        print(f"\nTrades by month:")
        for month in sorted(by_month.keys()):
            count = len(by_month[month])
            first = min(t.timestamp for t in by_month[month])
            last = max(t.timestamp for t in by_month[month])
            print(f"  {month}: {count} trades ({first.date()} to {last.date()})")

        print(f"\nChecking for date gaps...")
        # Find the first and last dates
        all_dates = sorted(by_day.keys())
        first_date = datetime.strptime(all_dates[0], '%Y-%m-%d')
        last_date = datetime.strptime(all_dates[-1], '%Y-%m-%d')

        # Check for missing days
        from datetime import timedelta
        current = first_date
        gaps = []
        while current <= last_date:
            date_str = current.strftime('%Y-%m-%d')
            if date_str not in by_day:
                gaps.append(date_str)
            current += timedelta(days=1)

        if gaps:
            print(f"\n  Found {len(gaps)} days with no trades:")
            # Group gaps into ranges
            gap_ranges = []
            range_start = gaps[0]
            range_end = gaps[0]

            for i in range(1, len(gaps)):
                current_gap = datetime.strptime(gaps[i], '%Y-%m-%d')
                prev_gap = datetime.strptime(gaps[i-1], '%Y-%m-%d')

                if (current_gap - prev_gap).days == 1:
                    # Continuous gap
                    range_end = gaps[i]
                else:
                    # Gap in gaps - save the range
                    if range_start == range_end:
                        gap_ranges.append(range_start)
                    else:
                        gap_ranges.append(f"{range_start} to {range_end}")
                    range_start = gaps[i]
                    range_end = gaps[i]

            # Add the last range
            if range_start == range_end:
                gap_ranges.append(range_start)
            else:
                gap_ranges.append(f"{range_start} to {range_end}")

            for gap_range in gap_ranges:
                print(f"    {gap_range}")
        else:
            print("\n  No date gaps found - continuous trading activity")

        # Check specifically for September
        sept_trades = [t for t in all_trades if t.timestamp.month == 9 and t.timestamp.year == 2025]
        print(f"\n  September 2025 trades: {len(sept_trades)}")

        if len(sept_trades) == 0:
            print("\n⚠️  CONFIRMED: No September trades in API responses")
            print("  However, withdrawals data shows $356,044.83 withdrawn in September")
            print("  This suggests trades existed but are no longer available from APIs")

    else:
        print("\n⚠️  No trades found at all!")

asyncio.run(main())
