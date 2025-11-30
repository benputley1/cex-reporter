#!/usr/bin/env python3
"""
Test script to pull recent ALKIMI DEX trades from Sui blockchain.

This script queries the Sui mainnet RPC directly to find ALKIMI swaps
on Cetus, Turbos, Bluefin, and Aftermath DEXs.

Usage:
    python scripts/test_dex_trades.py
"""

import asyncio
import sys
import os
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings


async def test_dex_queries():
    """Test DEX swap event queries."""
    import httpx

    rpc = "https://fullnode.mainnet.sui.io"
    alkimi_token = "0x1a8f4bc33f8ef7fbc851f156857aa65d397a6a6fd27a7ac2ca717b51f2fd9489::alkimi::ALKIMI"

    # DEX swap event types
    dex_events = {
        "cetus": "0x1eabed72c53feb73c694be620a9da9dc841af501d0bf5c69e5d9a8c2d2df7c64::pool::SwapEvent",
        "turbos": "0x91bfbc386a41afcfd9b2533058d7e915a1d3829089cc268ff4333d54d6339ca1::pool::SwapEvent",
        "bluefin": "0xa17fef5d722a9f08a4b15ed4a6a40c8ccc9b21ad5ab44ef2b01ca5c6fa0f2d37::clmm::SwapEvent",
    }

    print("=" * 60)
    print("ALKIMI DEX TRADES TEST")
    print("=" * 60)
    print(f"Token: {alkimi_token[:40]}...")
    print()

    async with httpx.AsyncClient(timeout=30.0) as client:
        total_alkimi_trades = []

        for dex_name, event_type in dex_events.items():
            print(f"\n[{dex_name.upper()}] Querying swap events...")
            print(f"  Event type: {event_type[:50]}...")

            try:
                resp = await client.post(rpc, json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "suix_queryEvents",
                    "params": [
                        {"MoveEventType": event_type},
                        None,  # cursor
                        50,    # limit
                        True   # descending
                    ]
                })

                data = resp.json()

                if 'error' in data:
                    print(f"  \033[91mError: {data['error']}\033[0m")
                    continue

                events = data.get('result', {}).get('data', [])
                print(f"  Found {len(events)} total swap events")

                # Filter for ALKIMI swaps
                alkimi_swaps = []
                for event in events:
                    parsed = event.get('parsedJson', {})
                    event_str = str(parsed).lower()

                    if 'alkimi' in event_str:
                        alkimi_swaps.append({
                            'dex': dex_name,
                            'tx': event.get('id', {}).get('txDigest', 'unknown'),
                            'timestamp': event.get('timestampMs', 0),
                            'data': parsed
                        })

                print(f"  \033[92mALKIMI swaps: {len(alkimi_swaps)}\033[0m")

                for swap in alkimi_swaps[:3]:  # Show first 3
                    ts = datetime.fromtimestamp(int(swap['timestamp']) / 1000) if swap['timestamp'] else None
                    print(f"    - TX: {swap['tx'][:16]}...")
                    if ts:
                        print(f"      Time: {ts}")

                    # Parse amounts
                    data = swap['data']
                    amount_in = float(data.get('amount_in', data.get('in_amount', 0))) / 1e9
                    amount_out = float(data.get('amount_out', data.get('out_amount', 0))) / 1e9
                    atob = data.get('atob', data.get('a2b', '?'))

                    print(f"      In: {amount_in:.2f}, Out: {amount_out:.2f}, A->B: {atob}")

                total_alkimi_trades.extend(alkimi_swaps)

            except Exception as e:
                print(f"  \033[91mException: {e}\033[0m")

        print("\n" + "=" * 60)
        print(f"TOTAL ALKIMI TRADES FOUND: {len(total_alkimi_trades)}")
        print("=" * 60)

        return total_alkimi_trades


async def test_sui_monitor():
    """Test the SuiTokenMonitor class directly."""
    from src.exchanges.sui_monitor import SuiTokenMonitor

    print("\n" + "=" * 60)
    print("TESTING SuiTokenMonitor CLASS")
    print("=" * 60)

    sui_config = settings.sui_config
    print(f"Token contract: {sui_config.get('token_contract', 'not set')[:50]}...")
    print(f"RPC URL: {sui_config.get('rpc_url', 'not set')}")

    monitor = SuiTokenMonitor(
        config=sui_config,
        account_name='TEST'
    )

    try:
        print("\nInitializing monitor...")
        success = await monitor.initialize()

        if success:
            print("\033[92mInitialization successful!\033[0m")

            # Fetch trades from last 7 days
            since = datetime.now() - timedelta(days=7)
            print(f"\nFetching trades since {since}...")

            trades = await monitor.get_trades(since=since)
            print(f"\n\033[92mFound {len(trades)} ALKIMI trades\033[0m")

            if trades:
                print("\nLast 10 trades:")
                print("-" * 80)
                for i, trade in enumerate(trades[:10], 1):
                    side_color = "\033[92m" if trade.side.value == "buy" else "\033[91m"
                    print(f"{i}. {trade.timestamp} | {trade.exchange:10} | "
                          f"{side_color}{trade.side.value:4}\033[0m | "
                          f"{trade.amount:>12,.2f} ALKIMI @ ${trade.price:.6f}")
                print("-" * 80)
            else:
                print("\nNo ALKIMI trades found in the queried period.")
                print("This could mean:")
                print("  - No ALKIMI trading activity on these DEXs recently")
                print("  - The event types might need adjustment")

        await monitor.close()

    except Exception as e:
        print(f"\033[91mError: {e}\033[0m")
        import traceback
        traceback.print_exc()


async def main():
    # First test raw queries
    await test_dex_queries()

    # Then test the SuiTokenMonitor class
    await test_sui_monitor()


if __name__ == '__main__':
    asyncio.run(main())
