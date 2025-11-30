#!/usr/bin/env python3
"""Check if September trades are available from exchange APIs"""
import sys
sys.path.insert(0, '.')
import asyncio
from datetime import datetime
from config.settings import settings

async def main():
    # Import exchange clients
    from src.exchanges.mexc import MEXCClient
    from src.exchanges.kraken import KrakenClient
    from src.exchanges.kucoin import KuCoinClient
    from src.exchanges.gateio import GateioClient

    clients = []

    # September 2025: Sept 1 - Sept 30
    sept_start = datetime(2025, 9, 1)
    sept_end = datetime(2025, 9, 30, 23, 59, 59)

    print("=" * 80)
    print(f"Checking for trades in September 2025")
    print(f"Period: {sept_start.date()} to {sept_end.date()}")
    print("=" * 80)

    # Initialize all exchange clients
    print("\nInitializing exchange clients...")

    # MEXC
    for account in settings.exchanges.mexc:
        try:
            client = MEXCClient(account.name, account.api_key, account.api_secret)
            await client.initialize()
            clients.append(client)
            print(f"  ✓ {client.name}")
        except Exception as e:
            print(f"  ✗ {account.name}: {e}")

    # Kraken
    for account in settings.exchanges.kraken:
        try:
            client = KrakenClient(account.name, account.api_key, account.api_secret)
            await client.initialize()
            clients.append(client)
            print(f"  ✓ {client.name}")
        except Exception as e:
            print(f"  ✗ {account.name}: {e}")

    # KuCoin
    for account in settings.exchanges.kucoin:
        try:
            client = KuCoinClient(account.name, account.api_key, account.api_secret, account.api_passphrase)
            await client.initialize()
            clients.append(client)
            print(f"  ✓ {client.name}")
        except Exception as e:
            print(f"  ✗ {account.name}: {e}")

    # Gate.io
    for account in settings.exchanges.gateio:
        try:
            client = GateioClient(account.name, account.api_key, account.api_secret)
            await client.initialize()
            clients.append(client)
            print(f"  ✓ {client.name}")
        except Exception as e:
            print(f"  ✗ {account.name}: {e}")

    print(f"\nInitialized {len(clients)} clients")
    print("\n" + "=" * 80)
    print("Fetching trades from September 2025...")
    print("=" * 80 + "\n")

    total_sept_trades = 0

    for client in clients:
        try:
            # Fetch trades since September 1
            all_trades = await client.fetch_trades(since=sept_start)

            # Filter to only September trades
            sept_trades = [
                t for t in all_trades
                if sept_start <= t.timestamp <= sept_end
            ]

            if sept_trades:
                print(f"✓ {client.name}: {len(sept_trades)} September trades")
                # Show first and last trade
                first = min(t.timestamp for t in sept_trades)
                last = max(t.timestamp for t in sept_trades)
                print(f"  Range: {first} to {last}")
                total_sept_trades += len(sept_trades)
            else:
                print(f"  {client.name}: 0 September trades (fetched {len(all_trades)} total since Sept 1)")

        except Exception as e:
            print(f"✗ {client.name}: Error - {e}")

        await client.close()

    print("\n" + "=" * 80)
    print(f"TOTAL SEPTEMBER 2025 TRADES: {total_sept_trades}")
    print("=" * 80)

    if total_sept_trades == 0:
        print("\n⚠️  NO SEPTEMBER TRADES FOUND")
        print("This confirms that exchange APIs are no longer returning September data.")
        print("You need persistent trade storage to preserve historical data.")
    else:
        print(f"\n✓ Found {total_sept_trades} September trades")
        print("The issue may be elsewhere in the processing pipeline.")

asyncio.run(main())
