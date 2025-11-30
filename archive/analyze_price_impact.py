"""
Analyze ALKIMI sales during recent price movements
"""
import asyncio
from datetime import datetime, timedelta
from collections import defaultdict
from src.data.trade_cache import TradeCache

async def analyze_price_impact():
    """Analyze recent trading activity and price movements"""

    cache = TradeCache()

    # Get all trades from the last 30 days
    since = datetime.now() - timedelta(days=30)
    all_trades = cache.get_trades(since=since)

    if not all_trades:
        print("No trades found in cache")
        return

    # Sort by timestamp
    all_trades.sort(key=lambda t: t.timestamp)

    print("=" * 80)
    print("ALKIMI TRADING ANALYSIS - PRICE MOVEMENTS & MARKET IMPACT")
    print("=" * 80)

    # Group trades by day
    daily_data = defaultdict(lambda: {
        'trades': [],
        'buy_volume': 0,
        'sell_volume': 0,
        'buy_count': 0,
        'sell_count': 0,
        'total_buy_usdt': 0,
        'total_sell_usdt': 0
    })

    for trade in all_trades:
        date = trade.timestamp.date()
        daily_data[date]['trades'].append(trade)

        if trade.side.value == 'sell':
            daily_data[date]['sell_volume'] += trade.amount
            daily_data[date]['sell_count'] += 1
            daily_data[date]['total_sell_usdt'] += trade.cost
        else:
            daily_data[date]['buy_volume'] += trade.amount
            daily_data[date]['buy_count'] += 1
            daily_data[date]['total_buy_usdt'] += trade.cost

    # Calculate daily prices and identify movements
    daily_prices = {}
    for date, data in sorted(daily_data.items()):
        trades = data['trades']
        avg_price = sum(t.price for t in trades) / len(trades)
        daily_prices[date] = {
            'avg_price': avg_price,
            'high': max(t.price for t in trades),
            'low': min(t.price for t in trades),
            'volume': data['sell_volume'] + data['buy_volume']
        }

    # Print daily summary
    print("\nDAILY TRADING SUMMARY:")
    print("-" * 80)
    print(f"{'Date':<12} {'Avg Price':<12} {'High':<12} {'Low':<12} {'Sell Vol':<15} {'Buy Vol':<15}")
    print("-" * 80)

    sorted_dates = sorted(daily_prices.keys())
    for i, date in enumerate(sorted_dates):
        price_data = daily_prices[date]
        trade_data = daily_data[date]

        # Calculate price change
        if i > 0:
            prev_date = sorted_dates[i-1]
            prev_price = daily_prices[prev_date]['avg_price']
            price_change = ((price_data['avg_price'] - prev_price) / prev_price) * 100
            indicator = "🟢" if price_change > 0 else "🔴" if price_change < 0 else "⚪"
        else:
            price_change = 0
            indicator = "⚪"

        print(f"{date} {indicator} ${price_data['avg_price']:.6f} "
              f"${price_data['high']:.6f} ${price_data['low']:.6f} "
              f"{trade_data['sell_volume']:>12,.0f} {trade_data['buy_volume']:>12,.0f} "
              f"({price_change:+.1f}%)")

    # Identify upward moves (consecutive days with price increases)
    print("\n" + "=" * 80)
    print("UPWARD PRICE MOVEMENTS ANALYSIS")
    print("=" * 80)

    upward_moves = []
    current_move = None

    for i in range(1, len(sorted_dates)):
        current_date = sorted_dates[i]
        prev_date = sorted_dates[i-1]

        current_price = daily_prices[current_date]['avg_price']
        prev_price = daily_prices[prev_date]['avg_price']
        price_change = ((current_price - prev_price) / prev_price) * 100

        if price_change > 0:  # Price went up
            if current_move is None:
                current_move = {
                    'start_date': prev_date,
                    'end_date': current_date,
                    'start_price': prev_price,
                    'current_price': current_price,
                    'days': 1,
                    'sell_volume': daily_data[current_date]['sell_volume'],
                    'buy_volume': daily_data[current_date]['buy_volume'],
                    'sell_usdt': daily_data[current_date]['total_sell_usdt'],
                    'buy_usdt': daily_data[current_date]['total_buy_usdt']
                }
            else:
                current_move['end_date'] = current_date
                current_move['current_price'] = current_price
                current_move['days'] += 1
                current_move['sell_volume'] += daily_data[current_date]['sell_volume']
                current_move['buy_volume'] += daily_data[current_date]['buy_volume']
                current_move['sell_usdt'] += daily_data[current_date]['total_sell_usdt']
                current_move['buy_usdt'] += daily_data[current_date]['total_buy_usdt']
        else:
            if current_move is not None:
                upward_moves.append(current_move)
                current_move = None

    # Add the last move if it's still ongoing
    if current_move is not None:
        upward_moves.append(current_move)

    if not upward_moves:
        print("\nNo upward price movements detected in the last 30 days")
        return

    # Analyze each upward move
    for i, move in enumerate(upward_moves, 1):
        price_change_pct = ((move['current_price'] - move['start_price']) / move['start_price']) * 100

        print(f"\nUpward Move #{i}:")
        print(f"  Period: {move['start_date']} to {move['end_date']} ({move['days']} days)")
        print(f"  Price: ${move['start_price']:.6f} → ${move['current_price']:.6f} ({price_change_pct:+.1f}%)")
        print(f"  Your Sells: {move['sell_volume']:,.0f} ALKIMI (${move['sell_usdt']:,.2f})")
        print(f"  Your Buys:  {move['buy_volume']:,.0f} ALKIMI (${move['buy_usdt']:,.2f})")
        print(f"  Net Position: {move['buy_volume'] - move['sell_volume']:+,.0f} ALKIMI")

    # Focus on the most recent upward move
    if upward_moves:
        latest_move = upward_moves[-1]
        print("\n" + "=" * 80)
        print("LATEST UPWARD MOVE - MARKET IMPACT ANALYSIS")
        print("=" * 80)

        price_change_pct = ((latest_move['current_price'] - latest_move['start_price']) / latest_move['start_price']) * 100

        print(f"\nPeriod: {latest_move['start_date']} to {latest_move['end_date']}")
        print(f"Duration: {latest_move['days']} day(s)")
        print(f"Price Movement: ${latest_move['start_price']:.6f} → ${latest_move['current_price']:.6f} ({price_change_pct:+.2f}%)")
        print(f"\nYour Trading Activity:")
        print(f"  Sold: {latest_move['sell_volume']:,.0f} ALKIMI for ${latest_move['sell_usdt']:,.2f}")
        print(f"  Bought: {latest_move['buy_volume']:,.0f} ALKIMI for ${latest_move['buy_usdt']:,.2f}")
        print(f"  Net: {latest_move['buy_volume'] - latest_move['sell_volume']:+,.0f} ALKIMI")

        if latest_move['sell_volume'] > 0:
            avg_sell_price = latest_move['sell_usdt'] / latest_move['sell_volume']
            print(f"  Avg Sell Price: ${avg_sell_price:.6f}")

        # Estimate market impact
        print("\nPOTENTIAL MARKET IMPACT:")
        print("-" * 80)

        # Get detailed trades during the move
        move_trades = []
        for date in sorted_dates:
            if latest_move['start_date'] <= date <= latest_move['end_date']:
                move_trades.extend(daily_data[date]['trades'])

        # Group by exchange to see where the selling happened
        exchange_sells = defaultdict(lambda: {'volume': 0, 'usdt': 0})
        for trade in move_trades:
            if trade.side.value == 'sell':
                exchange_sells[trade.exchange_name]['volume'] += trade.amount
                exchange_sells[trade.exchange_name]['usdt'] += trade.cost

        print("\nSells by Exchange:")
        for exchange, data in sorted(exchange_sells.items(), key=lambda x: x[1]['volume'], reverse=True):
            if data['volume'] > 0:
                avg_price = data['usdt'] / data['volume']
                print(f"  {exchange:10s}: {data['volume']:>12,.0f} ALKIMI @ ${avg_price:.6f} = ${data['usdt']:>10,.2f}")

        # Analysis
        print("\nIMPACT ASSESSMENT:")
        if latest_move['sell_volume'] > latest_move['buy_volume']:
            net_sell = latest_move['sell_volume'] - latest_move['buy_volume']
            print(f"  ⚠️  Net seller during price increase")
            print(f"  Your accounts were net sellers of {net_sell:,.0f} ALKIMI ({net_sell / latest_move['sell_volume'] * 100:.1f}% of sells)")
            print(f"  This selling pressure likely dampened the upward momentum")
            print(f"  Without your sells, the price may have increased more than {price_change_pct:.1f}%")
        elif latest_move['buy_volume'] > latest_move['sell_volume']:
            net_buy = latest_move['buy_volume'] - latest_move['sell_volume']
            print(f"  ✓ Net buyer during price increase")
            print(f"  Your accounts accumulated {net_buy:,.0f} ALKIMI during the move")
            print(f"  This buying pressure supported the {price_change_pct:.1f}% price increase")
        else:
            print(f"  ⚪ Market neutral (equal buys and sells)")
            print(f"  Your market making activity had minimal directional impact")

    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(analyze_price_impact())
