"""
Verify balances across all exchanges and compare to expected values
"""
import asyncio
from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient
from config.settings import settings

# Expected balances from user verification
EXPECTED = {
    'gateio': {'USDT': 53437.28, 'ALKIMI': 1466108.25},
    'kraken': {'USDT': 7261.13, 'ALKIMI': 1622546.08},
    'kucoin': {'USDT': 4418.48, 'ALKIMI': 1979921.99},
    'mexc': {'USDT': 5093.98, 'ALKIMI': 1618102.68}
}

async def verify_exchange_balances():
    """Check all exchange balances and compare to expected"""

    print("=" * 80)
    print("BALANCE VERIFICATION")
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

    # Aggregate by exchange
    exchange_totals = {
        'mexc': {'USDT': 0, 'ALKIMI': 0},
        'kraken': {'USDT': 0, 'ALKIMI': 0},
        'kucoin': {'USDT': 0, 'ALKIMI': 0},
        'gateio': {'USDT': 0, 'ALKIMI': 0}
    }

    try:
        for exchange_name, account_name, client in all_exchanges:
            try:
                await client.initialize()
                balances = await client.get_balances()

                usdt_key = 'USDT' if exchange_name != 'kraken' else 'USDT'  # Kraken reports as USD

                usdt_total = balances.get('USDT', {}).get('total', 0)
                alkimi_total = balances.get('ALKIMI', {}).get('total', 0)

                exchange_totals[exchange_name]['USDT'] += usdt_total
                exchange_totals[exchange_name]['ALKIMI'] += alkimi_total

                print(f"\n{exchange_name.upper()} - {account_name}:")
                print(f"  USDT: {usdt_total:,.2f}")
                print(f"  ALKIMI: {alkimi_total:,.2f}")

                await client.close()
            except Exception as e:
                print(f"\n{exchange_name.upper()} - {account_name}: ERROR - {str(e)[:100]}")
                try:
                    await client.close()
                except:
                    pass
                continue

        # Compare results
        print("\n" + "=" * 80)
        print("COMPARISON: API vs Expected")
        print("=" * 80)

        for exchange_name in ['mexc', 'kraken', 'kucoin', 'gateio']:
            api_usdt = exchange_totals[exchange_name]['USDT']
            api_alkimi = exchange_totals[exchange_name]['ALKIMI']

            exp_usdt = EXPECTED[exchange_name]['USDT']
            exp_alkimi = EXPECTED[exchange_name]['ALKIMI']

            usdt_diff = api_usdt - exp_usdt
            alkimi_diff = api_alkimi - exp_alkimi

            print(f"\n{exchange_name.upper()}:")
            print(f"  USDT:")
            print(f"    API:      {api_usdt:>15,.2f}")
            print(f"    Expected: {exp_usdt:>15,.2f}")
            print(f"    Diff:     {usdt_diff:>15,.2f} {'✓' if abs(usdt_diff) < 0.01 else '✗'}")

            print(f"  ALKIMI:")
            print(f"    API:      {api_alkimi:>15,.2f}")
            print(f"    Expected: {exp_alkimi:>15,.2f}")
            print(f"    Diff:     {alkimi_diff:>15,.2f} {'✓' if abs(alkimi_diff) < 1 else '✗'}")

        # Overall totals
        print("\n" + "=" * 80)
        print("OVERALL TOTALS")
        print("=" * 80)

        total_api_usdt = sum(v['USDT'] for v in exchange_totals.values())
        total_api_alkimi = sum(v['ALKIMI'] for v in exchange_totals.values())

        total_exp_usdt = sum(v['USDT'] for v in EXPECTED.values())
        total_exp_alkimi = sum(v['ALKIMI'] for v in EXPECTED.values())

        print(f"\nUSDT:")
        print(f"  API:      ${total_api_usdt:,.2f}")
        print(f"  Expected: ${total_exp_usdt:,.2f}")
        print(f"  Diff:     ${total_api_usdt - total_exp_usdt:,.2f}")

        print(f"\nALKIMI:")
        print(f"  API:      {total_api_alkimi:,.2f}")
        print(f"  Expected: {total_exp_alkimi:,.2f}")
        print(f"  Diff:     {total_api_alkimi - total_exp_alkimi:,.2f}")

    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(verify_exchange_balances())
