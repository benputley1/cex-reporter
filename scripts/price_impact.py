"""
Analyze price movements and market impact of recent trading

Usage:
  python scripts/price_impact.py            # Last 6 hours (default)
  python scripts/price_impact.py --hours 24 # Last 24 hours
  python scripts/price_impact.py --days 7   # Last 7 days
  python scripts/price_impact.py --slack    # Also post to Slack
"""
import asyncio
import argparse
import sqlite3
from datetime import datetime, timedelta
from collections import defaultdict
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.reporting.slack import SlackClient
from config.settings import settings


async def analyze_price_impact_async(hours: int = 6, days: int = None, post_to_slack: bool = False):
    """Async wrapper for analyze_price_impact to support Slack posting"""
    result = analyze_price_impact(hours, days)

    # Post to Slack if requested and we have data
    if post_to_slack and result:
        slack_client = SlackClient()
        await slack_client.send_message({"text": result['slack_message']})
        print("\n✓ Report posted to Slack")


def analyze_price_impact(hours: int = 6, days: int = None):
    """Analyze recent price movements and trading impact"""

    # Calculate time window
    if days:
        since = datetime.now() - timedelta(days=days)
        period_str = f"last {days} day(s)"
    else:
        since = datetime.now() - timedelta(hours=hours)
        period_str = f"last {hours} hour(s)"

    print("=" * 80)
    print(f"PRICE IMPACT ANALYSIS - {period_str.upper()}")
    print("=" * 80)
    print(f"Period: {since.strftime('%Y-%m-%d %H:%M:%S')} to now")
    print()

    # Connect to trade cache database
    db_path = Path(__file__).parent.parent / "data" / "trade_cache.db"

    if not db_path.exists():
        print("❌ Trade cache database not found. Run main.py first to populate cache.")
        return

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    # Query trades from database
    cursor = conn.execute("""
        SELECT
            exchange,
            account_name,
            timestamp,
            side,
            amount,
            price
        FROM trades
        WHERE timestamp >= ?
        ORDER BY timestamp ASC
    """, (since.isoformat(),))

    trades = cursor.fetchall()

    if not trades:
        print(f"No trades found in {period_str}")
        return

    # Group trades by hour
    hourly_data = defaultdict(lambda: {
        'buy_count': 0, 'sell_count': 0,
        'buy_vol': 0, 'sell_vol': 0,
        'buy_usdt': 0, 'sell_usdt': 0,
        'prices': []
    })

    exchange_totals = defaultdict(lambda: {'buy': 0, 'sell': 0, 'buy_vol': 0, 'sell_vol': 0})

    for trade in trades:
        timestamp = datetime.fromisoformat(trade['timestamp'])
        hour_key = timestamp.replace(minute=0, second=0, microsecond=0)

        side = trade['side']
        amount = trade['amount']
        price = trade['price']
        usdt_value = amount * price

        hourly_data[hour_key]['prices'].append(price)

        if side == 'buy':
            hourly_data[hour_key]['buy_count'] += 1
            hourly_data[hour_key]['buy_vol'] += amount
            hourly_data[hour_key]['buy_usdt'] += usdt_value
            exchange_totals[trade['exchange']]['buy'] += 1
            exchange_totals[trade['exchange']]['buy_vol'] += amount
        else:
            hourly_data[hour_key]['sell_count'] += 1
            hourly_data[hour_key]['sell_vol'] += amount
            hourly_data[hour_key]['sell_usdt'] += usdt_value
            exchange_totals[trade['exchange']]['sell'] += 1
            exchange_totals[trade['exchange']]['sell_vol'] += amount

    conn.close()

    # Calculate totals
    total_buy_count = sum(h['buy_count'] for h in hourly_data.values())
    total_sell_count = sum(h['sell_count'] for h in hourly_data.values())
    total_buy_vol = sum(h['buy_vol'] for h in hourly_data.values())
    total_sell_vol = sum(h['sell_vol'] for h in hourly_data.values())
    total_buy_usdt = sum(h['buy_usdt'] for h in hourly_data.values())
    total_sell_usdt = sum(h['sell_usdt'] for h in hourly_data.values())

    # Print overall summary
    print("OVERALL SUMMARY:")
    print("-" * 80)
    print(f"Total Trades: {total_buy_count + total_sell_count:,}")
    print(f"  Buys:  {total_buy_count:>5} trades | {total_buy_vol:>15,.0f} ALKIMI | ${total_buy_usdt:>12,.2f}")
    print(f"  Sells: {total_sell_count:>5} trades | {total_sell_vol:>15,.0f} ALKIMI | ${total_sell_usdt:>12,.2f}")
    print(f"  Net:   {total_buy_vol - total_sell_vol:>+15,.0f} ALKIMI | ${total_buy_usdt - total_sell_usdt:>+12,.2f}")

    # Price analysis
    all_prices = [p for h in hourly_data.values() for p in h['prices']]
    if all_prices:
        min_price = min(all_prices)
        max_price = max(all_prices)
        avg_price = sum(all_prices) / len(all_prices)
        latest_price = all_prices[-1]

        print(f"\nPRICE RANGE:")
        print("-" * 80)
        print(f"  Low:     ${min_price:.6f}")
        print(f"  High:    ${max_price:.6f}")
        print(f"  Average: ${avg_price:.6f}")
        print(f"  Latest:  ${latest_price:.6f}")
        print(f"  Range:   ${max_price - min_price:.6f} ({((max_price - min_price) / min_price * 100):.2f}%)")

    # Exchange breakdown
    print(f"\nBREAKDOWN BY EXCHANGE:")
    print("-" * 80)
    print(f"{'Exchange':<15} {'Buys':<10} {'Buy Vol':<18} {'Sells':<10} {'Sell Vol':<18} {'Net Vol':<18}")
    print("-" * 80)

    for exchange, stats in sorted(exchange_totals.items()):
        net_vol = stats['buy_vol'] - stats['sell_vol']
        indicator = "🟢" if net_vol > 0 else "🔴" if net_vol < 0 else "⚪"

        print(f"{indicator} {exchange:<13} "
              f"{stats['buy']:<10} {stats['buy_vol']:<18,.0f} "
              f"{stats['sell']:<10} {stats['sell_vol']:<18,.0f} "
              f"{net_vol:<+18,.0f}")

    # Hourly breakdown
    if len(hourly_data) > 0:
        print(f"\nHOURLY BREAKDOWN:")
        print("-" * 80)
        print(f"{'Hour':<20} {'Avg Price':<12} {'Buys':<8} {'Sells':<8} {'Net Vol':<18}")
        print("-" * 80)

        for hour in sorted(hourly_data.keys()):
            data = hourly_data[hour]
            avg_price = sum(data['prices']) / len(data['prices']) if data['prices'] else 0
            net_vol = data['buy_vol'] - data['sell_vol']
            indicator = "🟢" if net_vol > 0 else "🔴" if net_vol < 0 else "⚪"

            print(f"{hour.strftime('%Y-%m-%d %H:%M')} {indicator} "
                  f"${avg_price:<10.6f} "
                  f"{data['buy_count']:<8} {data['sell_count']:<8} "
                  f"{net_vol:<+18,.0f}")

    # Market impact assessment
    print(f"\nMARKET IMPACT ASSESSMENT:")
    print("-" * 80)

    net_position = total_buy_vol - total_sell_vol

    if net_position > 0:
        pct_of_total = (net_position / total_buy_vol * 100) if total_buy_vol > 0 else 0
        print(f"  Position: NET BUYER")
        print(f"  Accumulated: {net_position:,.0f} ALKIMI")
        print(f"  Impact: Your buying created {pct_of_total:.1f}% upward pressure")
        if total_buy_count > 0:
            avg_buy = total_buy_usdt / total_buy_vol
            print(f"  Average Buy Price: ${avg_buy:.6f}")
    elif net_position < 0:
        net_sell = abs(net_position)
        pct_of_total = (net_sell / total_sell_vol * 100) if total_sell_vol > 0 else 0
        print(f"  Position: NET SELLER")
        print(f"  Sold: {net_sell:,.0f} ALKIMI (${total_sell_usdt - total_buy_usdt:,.2f})")
        print(f"  Impact: Your selling created {pct_of_total:.1f}% downward pressure")
        if total_sell_count > 0:
            avg_sell = total_sell_usdt / total_sell_vol
            print(f"  Average Sell Price: ${avg_sell:.6f}")
    else:
        print(f"  Position: MARKET NEUTRAL")
        print(f"  Impact: Balanced market making with minimal directional impact")

    if total_buy_count > 0 and total_sell_count > 0:
        avg_buy = total_buy_usdt / total_buy_vol
        avg_sell = total_sell_usdt / total_sell_vol
        spread = avg_sell - avg_buy
        spread_pct = (spread / avg_buy) * 100
        print(f"\n  Spread Captured: ${spread:.6f} ({spread_pct:+.2f}%)")

    print("\n" + "=" * 80)

    # Build Slack message
    if net_position > 0:
        position_emoji = "🟢"
        position_text = f"NET BUYER (+{net_position:,.0f} ALKIMI)"
    elif net_position < 0:
        position_emoji = "🔴"
        position_text = f"NET SELLER ({abs(net_position):,.0f} ALKIMI)"
    else:
        position_emoji = "⚪"
        position_text = "MARKET NEUTRAL"

    # Build exchange breakdown
    exchange_lines = []
    for exchange, stats in sorted(exchange_totals.items(), key=lambda x: abs(x[1]['buy_vol'] - x[1]['sell_vol']), reverse=True):
        net_vol = stats['buy_vol'] - stats['sell_vol']
        indicator = "🟢" if net_vol > 0 else "🔴" if net_vol < 0 else "⚪"
        exchange_lines.append(
            f"{indicator} *{exchange}*: {stats['buy'] + stats['sell']} trades | Net: {net_vol:+,.0f} ALKIMI"
        )

    slack_message = f"""*📈 Price Impact Analysis - {period_str.title()}*

*{position_emoji} Position:* {position_text}

*Summary:*
• Total Trades: {total_buy_count + total_sell_count:,}
• Buys: {total_buy_count} ({total_buy_vol:,.0f} ALKIMI | ${total_buy_usdt:,.2f})
• Sells: {total_sell_count} ({total_sell_vol:,.0f} ALKIMI | ${total_sell_usdt:,.2f})

*Price Range:*
• Low: ${min_price:.6f} | High: ${max_price:.6f}
• Average: ${avg_price:.6f} | Latest: ${latest_price:.6f}
• Range: {((max_price - min_price) / min_price * 100):.2f}%

*Exchange Activity:*
{chr(10).join(exchange_lines) if exchange_lines else '• No activity'}"""

    if total_buy_count > 0 and total_sell_count > 0:
        slack_message += f"\n\n*Spread Captured:* ${spread:.6f} ({spread_pct:+.2f}%)"

    return {
        'slack_message': slack_message,
        'net_position': net_position,
        'total_trades': total_buy_count + total_sell_count
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Analyze price impact of recent trading')
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--hours', type=int, default=6, help='Number of hours to analyze (default: 6)')
    group.add_argument('--days', type=int, help='Number of days to analyze')
    parser.add_argument('--slack', action='store_true', help='Post results to Slack')

    args = parser.parse_args()

    if args.slack:
        asyncio.run(analyze_price_impact_async(hours=args.hours, days=args.days, post_to_slack=True))
    else:
        analyze_price_impact(hours=args.hours, days=args.days)
