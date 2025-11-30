"""
Pull trades from all exchanges within a specific time range.
"""

import asyncio
import sys
import os
from datetime import datetime, timezone

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from config.settings import settings
from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient


async def pull_trades_in_range():
    """Pull all trades within the specified time range."""

    # Define time range
    start_time = datetime(2025, 11, 4, 0, 0, 0, tzinfo=timezone.utc)
    end_time = datetime(2025, 11, 5, 10, 0, 0, tzinfo=timezone.utc)

    print(f"\n{'='*80}")
    print(f"Pulling Trades from All Exchanges")
    print(f"Time Range: {start_time.strftime('%Y-%m-%d %H:%M:%S UTC')} to {end_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print(f"{'='*80}\n")

    # Create exchange instances with multi-account support
    exchange_classes = [
        ('mexc', 'MEXC', MEXCClient),
        ('kraken', 'Kraken', KrakenClient),
        ('kucoin', 'KuCoin', KuCoinClient),
        ('gateio', 'Gate.io', GateioClient),
    ]

    all_trades = []
    exchanges = []

    # Initialize all exchange accounts
    for exchange_key, display_name, exchange_class in exchange_classes:
        try:
            # Get all accounts for this exchange
            accounts = settings.get_exchange_accounts(exchange_key)

            if not accounts:
                print(f"⚠️  No accounts configured for {display_name}, skipping...\n")
                continue

            # Create an instance for each account
            for account_config in accounts:
                account_name = account_config['account_name']
                try:
                    exchange = exchange_class(
                        config=account_config,
                        account_name=account_name
                    )
                    await exchange.initialize()
                    exchanges.append((f"{display_name} ({account_name})", exchange))
                    print(f"✓ Initialized {display_name} ({account_name})")
                except Exception as e:
                    print(f"✗ Failed to initialize {display_name} ({account_name}): {e}")

        except Exception as e:
            print(f"✗ Failed to initialize {display_name} exchange: {e}")

    print(f"\n{'='*80}")
    print("Fetching Trades...")
    print(f"{'='*80}\n")

    # Fetch trades from each exchange
    for name, exchange in exchanges:
        print(f"\nFetching from {name}...")
        try:
            # Fetch trades since start_time
            trades = await exchange.get_trades(start_time)

            # Filter to only trades within our time range
            filtered_trades = [
                t for t in trades
                if start_time <= t.timestamp <= end_time
            ]

            print(f"✓ Found {len(filtered_trades)} trades in time range (out of {len(trades)} total since start)")

            # Add exchange and account info to each trade
            for trade in filtered_trades:
                trade.exchange_name = name

            all_trades.extend(filtered_trades)

        except Exception as e:
            print(f"✗ Error fetching trades: {e}")
        finally:
            try:
                await exchange.close()
            except:
                pass

    # Sort all trades by timestamp
    all_trades.sort(key=lambda t: t.timestamp)

    # Display summary
    print(f"\n{'='*80}")
    print(f"Trade Summary")
    print(f"{'='*80}\n")
    print(f"Total Trades: {len(all_trades)}")

    if all_trades:
        # Group by exchange
        from collections import defaultdict
        by_exchange = defaultdict(list)
        for trade in all_trades:
            by_exchange[trade.exchange_name].append(trade)

        print(f"\nBreakdown by Exchange:")
        for exchange_name in sorted(by_exchange.keys()):
            trades_list = by_exchange[exchange_name]
            buys = sum(1 for t in trades_list if t.side.value == 'buy')
            sells = sum(1 for t in trades_list if t.side.value == 'sell')
            print(f"  {exchange_name}: {len(trades_list)} trades ({buys} buys, {sells} sells)")

        # Calculate totals
        total_buys = sum(1 for t in all_trades if t.side.value == 'buy')
        total_sells = sum(1 for t in all_trades if t.side.value == 'sell')

        buy_volume = sum(t.amount * t.price for t in all_trades if t.side.value == 'buy')
        sell_volume = sum(t.amount * t.price for t in all_trades if t.side.value == 'sell')
        total_fees = sum(t.fee for t in all_trades)

        print(f"\nOverall Totals:")
        print(f"  Buys: {total_buys} trades, ${buy_volume:,.2f} volume")
        print(f"  Sells: {total_sells} trades, ${sell_volume:,.2f} volume")
        print(f"  Total Fees: ${total_fees:.2f}")

        # Show detailed trades
        print(f"\n{'='*80}")
        print(f"Detailed Trade List")
        print(f"{'='*80}\n")

        for i, trade in enumerate(all_trades, 1):
            print(f"\nTrade #{i}")
            print(f"  Time: {trade.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            print(f"  Exchange: {trade.exchange_name}")
            print(f"  Symbol: {trade.symbol}")
            print(f"  Side: {trade.side.value.upper()}")
            print(f"  Amount: {trade.amount:,.2f}")
            print(f"  Price: ${trade.price:.6f}")
            print(f"  Total: ${trade.amount * trade.price:,.2f}")
            print(f"  Fee: ${trade.fee:.4f}")
            print(f"  Order ID: {trade.order_id}")
    else:
        print("\n⚠️  No trades found in the specified time range")

    print(f"\n{'='*80}")
    print("Complete")
    print(f"{'='*80}\n")


if __name__ == '__main__':
    asyncio.run(pull_trades_in_range())
