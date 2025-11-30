#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from datetime import datetime
import asyncio
from collections import defaultdict

async def check_trades():
    from main import ExchangeManager
    from config import get_config

    config = get_config()
    manager = ExchangeManager(config)
    await manager.initialize()

    # Fetch all trades
    all_trades = []
    for client in manager.clients:
        trades = await client.fetch_trades(since=datetime(2025, 8, 15))
        all_trades.extend(trades)
        print(f'{client.name}: {len(trades)} trades')

    # Group by month
    trades_by_month = defaultdict(list)
    for trade in all_trades:
        month_key = trade.timestamp.strftime('%Y-%m')
        trades_by_month[month_key].append(trade)

    # Print summary
    print(f'\nTotal trades fetched: {len(all_trades)}')
    print(f'\nTrades by month:')
    for month in sorted(trades_by_month.keys()):
        trades = trades_by_month[month]
        print(f'  {month}: {len(trades)} trades')
        if len(trades) > 0:
            first_date = min(t.timestamp for t in trades)
            last_date = max(t.timestamp for t in trades)
            print(f'    Date range: {first_date} to {last_date}')

    await manager.cleanup()

asyncio.run(check_trades())
