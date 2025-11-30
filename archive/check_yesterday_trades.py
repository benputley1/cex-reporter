"""
Check how many trades happened yesterday across all exchanges
"""
import asyncio
from datetime import datetime, timedelta
from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient
from config.settings import settings

async def check_yesterday_trades():
    """Check trades from yesterday across all exchanges"""

    # Calculate yesterday's date range
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    yesterday_start = today - timedelta(days=1)
    yesterday_end = today

    print("=" * 80)
    print(f"TRADES FROM YESTERDAY ({yesterday_start.date()})")
    print("=" * 80)

    all_exchanges = []

    # Initialize all MEXC accounts
    for mexc_account in settings.mexc_accounts:
        client = MEXCClient(
            config=mexc_account,
            mock_mode=False,
            account_name=mexc_account['account_name']
        )
        all_exchanges.append(('mexc', mexc_account['account_name'], client))

    # Initialize all Kraken accounts
    for kraken_account in settings.kraken_accounts:
        client = KrakenClient(
            config=kraken_account,
            mock_mode=False,
            account_name=kraken_account['account_name']
        )
        all_exchanges.append(('kraken', kraken_account['account_name'], client))

    # Initialize all KuCoin accounts
    for kucoin_account in settings.kucoin_accounts:
        client = KuCoinClient(
            config=kucoin_account,
            mock_mode=False,
            account_name=kucoin_account['account_name']
        )
        all_exchanges.append(('kucoin', kucoin_account['account_name'], client))

    # Initialize all Gate.io accounts
    for gateio_account in settings.gateio_accounts:
        client = GateioClient(
            config=gateio_account,
            mock_mode=False,
            account_name=gateio_account['account_name']
        )
        all_exchanges.append(('gateio', gateio_account['account_name'], client))

    total_trades = 0
    exchange_totals = {}

    try:
        for exchange_name, account_name, client in all_exchanges:
            try:
                await client.initialize()

                # Fetch trades from yesterday
                trades = await client.get_trades(since=yesterday_start)

                # Filter for trades that happened yesterday only
                yesterday_trades = [
                    t for t in trades
                    if yesterday_start <= t.timestamp < yesterday_end
                ]

                if yesterday_trades:
                    print(f"\n{exchange_name.upper()} - {account_name}: {len(yesterday_trades)} trades")

                    # Show breakdown by side
                    buy_trades = [t for t in yesterday_trades if t.side.value == 'buy']
                    sell_trades = [t for t in yesterday_trades if t.side.value == 'sell']

                    print(f"  Buy:  {len(buy_trades)}")
                    print(f"  Sell: {len(sell_trades)}")

                    # Calculate volume
                    total_volume = sum(t.amount * t.price for t in yesterday_trades)
                    print(f"  Volume: ${total_volume:,.2f}")

                    total_trades += len(yesterday_trades)

                    if exchange_name not in exchange_totals:
                        exchange_totals[exchange_name] = 0
                    exchange_totals[exchange_name] += len(yesterday_trades)
                else:
                    print(f"\n{exchange_name.upper()} - {account_name}: No trades")

                await client.close()

            except Exception as e:
                print(f"\n{exchange_name.upper()} - {account_name}: ERROR - {str(e)[:100]}")
                try:
                    await client.close()
                except:
                    pass
                continue

        # Summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        print(f"\nTotal trades yesterday: {total_trades}")
        print("\nBy Exchange:")
        for exchange_name in sorted(exchange_totals.keys()):
            print(f"  {exchange_name.upper()}: {exchange_totals[exchange_name]} trades")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(check_yesterday_trades())
