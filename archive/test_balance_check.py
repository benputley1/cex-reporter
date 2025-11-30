"""
Quick script to check raw balance structure from exchanges
"""
import asyncio
import ccxt.async_support as ccxt
from config.settings import settings

async def check_mexc_balance():
    """Check MEXC balance structure"""
    print("Checking MEXC Balance Structure...")
    print("=" * 60)

    # Get first MEXC config
    mexc_accounts = settings.mexc_accounts
    if not mexc_accounts:
        print("No MEXC accounts configured")
        return

    config = mexc_accounts[0]

    mexc = ccxt.mexc({
        'apiKey': config.get('apiKey'),
        'secret': config.get('secret'),
        'enableRateLimit': True,
    })

    try:
        await mexc.load_markets()
        balance = await mexc.fetch_balance()

        # Check if 'free', 'used', 'total' exist at top level
        if 'free' in balance:
            alkimi_free = balance['free'].get('ALKIMI', 0)
            usdt_free = balance['free'].get('USDT', 0)
            print(f"\nFree:")
            print(f"  ALKIMI: {alkimi_free:,.2f}")
            print(f"  USDT: ${usdt_free:,.2f}")

        if 'used' in balance:
            alkimi_used = balance['used'].get('ALKIMI', 0)
            usdt_used = balance['used'].get('USDT', 0)
            print(f"\nUsed/Locked:")
            print(f"  ALKIMI: {alkimi_used:,.2f}")
            print(f"  USDT: ${usdt_used:,.2f}")

        if 'total' in balance:
            alkimi_total = balance['total'].get('ALKIMI', 0)
            usdt_total = balance['total'].get('USDT', 0)
            print(f"\nTotal:")
            print(f"  ALKIMI: {alkimi_total:,.2f}")
            print(f"  USDT: ${usdt_total:,.2f}")

        # Also check open orders
        print(f"\n" + "=" * 60)
        print("Checking Open Orders on MEXC...")

        try:
            orders = await mexc.fetch_open_orders()
            print(f"\nFound {len(orders)} open orders")

            for order in orders[:5]:  # Show first 5
                symbol = order.get('symbol', 'N/A')
                side = order.get('side', 'N/A')
                amount = order.get('amount', 0)
                remaining = order.get('remaining', 0)
                print(f"  {symbol}: {side} {remaining:,.2f} (of {amount:,.2f})")

        except Exception as e:
            print(f"Could not fetch open orders: {e}")

        await mexc.close()

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        try:
            await mexc.close()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(check_mexc_balance())
