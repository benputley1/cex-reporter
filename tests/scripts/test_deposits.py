"""Quick test to check what deposit/withdrawal APIs return"""
import asyncio
import ccxt.async_support as ccxt
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv

load_dotenv()

async def test_gateio():
    """Test Gate.io deposit/withdrawal API"""
    exchange = ccxt.gateio({
        'apiKey': os.getenv('GATEIO_MM1_API_KEY'),
        'secret': os.getenv('GATEIO_MM1_API_SECRET'),
        'enableRateLimit': True,
    })

    try:
        await exchange.load_markets()
        print("✓ Gate.io connected successfully")

        # Test deposits
        since = datetime.now() - timedelta(days=90)
        since_ts = int(since.timestamp() * 1000)

        print(f"\nFetching deposits since {since.date()}...")

        for asset in ['USDT', 'ALKIMI']:
            try:
                print(f"\n--- {asset} Deposits ---")
                deposits = await exchange.fetch_deposits(code=asset, since=since_ts, limit=10)
                print(f"API returned {len(deposits)} deposits")

                if deposits:
                    print("First deposit sample:")
                    print(f"  Keys: {deposits[0].keys()}")
                    print(f"  Status: {deposits[0].get('status')}")
                    print(f"  Amount: {deposits[0].get('amount')}")
                    print(f"  Timestamp: {deposits[0].get('timestamp')}")
                else:
                    print("  No deposits found")

            except Exception as e:
                print(f"  Error: {e}")

        # Test withdrawals
        for asset in ['USDT', 'ALKIMI']:
            try:
                print(f"\n--- {asset} Withdrawals ---")
                withdrawals = await exchange.fetch_withdrawals(code=asset, since=since_ts, limit=10)
                print(f"API returned {len(withdrawals)} withdrawals")

                if withdrawals:
                    print("First withdrawal sample:")
                    print(f"  Keys: {withdrawals[0].keys()}")
                    print(f"  Status: {withdrawals[0].get('status')}")
                    print(f"  Amount: {withdrawals[0].get('amount')}")
                    print(f"  Timestamp: {withdrawals[0].get('timestamp')}")
                else:
                    print("  No withdrawals found")

            except Exception as e:
                print(f"  Error: {e}")

    finally:
        await exchange.close()

if __name__ == '__main__':
    asyncio.run(test_gateio())
