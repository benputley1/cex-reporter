"""
Example usage of mock data module for CEX Reporter

This demonstrates how to use the mock data module for testing and development
without needing actual exchange API keys.
"""
from datetime import datetime
from src.utils.mock_data import (
    get_mock_balances,
    get_mock_prices,
    get_mock_trades,
    get_all_mock_trades,
    get_mock_trade_summary,
    get_portfolio_summary,
    get_cached_trades,
)


def example_balances():
    """Example: Fetch balances for all exchanges"""
    print("\n" + "=" * 60)
    print("Example 1: Fetching Balances")
    print("=" * 60)

    exchanges = ['mexc', 'kraken', 'kucoin', 'gateio']

    for exchange in exchanges:
        balances = get_mock_balances(exchange)
        print(f"\n{exchange.upper()}:")
        for asset, amount in balances.items():
            if amount > 0:
                print(f"  {asset}: {amount:,.2f}")


def example_prices():
    """Example: Fetch current prices"""
    print("\n" + "=" * 60)
    print("Example 2: Fetching Prices")
    print("=" * 60)

    symbols = ['USDT', 'ALKIMI']
    prices = get_mock_prices(symbols)

    print("\nCurrent Prices:")
    for symbol, price in prices.items():
        print(f"  {symbol}/USD: ${price:.6f}")


def example_trades():
    """Example: Fetch trade history for a single exchange"""
    print("\n" + "=" * 60)
    print("Example 3: Fetching Trade History")
    print("=" * 60)

    start_date = datetime(2025, 8, 19, 0, 0, 0)
    trades = get_mock_trades('mexc', start_date)

    print(f"\nTotal trades for MEXC since {start_date.date()}: {len(trades)}")
    print("\nFirst 5 trades:")
    for trade in trades[:5]:
        print(f"  {trade.timestamp.strftime('%Y-%m-%d %H:%M')} | "
              f"{trade.symbol:6s} | {trade.side.value.upper():4s} | "
              f"Amount: {trade.amount:>10,.2f} | "
              f"Price: ${trade.price:.6f}")


def example_all_trades():
    """Example: Fetch trades across all exchanges"""
    print("\n" + "=" * 60)
    print("Example 4: Fetching All Trades")
    print("=" * 60)

    start_date = datetime(2025, 8, 19, 0, 0, 0)
    all_trades = get_all_mock_trades(start_date)

    print(f"\nTrades across all exchanges since {start_date.date()}:")
    for exchange, trades in all_trades.items():
        print(f"  {exchange.upper():8s}: {len(trades):3d} trades")


def example_trade_summary():
    """Example: Get trade summary statistics"""
    print("\n" + "=" * 60)
    print("Example 5: Trade Summary Statistics")
    print("=" * 60)

    start_date = datetime(2025, 8, 19, 0, 0, 0)
    summary = get_mock_trade_summary(start_date)

    print(f"\nTrade statistics since {start_date.date()}:\n")
    for exchange, stats in summary.items():
        print(f"{exchange.upper()}:")
        print(f"  Total Trades:     {stats['total_trades']:>6}")
        print(f"  Buy Volume:       ${stats['buy_volume_usd']:>12,.2f}")
        print(f"  Sell Volume:      ${stats['sell_volume_usd']:>12,.2f}")
        print(f"  Net Volume:       ${stats['net_volume_usd']:>12,.2f}")
        print(f"  Total Fees:       ${stats['total_fees_usdt']:>12,.4f}")
        if stats['alkimi_trades'] > 0:
            print(f"  Avg ALKIMI Price: ${stats['avg_alkimi_price']:>11,.6f}")
        print()


def example_portfolio_summary():
    """Example: Get portfolio summary"""
    print("\n" + "=" * 60)
    print("Example 6: Portfolio Summary")
    print("=" * 60)

    portfolio = get_portfolio_summary()

    print("\nTotal Holdings:")
    print(f"  USDT:   {portfolio['total_usdt']:>15,.2f} @ ${portfolio['usdt_price']:.2f}")
    print(f"  ALKIMI: {portfolio['total_alkimi']:>15,.0f} @ ${portfolio['alkimi_price']:.2f}")

    print("\nValue Breakdown:")
    print(f"  USDT Value:   ${portfolio['usdt_value_usd']:>12,.2f}")
    print(f"  ALKIMI Value: ${portfolio['alkimi_value_usd']:>12,.2f}")
    print(f"  Total Value:  ${portfolio['total_value_usd']:>12,.2f}")

    print(f"\nTracking {len(portfolio['exchanges'])} exchanges: "
          f"{', '.join(portfolio['exchanges'])}")


def example_filtered_trades():
    """Example: Filter trades by date"""
    print("\n" + "=" * 60)
    print("Example 7: Filtering Trades by Date")
    print("=" * 60)

    # Get all trades
    start_date = datetime(2025, 8, 19, 0, 0, 0)
    all_trades = get_cached_trades('mexc')

    # Filter for September only
    sept_start = datetime(2025, 9, 1, 0, 0, 0)
    sept_end = datetime(2025, 10, 1, 0, 0, 0)
    sept_trades = [t for t in all_trades if sept_start <= t.timestamp < sept_end]

    print(f"\nMEXC Trades:")
    print(f"  Total trades (since {start_date.date()}): {len(all_trades)}")
    print(f"  September trades only: {len(sept_trades)}")

    # Calculate September statistics
    buy_volume = sum(t.price * t.amount for t in sept_trades
                     if t.side.value == 'buy')
    sell_volume = sum(t.price * t.amount for t in sept_trades
                      if t.side.value == 'sell')

    print(f"\nSeptember Statistics:")
    print(f"  Buy Volume:  ${buy_volume:>10,.2f}")
    print(f"  Sell Volume: ${sell_volume:>10,.2f}")
    print(f"  Net Volume:  ${buy_volume - sell_volume:>10,.2f}")


def example_calculating_pnl():
    """Example: Calculate simple P&L from trades"""
    print("\n" + "=" * 60)
    print("Example 8: Calculating P&L")
    print("=" * 60)

    start_date = datetime(2025, 8, 19, 0, 0, 0)
    trades = get_cached_trades('mexc')

    # Focus on ALKIMI trades only
    alkimi_trades = [t for t in trades if t.symbol == 'ALKIMI']

    total_bought = 0
    total_bought_cost = 0
    total_sold = 0
    total_sold_revenue = 0
    total_fees = 0

    for trade in alkimi_trades:
        cost = trade.price * trade.amount
        total_fees += trade.fee

        if trade.side.value == 'buy':
            total_bought += trade.amount
            total_bought_cost += cost
        else:  # sell
            total_sold += trade.amount
            total_sold_revenue += cost

    avg_buy_price = total_bought_cost / total_bought if total_bought > 0 else 0
    avg_sell_price = total_sold_revenue / total_sold if total_sold > 0 else 0

    net_alkimi = total_bought - total_sold
    realized_pnl = total_sold_revenue - (total_sold * avg_buy_price)
    unrealized_pnl = net_alkimi * (0.20 - avg_buy_price)  # Current price = $0.20

    print(f"\nALKIMI Trading Analysis (MEXC):")
    print(f"  Trades:           {len(alkimi_trades)}")
    print(f"  Bought:           {total_bought:>12,.2f} @ ${avg_buy_price:.6f}")
    print(f"  Sold:             {total_sold:>12,.2f} @ ${avg_sell_price:.6f}")
    print(f"  Net Position:     {net_alkimi:>12,.2f} ALKIMI")
    print(f"\n  Total Fees:       ${total_fees:>11,.4f}")
    print(f"  Realized P&L:     ${realized_pnl:>11,.2f}")
    print(f"  Unrealized P&L:   ${unrealized_pnl:>11,.2f}")
    print(f"  Total P&L:        ${realized_pnl + unrealized_pnl - total_fees:>11,.2f}")


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("CEX Reporter - Mock Data Usage Examples")
    print("=" * 60)

    example_balances()
    example_prices()
    example_trades()
    example_all_trades()
    example_trade_summary()
    example_portfolio_summary()
    example_filtered_trades()
    example_calculating_pnl()

    print("\n" + "=" * 60)
    print("Examples Complete!")
    print("=" * 60 + "\n")


if __name__ == '__main__':
    main()
