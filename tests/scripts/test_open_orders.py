"""
Test script to check open orders support and fetch open orders from all exchanges.
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from config.settings import settings
from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient


async def test_open_orders():
    """Test fetching open orders from all exchanges."""

    # Create exchange instances with multi-account support
    exchange_classes = [
        ('mexc', 'MEXC', MEXCClient),
        ('kraken', 'Kraken', KrakenClient),
        ('kucoin', 'KuCoin', KuCoinClient),
        ('gateio', 'Gate.io', GateioClient),
    ]

    exchanges = []

    print(f"\n{'='*80}")
    print("Testing Open Orders Support")
    print(f"{'='*80}\n")

    # Initialize all exchange accounts
    for exchange_key, display_name, exchange_class in exchange_classes:
        try:
            # Get all accounts for this exchange
            accounts = settings.get_exchange_accounts(exchange_key)

            if not accounts:
                print(f"⚠️  No accounts configured for {display_name}, skipping...\n")
                continue

            # Create an instance for each account
            for account_config in accounts:
                account_name = account_config['account_name']
                try:
                    exchange = exchange_class(
                        config=account_config,
                        account_name=account_name
                    )
                    await exchange.initialize()
                    exchanges.append((f"{display_name} ({account_name})", exchange))
                except Exception as e:
                    print(f"✗ Failed to initialize {display_name} ({account_name}): {e}\n")

        except Exception as e:
            print(f"✗ Failed to initialize {display_name} exchange: {e}\n")

    # Test each exchange for open orders support
    for name, exchange in exchanges:
        print(f"\n{name}")
        print("-" * 40)

        try:
            # Check if exchange supports open orders
            has_open_orders = exchange.client.has.get('fetchOpenOrders', False)
            print(f"Supports fetchOpenOrders: {has_open_orders}")

            if has_open_orders:
                # Try to fetch open orders
                try:
                    # Fetch open orders for ALKIMI/USDT
                    orders = await exchange.client.fetch_open_orders('ALKIMI/USDT')
                    print(f"✓ Found {len(orders)} open orders for ALKIMI/USDT")

                    if orders:
                        print("\nSample order structure:")
                        for i, order in enumerate(orders[:2], 1):  # Show first 2 orders
                            print(f"\nOrder {i}:")
                            print(f"  ID: {order.get('id')}")
                            print(f"  Symbol: {order.get('symbol')}")
                            print(f"  Type: {order.get('type')}")
                            print(f"  Side: {order.get('side')}")
                            print(f"  Price: {order.get('price')}")
                            print(f"  Amount: {order.get('amount')}")
                            print(f"  Filled: {order.get('filled')}")
                            print(f"  Remaining: {order.get('remaining')}")
                            print(f"  Status: {order.get('status')}")
                    else:
                        print("  (No open orders currently)")

                except Exception as e:
                    print(f"✗ Error fetching open orders: {e}")
            else:
                print("⚠️  Exchange does not support fetchOpenOrders")

        except Exception as e:
            print(f"✗ Error: {e}")
        finally:
            try:
                await exchange.close()
            except:
                pass

    print(f"\n{'='*80}")
    print("Test Complete")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    asyncio.run(test_open_orders())
