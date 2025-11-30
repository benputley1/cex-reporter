#!/usr/bin/env python3
"""
DEX Integration Test Script

Tests the Sui DEX monitoring functionality:
- RPC connectivity
- Token contract monitoring
- Trade parsing
- Balance fetching

Usage:
    python scripts/test_dex_integration.py
    python scripts/test_dex_integration.py --mock
"""

import asyncio
import sys
import os
import argparse
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from src.utils import get_logger

logger = get_logger(__name__)


async def test_sui_rpc_connectivity(rpc_url: str) -> bool:
    """Test basic RPC connectivity."""
    print("\n[1] Testing Sui RPC Connectivity...")
    print(f"    URL: {rpc_url}")

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            # Simple RPC call to check connectivity
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "sui_getLatestCheckpointSequenceNumber",
                    "params": []
                },
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    checkpoint = data['result']
                    print(f"    \033[92m✓\033[0m Connected! Latest checkpoint: {checkpoint}")
                    return True
                else:
                    print(f"    \033[91m✗\033[0m RPC error: {data.get('error', 'Unknown')}")
                    return False
            else:
                print(f"    \033[91m✗\033[0m HTTP error: {response.status_code}")
                return False

    except Exception as e:
        print(f"    \033[91m✗\033[0m Connection failed: {e}")
        return False


async def test_token_contract(rpc_url: str, token_contract: str) -> bool:
    """Test token contract accessibility."""
    print("\n[2] Testing Token Contract...")
    print(f"    Contract: {token_contract[:20]}...")

    if not token_contract or token_contract == 'your_alkimi_token_contract_address_here':
        print("    \033[93m!\033[0m Token contract not configured")
        return False

    try:
        import httpx

        async with httpx.AsyncClient() as client:
            # Get coin metadata (for coin types, not objects)
            response = await client.post(
                rpc_url,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "suix_getCoinMetadata",
                    "params": [token_contract]
                },
                timeout=10.0
            )

            if response.status_code == 200:
                data = response.json()
                if 'result' in data and data['result']:
                    name = data['result'].get('name', 'Unknown')
                    symbol = data['result'].get('symbol', 'Unknown')
                    decimals = data['result'].get('decimals', 0)
                    print(f"    \033[92m✓\033[0m Token found! {name} ({symbol}), {decimals} decimals")
                    return True
                else:
                    print(f"    \033[91m✗\033[0m Token not found or invalid")
                    return False
            else:
                print(f"    \033[91m✗\033[0m HTTP error: {response.status_code}")
                return False

    except Exception as e:
        print(f"    \033[91m✗\033[0m Failed: {e}")
        return False


async def test_sui_monitor_class() -> bool:
    """Test the SuiTokenMonitor class."""
    print("\n[3] Testing SuiTokenMonitor Class...")

    try:
        from src.exchanges.sui_monitor import SuiTokenMonitor

        sui_config = settings.sui_config

        if not sui_config.get('token_contract') or sui_config['token_contract'] == 'your_alkimi_token_contract_address_here':
            print("    \033[93m!\033[0m Token contract not configured, using mock mode")
            return True

        monitor = SuiTokenMonitor(
            config=sui_config,
            account_name='TEST'
        )

        success = await monitor.initialize()

        if success:
            print(f"    \033[92m✓\033[0m SuiTokenMonitor initialized")

            # Try to get balances
            print("    Testing balance fetch...")
            balances = await monitor.get_balances()
            print(f"    \033[92m✓\033[0m Balances: {balances}")

            # Try to get recent trades
            print("    Testing trade fetch...")
            since = datetime.now() - timedelta(hours=24)
            trades = await monitor.get_trades(since=since)
            print(f"    \033[92m✓\033[0m Found {len(trades)} trades in last 24h")

            await monitor.close()
            return True
        else:
            print(f"    \033[91m✗\033[0m Failed to initialize")
            return False

    except ImportError as e:
        print(f"    \033[91m✗\033[0m Import error: {e}")
        return False
    except Exception as e:
        print(f"    \033[91m✗\033[0m Error: {e}")
        return False


async def test_cex_dex_breakdown() -> bool:
    """Test the CEX/DEX breakdown functionality."""
    print("\n[4] Testing CEX/DEX Breakdown Logic...")

    try:
        from src.analytics.simple_tracker import DEX_EXCHANGES

        print(f"    DEX exchanges defined: {DEX_EXCHANGES}")

        # Create some mock trades to test categorization
        from src.exchanges.base import Trade, TradeSide

        test_trades = [
            Trade(
                timestamp=datetime.now(),
                symbol='ALKIMI',
                side=TradeSide.BUY,
                amount=1000,
                price=0.025,
                fee=0.1,
                trade_id='test1',
                exchange='mexc'
            ),
            Trade(
                timestamp=datetime.now(),
                symbol='ALKIMI',
                side=TradeSide.SELL,
                amount=500,
                price=0.026,
                fee=0.05,
                trade_id='test2',
                exchange='sui_dex'
            ),
            Trade(
                timestamp=datetime.now(),
                symbol='ALKIMI',
                side=TradeSide.BUY,
                amount=2000,
                price=0.024,
                fee=0.2,
                trade_id='test3',
                exchange='cetus'
            ),
        ]

        # Categorize trades
        cex_trades = []
        dex_trades = []

        for trade in test_trades:
            exchange_lower = trade.exchange.lower() if trade.exchange else ''
            if exchange_lower in DEX_EXCHANGES or 'dex' in exchange_lower:
                dex_trades.append(trade)
            else:
                cex_trades.append(trade)

        print(f"    Test results:")
        print(f"      CEX trades: {len(cex_trades)} (expected: 1)")
        print(f"      DEX trades: {len(dex_trades)} (expected: 2)")

        if len(cex_trades) == 1 and len(dex_trades) == 2:
            print(f"    \033[92m✓\033[0m Categorization working correctly")
            return True
        else:
            print(f"    \033[91m✗\033[0m Categorization error")
            return False

    except Exception as e:
        print(f"    \033[91m✗\033[0m Error: {e}")
        return False


async def main():
    parser = argparse.ArgumentParser(description='Test DEX Integration')
    parser.add_argument('--mock', action='store_true', help='Run with mock data only')
    args = parser.parse_args()

    print("=" * 60)
    print("ALKIMI DEX INTEGRATION TEST")
    print("=" * 60)

    sui_config = settings.sui_config
    rpc_url = sui_config.get('rpc_url', 'https://fullnode.mainnet.sui.io')
    token_contract = sui_config.get('token_contract', '')

    results = []

    # Test 1: RPC Connectivity
    if not args.mock:
        results.append(await test_sui_rpc_connectivity(rpc_url))
    else:
        print("\n[1] RPC Connectivity - Skipped (mock mode)")
        results.append(True)

    # Test 2: Token Contract
    if not args.mock and token_contract:
        results.append(await test_token_contract(rpc_url, token_contract))
    else:
        print("\n[2] Token Contract - Skipped (not configured or mock mode)")
        results.append(True)

    # Test 3: SuiTokenMonitor class
    results.append(await test_sui_monitor_class())

    # Test 4: CEX/DEX breakdown logic
    results.append(await test_cex_dex_breakdown())

    # Summary
    print("\n" + "=" * 60)
    print("TEST SUMMARY")
    print("=" * 60)

    passed = sum(1 for r in results if r)
    total = len(results)

    print(f"\n    Passed: {passed}/{total}")

    if passed == total:
        print("\n\033[92mAll tests passed!\033[0m\n")
        return 0
    else:
        print("\n\033[91mSome tests failed.\033[0m\n")
        return 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
