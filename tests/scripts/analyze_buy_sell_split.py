"""
Analyze buy/sell order split across all exchange accounts.
"""

import asyncio
import sys
import os
from datetime import datetime, timezone
from collections import defaultdict

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from config.settings import settings
from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient


async def analyze_buy_sell_split():
    """Analyze the buy/sell order distribution."""

    # October 2025
    from datetime import timedelta
    start_date = datetime(2025, 10, 1, 0, 0, 0, tzinfo=timezone.utc)
    end_date = datetime(2025, 10, 31, 23, 59, 59, tzinfo=timezone.utc)

    print(f"\n{'='*80}")
    print("Buy/Sell Order Analysis")
    print(f"Period: October 2025")
    print(f"From: {start_date.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"To:   {end_date.strftime('%Y-%m-%d %H:%M UTC')}")
    print(f"{'='*80}\n")

    # Create exchange instances with multi-account support
    exchange_classes = [
        ('mexc', 'MEXC', MEXCClient),
        ('kraken', 'Kraken', KrakenClient),
        ('kucoin', 'KuCoin', KuCoinClient),
        ('gateio', 'Gate.io', GateioClient),
    ]

    exchanges = []
    historical_start = start_date

    # Initialize all exchange accounts
    print("Initializing exchanges...")
    for exchange_key, display_name, exchange_class in exchange_classes:
        try:
            accounts = settings.get_exchange_accounts(exchange_key)
            if not accounts:
                continue

            for account_config in accounts:
                account_name = account_config['account_name']
                try:
                    exchange = exchange_class(
                        config=account_config,
                        account_name=account_name
                    )
                    await exchange.initialize()
                    exchanges.append((f"{display_name} ({account_name})", exchange))
                    print(f"  ✓ {display_name} ({account_name})")
                except Exception as e:
                    print(f"  ✗ {display_name} ({account_name}): {e}")
        except Exception as e:
            print(f"  ✗ {display_name}: {e}")

    print(f"\n{'='*80}")
    print("Fetching Trade Data...")
    print(f"{'='*80}\n")

    # Collect data by exchange
    exchange_stats = defaultdict(lambda: {'buys': 0, 'sells': 0, 'buy_volume': 0, 'sell_volume': 0})
    total_buys = 0
    total_sells = 0
    total_buy_volume = 0
    total_sell_volume = 0

    for name, exchange in exchanges:
        try:
            all_trades = await exchange.get_trades(historical_start)

            # Filter to only trades within the time range
            # Handle both timezone-aware and naive datetimes
            trades = []
            for t in all_trades:
                ts = t.timestamp
                # Make timezone-aware if naive
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                if start_date <= ts <= end_date:
                    trades.append(t)

            buys = sum(1 for t in trades if t.side.value == 'buy')
            sells = sum(1 for t in trades if t.side.value == 'sell')
            buy_volume = sum(t.amount * t.price for t in trades if t.side.value == 'buy')
            sell_volume = sum(t.amount * t.price for t in trades if t.side.value == 'sell')

            exchange_stats[name] = {
                'buys': buys,
                'sells': sells,
                'buy_volume': buy_volume,
                'sell_volume': sell_volume,
                'total': buys + sells
            }

            total_buys += buys
            total_sells += sells
            total_buy_volume += buy_volume
            total_sell_volume += sell_volume

            print(f"{name}: {len(trades)} trades ({buys} buys, {sells} sells)")

        except Exception as e:
            print(f"{name}: ✗ Error - {e}")
        finally:
            try:
                await exchange.close()
            except:
                pass

    total_trades = total_buys + total_sells
    total_volume = total_buy_volume + total_sell_volume

    # Display results
    print(f"\n{'='*80}")
    print("Overall Statistics")
    print(f"{'='*80}\n")

    if total_trades > 0:
        buy_pct = (total_buys / total_trades) * 100
        sell_pct = (total_sells / total_trades) * 100

        print(f"Total Trades: {total_trades:,}")
        print(f"\nOrder Count:")
        print(f"  Buy Orders:  {total_buys:,} ({buy_pct:.2f}%)")
        print(f"  Sell Orders: {total_sells:,} ({sell_pct:.2f}%)")

        if total_volume > 0:
            buy_vol_pct = (total_buy_volume / total_volume) * 100
            sell_vol_pct = (total_sell_volume / total_volume) * 100

            print(f"\nVolume (USD):")
            print(f"  Buy Volume:  ${total_buy_volume:,.2f} ({buy_vol_pct:.2f}%)")
            print(f"  Sell Volume: ${total_sell_volume:,.2f} ({sell_vol_pct:.2f}%)")
            print(f"  Total Volume: ${total_volume:,.2f}")

        # Show breakdown by exchange
        print(f"\n{'='*80}")
        print("Breakdown by Exchange Account")
        print(f"{'='*80}\n")

        for name in sorted(exchange_stats.keys()):
            stats = exchange_stats[name]
            if stats['total'] > 0:
                buy_pct = (stats['buys'] / stats['total']) * 100
                sell_pct = (stats['sells'] / stats['total']) * 100

                print(f"\n{name}")
                print(f"  Total: {stats['total']:,} trades")
                print(f"  Buys:  {stats['buys']:,} ({buy_pct:.1f}%)")
                print(f"  Sells: {stats['sells']:,} ({sell_pct:.1f}%)")

                if stats['buy_volume'] + stats['sell_volume'] > 0:
                    vol_total = stats['buy_volume'] + stats['sell_volume']
                    buy_vol_pct = (stats['buy_volume'] / vol_total) * 100
                    sell_vol_pct = (stats['sell_volume'] / vol_total) * 100
                    print(f"  Buy Volume:  ${stats['buy_volume']:,.2f} ({buy_vol_pct:.1f}%)")
                    print(f"  Sell Volume: ${stats['sell_volume']:,.2f} ({sell_vol_pct:.1f}%)")

    else:
        print("No trades found in historical period")

    print(f"\n{'='*80}")
    print("Analysis Complete")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    asyncio.run(analyze_buy_sell_split())
