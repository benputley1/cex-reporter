"""
Check open orders on KuCoin MM2 account
"""
import asyncio
import ccxt.async_support as ccxt
from config.settings import settings

async def check_open_orders():
    """Check open orders on KuCoin MM2"""
    print("=" * 80)
    print("KuCoin MM2 - Open Orders")
    print("=" * 80)

    # Get KuCoin MM2 config
    kucoin_accounts = settings.kucoin_accounts
    mm2_config = None

    for account in kucoin_accounts:
        if account['account_name'] == 'MM2':
            mm2_config = account
            break

    if not mm2_config:
        print("ERROR: KuCoin MM2 account not found")
        return

    # Initialize exchange
    exchange = ccxt.kucoin({
        'apiKey': mm2_config.get('apiKey'),
        'secret': mm2_config.get('secret'),
        'password': mm2_config.get('password'),
        'enableRateLimit': True,
    })

    try:
        await exchange.load_markets()
        print("\n✓ Connected to KuCoin MM2\n")

        # Fetch all open orders
        open_orders = await exchange.fetch_open_orders()

        print(f"Total open orders: {len(open_orders)}\n")

        if not open_orders:
            print("No open orders found.")
            await exchange.close()
            return

        # Group by symbol
        orders_by_symbol = {}
        for order in open_orders:
            symbol = order['symbol']
            if symbol not in orders_by_symbol:
                orders_by_symbol[symbol] = []
            orders_by_symbol[symbol].append(order)

        # Display orders by symbol
        for symbol in sorted(orders_by_symbol.keys()):
            symbol_orders = orders_by_symbol[symbol]
            print("=" * 80)
            print(f"Symbol: {symbol}")
            print("=" * 80)

            # Separate buy and sell orders
            buy_orders = [o for o in symbol_orders if o['side'] == 'buy']
            sell_orders = [o for o in symbol_orders if o['side'] == 'sell']

            if sell_orders:
                print(f"\n🔴 SELL ORDERS ({len(sell_orders)}):")
                print("-" * 80)
                # Sort by price (highest first)
                sell_orders.sort(key=lambda x: x['price'], reverse=True)

                total_sell_amount = 0
                total_sell_value = 0

                for order in sell_orders:
                    price = order['price']
                    amount = order['amount']
                    remaining = order['remaining']
                    filled = order['filled']
                    value = remaining * price

                    total_sell_amount += remaining
                    total_sell_value += value

                    print(f"\nPrice: ${price:.6f}")
                    print(f"  Amount: {amount:,.2f} (Remaining: {remaining:,.2f}, Filled: {filled:,.2f})")
                    print(f"  Value: ${value:,.2f}")
                    print(f"  Order ID: {order['id']}")
                    print(f"  Created: {order.get('datetime', 'N/A')}")
                    print(f"  Status: {order.get('status', 'N/A')}")

                print(f"\n{'─' * 80}")
                print(f"Total Sell Orders: {len(sell_orders)}")
                print(f"Total Amount: {total_sell_amount:,.2f} ALKIMI")
                print(f"Total Value: ${total_sell_value:,.2f}")
                print(f"Average Price: ${total_sell_value / total_sell_amount:.6f}")

            if buy_orders:
                print(f"\n🟢 BUY ORDERS ({len(buy_orders)}):")
                print("-" * 80)
                # Sort by price (highest first)
                buy_orders.sort(key=lambda x: x['price'], reverse=True)

                total_buy_amount = 0
                total_buy_value = 0

                for order in buy_orders:
                    price = order['price']
                    amount = order['amount']
                    remaining = order['remaining']
                    filled = order['filled']
                    value = remaining * price

                    total_buy_amount += remaining
                    total_buy_value += value

                    print(f"\nPrice: ${price:.6f}")
                    print(f"  Amount: {amount:,.2f} (Remaining: {remaining:,.2f}, Filled: {filled:,.2f})")
                    print(f"  Value: ${value:,.2f}")
                    print(f"  Order ID: {order['id']}")
                    print(f"  Created: {order.get('datetime', 'N/A')}")
                    print(f"  Status: {order.get('status', 'N/A')}")

                print(f"\n{'─' * 80}")
                print(f"Total Buy Orders: {len(buy_orders)}")
                print(f"Total Amount: {total_buy_amount:,.2f} ALKIMI")
                print(f"Total Value: ${total_buy_value:,.2f}")
                print(f"Average Price: ${total_buy_value / total_buy_amount:.6f}")

            print("\n")

        # Overall summary
        print("=" * 80)
        print("SUMMARY")
        print("=" * 80)

        total_orders = len(open_orders)
        total_buy = len([o for o in open_orders if o['side'] == 'buy'])
        total_sell = len([o for o in open_orders if o['side'] == 'sell'])

        print(f"\nTotal Open Orders: {total_orders}")
        print(f"  Buy Orders: {total_buy}")
        print(f"  Sell Orders: {total_sell}")

        await exchange.close()

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
        try:
            await exchange.close()
        except:
            pass

if __name__ == "__main__":
    asyncio.run(check_open_orders())
