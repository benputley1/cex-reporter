#!/usr/bin/env python3
"""Debug script to check trade date distribution"""
import sys
sys.path.insert(0, '.')
import asyncio
from datetime import datetime
from collections import defaultdict
from config import get_config

async def main():
    config = get_config()

    # Import exchange clients
    from src.exchanges.mexc import MEXCClient
    from src.exchanges.kraken import KrakenClient
    from src.exchanges.kucoin import KuCoinClient
    from src.exchanges.gateio import GateIOClient

    clients = []

    # Initialize MEXC clients
    for account in config['exchanges']['mexc']:
        client = MEXCClient(account['name'], account['api_key'], account['api_secret'])
        await client.initialize()
        clients.append(client)

    # Fetch all trades
    all_trades = []
    since_date = datetime(2025, 8, 15)

    print(f"Fetching trades since {since_date}")
    print("-" * 80)

    for client in clients:
        try:
            trades = await client.fetch_trades(since=since_date)
            all_trades.extend(trades)
            print(f"{client.name}: {len(trades)} trades")
            if trades:
                first = min(t.timestamp for t in trades)
                last = max(t.timestamp for t in trades)
                print(f"  Date range: {first} to {last}")
        except Exception as e:
            print(f"{client.name}: Error - {e}")
        await client.close()

    print("-" * 80)
    print(f"Total trades: {len(all_trades)}")

    # Group by month
    by_month = defaultdict(list)
    for trade in all_trades:
        month_key = trade.timestamp.strftime('%Y-%m')
        by_month[month_key].append(trade)

    print("\nTrades by month:")
    for month in sorted(by_month.keys()):
        trades = by_month[month]
        print(f"  {month}: {len(trades)} trades")
        first = min(t.timestamp for t in trades)
        last = max(t.timestamp for t in trades)
        print(f"    Range: {first.date()} to {last.date()}")

asyncio.run(main())
