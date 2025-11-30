"""
Check recent trading activity across all exchanges

Usage:
  python scripts/recent_activity.py            # Last 6 hours (default)
  python scripts/recent_activity.py --hours 24 # Last 24 hours
  python scripts/recent_activity.py --days 7   # Last 7 days
  python scripts/recent_activity.py --slack    # Also post to Slack
"""
import asyncio
import argparse
from datetime import datetime, timedelta
from collections import defaultdict
from typing import List

# Add parent directory to path
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient
from src.reporting.slack import SlackClient
from config.settings import settings


async def check_recent_activity(hours: int = 6, days: int = None, post_to_slack: bool = False):
    """Check recent trading activity across all exchanges"""

    # Calculate time window
    if days:
        since = datetime.now() - timedelta(days=days)
        period_str = f"last {days} day(s)"
    else:
        since = datetime.now() - timedelta(hours=hours)
        period_str = f"last {hours} hour(s)"

    print("=" * 80)
    print(f"RECENT TRADING ACTIVITY - {period_str.upper()}")
    print("=" * 80)
    print(f"Period: {since.strftime('%Y-%m-%d %H:%M:%S')} to now")
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

    # Fetch trades from all exchanges
    all_trades = []
    exchange_stats = defaultdict(lambda: {'buy': 0, 'sell': 0, 'buy_vol': 0, 'sell_vol': 0})

    for exchange in exchanges:
        try:
            trades = await exchange.get_trades(since=since)
            all_trades.extend(trades)

            exchange_key = f"{exchange.exchange_name}/{exchange.account_name}"
            for trade in trades:
                if trade.side.value == 'buy':
                    exchange_stats[exchange_key]['buy'] += 1
                    exchange_stats[exchange_key]['buy_vol'] += trade.amount
                else:
                    exchange_stats[exchange_key]['sell'] += 1
                    exchange_stats[exchange_key]['sell_vol'] += trade.amount

        except Exception as e:
            print(f"⚠️  Error fetching from {exchange.exchange_name}/{exchange.account_name}: {e}")

    # Close all connections
    for exchange in exchanges:
        await exchange.close()

    # Print summary
    print(f"\nTOTAL ACTIVITY:")
    print("-" * 80)
    total_buys = sum(s['buy'] for s in exchange_stats.values())
    total_sells = sum(s['sell'] for s in exchange_stats.values())
    total_buy_vol = sum(s['buy_vol'] for s in exchange_stats.values())
    total_sell_vol = sum(s['sell_vol'] for s in exchange_stats.values())

    print(f"  Total Trades: {total_buys + total_sells:,}")
    print(f"  Buys:  {total_buys:>4} trades ({total_buy_vol:>15,.0f} ALKIMI)")
    print(f"  Sells: {total_sells:>4} trades ({total_sell_vol:>15,.0f} ALKIMI)")
    print(f"  Net:   {total_buy_vol - total_sell_vol:>+15,.0f} ALKIMI")

    print(f"\nBREAKDOWN BY EXCHANGE:")
    print("-" * 80)
    print(f"{'Exchange/Account':<25} {'Buys':<10} {'Buy Vol':<18} {'Sells':<10} {'Sell Vol':<18} {'Net Vol':<18}")
    print("-" * 80)

    for exchange_key, stats in sorted(exchange_stats.items()):
        net_vol = stats['buy_vol'] - stats['sell_vol']
        indicator = "🟢" if net_vol > 0 else "🔴" if net_vol < 0 else "⚪"

        print(f"{indicator} {exchange_key:<23} "
              f"{stats['buy']:<10} {stats['buy_vol']:<18,.0f} "
              f"{stats['sell']:<10} {stats['sell_vol']:<18,.0f} "
              f"{net_vol:<+18,.0f}")

    # Calculate average prices
    if all_trades:
        all_trades.sort(key=lambda t: t.timestamp)
        avg_buy_price = sum(t.price for t in all_trades if t.side.value == 'buy') / max(total_buys, 1)
        avg_sell_price = sum(t.price for t in all_trades if t.side.value == 'sell') / max(total_sells, 1)

        print(f"\nPRICE SUMMARY:")
        print("-" * 80)
        if total_buys > 0:
            print(f"  Average Buy Price:  ${avg_buy_price:.6f}")
        if total_sells > 0:
            print(f"  Average Sell Price: ${avg_sell_price:.6f}")
        if total_buys > 0 and total_sells > 0:
            spread = avg_sell_price - avg_buy_price
            spread_pct = (spread / avg_buy_price) * 100
            print(f"  Spread:             ${spread:.6f} ({spread_pct:+.2f}%)")

    print("\n" + "=" * 80)

    # Post to Slack if requested
    if post_to_slack:
        slack_client = SlackClient()

        # Format message
        net_position = total_buy_vol - total_sell_vol
        if net_position > 0:
            position_emoji = "🟢"
            position_text = f"NET BUYER (+{net_position:,.0f} ALKIMI)"
        elif net_position < 0:
            position_emoji = "🔴"
            position_text = f"NET SELLER ({net_position:,.0f} ALKIMI)"
        else:
            position_emoji = "⚪"
            position_text = "MARKET NEUTRAL"

        # Build exchange breakdown
        exchange_lines = []
        for exchange_key, stats in sorted(exchange_stats.items(), key=lambda x: abs(x[1]['buy_vol'] - x[1]['sell_vol']), reverse=True):
            net_vol = stats['buy_vol'] - stats['sell_vol']
            indicator = "🟢" if net_vol > 0 else "🔴" if net_vol < 0 else "⚪"
            exchange_lines.append(
                f"{indicator} *{exchange_key}*: {stats['buy'] + stats['sell']} trades | Net: {net_vol:+,.0f} ALKIMI"
            )

        message = f"""*📊 Trading Activity Report - {period_str.title()}*

*{position_emoji} Overall Position:* {position_text}

*Total Activity:*
• Trades: {total_buys + total_sells:,}
• Buys: {total_buys} ({total_buy_vol:,.0f} ALKIMI)
• Sells: {total_sells} ({total_sell_vol:,.0f} ALKIMI)

*Exchange Breakdown:*
{chr(10).join(exchange_lines) if exchange_lines else '• No activity'}"""

        if all_trades and (total_buys > 0 or total_sells > 0):
            message += "\n\n*Price Summary:*"
            if total_buys > 0:
                message += f"\n• Avg Buy: ${avg_buy_price:.6f}"
            if total_sells > 0:
                message += f"\n• Avg Sell: ${avg_sell_price:.6f}"
            if total_buys > 0 and total_sells > 0:
                message += f"\n• Spread: ${spread:.6f} ({spread_pct:+.2f}%)"

        await slack_client.send_message({"text": message})
        print("\n✓ Report posted to Slack")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Check recent trading activity')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--hours', type=int, default=6, help='Number of hours to check (default: 6)')
    group.add_argument('--days', type=int, help='Number of days to check')
    parser.add_argument('--slack', action='store_true', help='Post results to Slack')

    args = parser.parse_args()

    asyncio.run(check_recent_activity(hours=args.hours, days=args.days, post_to_slack=args.slack))
