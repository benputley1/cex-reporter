"""
Check current balances across all exchanges

Usage:
  python scripts/check_balances.py
  python scripts/check_balances.py --slack  # Also post to Slack
"""
import asyncio
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient
from src.reporting.slack import SlackClient
from config.settings import settings


async def check_all_balances(post_to_slack: bool = False):
    """Check balances across all configured exchange accounts"""

    print("=" * 80)
    print("CURRENT BALANCES - ALL EXCHANGES")
    print("=" * 80)
    print()

    # Initialize all exchange clients
    exchanges = []

    # MEXC accounts
    for account in settings.mexc_accounts:
        client = MEXCClient(
            config=account,
            mock_mode=settings.mock_mode,
            account_name=account['account_name']
        )
        await client.initialize()
        exchanges.append(client)

    # Kraken accounts
    for account in settings.kraken_accounts:
        client = KrakenClient(
            config=account,
            mock_mode=settings.mock_mode,
            account_name=account['account_name']
        )
        await client.initialize()
        exchanges.append(client)

    # KuCoin accounts
    for account in settings.kucoin_accounts:
        client = KuCoinClient(
            config=account,
            mock_mode=settings.mock_mode,
            account_name=account['account_name']
        )
        await client.initialize()
        exchanges.append(client)

    # Gate.io accounts
    for account in settings.gateio_accounts:
        client = GateioClient(
            config=account,
            mock_mode=settings.mock_mode,
            account_name=account['account_name']
        )
        await client.initialize()
        exchanges.append(client)

    # Fetch balances in parallel
    import time
    print(f"Fetching balances from {len(exchanges)} exchanges in parallel...")
    start_time = time.time()

    timeout = settings.exchange_timeout_seconds
    tasks = [asyncio.wait_for(exchange.get_balances(), timeout=timeout) for exchange in exchanges]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    elapsed_time = time.time() - start_time
    print(f"Completed in {elapsed_time:.2f}s\n")

    total_usdt = 0
    total_alkimi = 0
    exchange_balances = []

    for exchange, result in zip(exchanges, results):
        try:
            if isinstance(result, Exception):
                print(f"✗ {exchange.exchange_name:10} / {exchange.account_name:<6}")
                print(f"    Error: {result}")
                print()
                continue

            balances = result

            usdt = balances.get('USDT', {}).get('total', 0)
            alkimi = balances.get('ALKIMI', {}).get('total', 0)

            total_usdt += usdt
            total_alkimi += alkimi

            # Store for Slack
            if usdt > 0 or alkimi > 0:
                exchange_balances.append({
                    'name': f"{exchange.exchange_name}/{exchange.account_name}",
                    'usdt': usdt,
                    'alkimi': alkimi
                })

            indicator = "✓" if (usdt > 0 or alkimi > 0) else "○"

            print(f"{indicator} {exchange.exchange_name:10} / {exchange.account_name:<6}")
            if usdt > 0:
                print(f"    USDT:   {usdt:>15,.2f}")
            if alkimi > 0:
                print(f"    ALKIMI: {alkimi:>15,.2f}")
            if usdt == 0 and alkimi == 0:
                print(f"    (No balances)")
            print()

        except Exception as e:
            print(f"✗ {exchange.exchange_name:10} / {exchange.account_name:<6}")
            print(f"    Error: {e}")
            print()

    # Close all connections
    for exchange in exchanges:
        await exchange.close()

    # Print totals
    print("=" * 80)
    print("TOTAL BALANCES:")
    print("-" * 80)
    print(f"  USDT:   ${total_usdt:>15,.2f}")
    print(f"  ALKIMI:  {total_alkimi:>15,.2f}")
    print("=" * 80)

    # Post to Slack if requested
    if post_to_slack:
        slack_client = SlackClient()

        message = f"""*💰 Current Balances*

*Total Holdings:*
• USDT: ${total_usdt:,.2f}
• ALKIMI: {total_alkimi:,.0f}

*Exchange Breakdown:*
"""
        for bal in sorted(exchange_balances, key=lambda x: x['usdt'] + x['alkimi'], reverse=True):
            if bal['usdt'] > 0 and bal['alkimi'] > 0:
                message += f"• *{bal['name']}*: ${bal['usdt']:,.2f} | {bal['alkimi']:,.0f} ALKIMI\n"
            elif bal['usdt'] > 0:
                message += f"• *{bal['name']}*: ${bal['usdt']:,.2f}\n"
            elif bal['alkimi'] > 0:
                message += f"• *{bal['name']}*: {bal['alkimi']:,.0f} ALKIMI\n"

        await slack_client.send_message({"text": message})
        print("\n✓ Balances posted to Slack")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Check current balances')
    parser.add_argument('--slack', action='store_true', help='Post results to Slack')

    args = parser.parse_args()

    asyncio.run(check_all_balances(post_to_slack=args.slack))
