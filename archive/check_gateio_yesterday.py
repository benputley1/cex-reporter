"""
Check Gate.io MM1 and MM2 for yesterday's trades
"""
import asyncio
from datetime import datetime, timedelta
from src.exchanges.gateio import GateioClient
from config.settings import settings

async def check_gateio_yesterday():
    """Check Gate.io MM1 and MM2 trades from yesterday"""

    # Calculate yesterday's date range
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today - timedelta(days=1)
    yesterday_end = today

    print("=" * 80)
    print(f"GATE.IO TRADES FROM YESTERDAY ({yesterday_start.date()})")
    print("=" * 80)

    # Find MM1 and MM2 accounts
    mm1_config = None
    mm2_config = None

    for account in settings.gateio_accounts:
        if account['account_name'] == 'MM1':
            mm1_config = account
        elif account['account_name'] == 'MM2':
            mm2_config = account

    results = {}

    # Check MM1
    if mm1_config:
        print("\n" + "─" * 80)
        print("Gate.io MM1")
        print("─" * 80)

        client = GateioClient(
            config=mm1_config,
            mock_mode=False,
            account_name='MM1'
        )

        try:
            await client.initialize()
            print("✓ Connected successfully")

            # Fetch trades from yesterday
            trades = await client.get_trades(since=yesterday_start)

            # Filter for trades that happened yesterday only
            yesterday_trades = [
                t for t in trades
                if yesterday_start <= t.timestamp < yesterday_end
            ]

            if yesterday_trades:
                print(f"Found {len(yesterday_trades)} trades")

                # Show breakdown by side
                buy_trades = [t for t in yesterday_trades if t.side.value == 'buy']
                sell_trades = [t for t in yesterday_trades if t.side.value == 'sell']

                print(f"  Buy:  {len(buy_trades)}")
                print(f"  Sell: {len(sell_trades)}")

                # Calculate volume
                total_volume = sum(t.amount * t.price for t in yesterday_trades)
                print(f"  Volume: ${total_volume:,.2f}")

                results['MM1'] = {
                    'trades': len(yesterday_trades),
                    'buy': len(buy_trades),
                    'sell': len(sell_trades),
                    'volume': total_volume
                }
            else:
                print("No trades yesterday")
                results['MM1'] = {
                    'trades': 0,
                    'buy': 0,
                    'sell': 0,
                    'volume': 0
                }

            await client.close()

        except Exception as e:
            print(f"✗ ERROR: {str(e)[:150]}")
            results['MM1'] = {'error': str(e)[:150]}
            try:
                await client.close()
            except:
                pass

    # Check MM2
    if mm2_config:
        print("\n" + "─" * 80)
        print("Gate.io MM2")
        print("─" * 80)

        client = GateioClient(
            config=mm2_config,
            mock_mode=False,
            account_name='MM2'
        )

        try:
            await client.initialize()
            print("✓ Connected successfully")

            # Fetch trades from yesterday
            trades = await client.get_trades(since=yesterday_start)

            # Filter for trades that happened yesterday only
            yesterday_trades = [
                t for t in trades
                if yesterday_start <= t.timestamp < yesterday_end
            ]

            if yesterday_trades:
                print(f"Found {len(yesterday_trades)} trades")

                # Show breakdown by side
                buy_trades = [t for t in yesterday_trades if t.side.value == 'buy']
                sell_trades = [t for t in yesterday_trades if t.side.value == 'sell']

                print(f"  Buy:  {len(buy_trades)}")
                print(f"  Sell: {len(sell_trades)}")

                # Calculate volume
                total_volume = sum(t.amount * t.price for t in yesterday_trades)
                print(f"  Volume: ${total_volume:,.2f}")

                results['MM2'] = {
                    'trades': len(yesterday_trades),
                    'buy': len(buy_trades),
                    'sell': len(sell_trades),
                    'volume': total_volume
                }
            else:
                print("No trades yesterday")
                results['MM2'] = {
                    'trades': 0,
                    'buy': 0,
                    'sell': 0,
                    'volume': 0
                }

            await client.close()

        except Exception as e:
            print(f"✗ ERROR: {str(e)[:150]}")
            results['MM2'] = {'error': str(e)[:150]}
            try:
                await client.close()
            except:
                pass

    # Summary
    print("\n" + "=" * 80)
    print("GATE.IO SUMMARY & UPDATED TOTALS")
    print("=" * 80)

    gateio_total_trades = 0
    gateio_total_volume = 0.0

    for account_name, data in results.items():
        if 'error' not in data:
            gateio_total_trades += data['trades']
            gateio_total_volume += data['volume']

    print(f"\nGate.io MM1 & MM2: {gateio_total_trades} trades, ${gateio_total_volume:,.2f} volume")

    # Previous results from yesterday's check
    print("\n" + "─" * 80)
    print("PREVIOUS RESULTS:")
    print("─" * 80)
    print("MEXC: 55 trades ($9,102.37 volume)")
    print("KuCoin: 8 trades ($4,923.01 volume)")
    print("Gate.io TM: 1 trade ($821.10 volume)")
    print("TOTAL: 64 trades")

    print("\n" + "─" * 80)
    print("UPDATED TOTALS INCLUDING MM1 & MM2:")
    print("─" * 80)

    previous_total = 64
    previous_volume = 9102.37 + 4923.01 + 821.10
    previous_gateio = 1  # TM only

    new_total_trades = previous_total + gateio_total_trades
    new_total_volume = previous_volume + gateio_total_volume
    new_gateio_total = previous_gateio + gateio_total_trades

    print(f"\nGate.io (All accounts): {new_gateio_total} trades")
    print(f"MEXC: 55 trades")
    print(f"KuCoin: 8 trades")
    print(f"Kraken: 0 trades")
    print(f"\nTOTAL YESTERDAY: {new_total_trades} trades")
    print(f"TOTAL VOLUME: ${new_total_volume:,.2f}")

if __name__ == "__main__":
    asyncio.run(check_gateio_yesterday())
