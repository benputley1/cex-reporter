"""
Mock data generator for CEX Reporter
Provides realistic test data for development and testing without API keys
"""
import random
from datetime import datetime, timedelta
from typing import Dict, List, Optional
from uuid import uuid4

from src.exchanges.base import Trade, TradeSide


# Exchange-specific balance configurations
MOCK_BALANCES = {
    'mexc': {
        'USDT': 50000.00,
        'ALKIMI': 1500000.00,
    },
    'kraken': {
        'USDT': 75000.00,  # Note: Kraken actually uses 'USD' not 'USDT', mapping handled in client
        'ALKIMI': 0.00,  # Not listed on Kraken
    },
    'kucoin': {
        'USDT': 30000.00,
        'ALKIMI': 800000.00,
    },
    'gateio': {
        'USDT': 45000.00,
        'ALKIMI': 1200000.00,
    },
}

# Current market prices (in USD)
MOCK_PRICES = {
    'USDT': 1.00,
    'ALKIMI': 0.20,
    'BTC': 67500.00,
    'ETH': 3200.00,
}

# Price ranges for generating historical data
PRICE_RANGES = {
    'USDT': (0.998, 1.002),
    'ALKIMI': (0.15, 0.25),
}


def get_mock_balances(exchange: str) -> Dict[str, float]:
    """
    Get mock balances for an exchange

    Args:
        exchange: Exchange name (mexc, kraken, kucoin, gateio)

    Returns:
        Dictionary mapping asset symbols to amounts
    """
    exchange = exchange.lower()
    if exchange not in MOCK_BALANCES:
        raise ValueError(f"Unknown exchange: {exchange}")

    return MOCK_BALANCES[exchange].copy()


def get_mock_prices(symbols: List[str]) -> Dict[str, float]:
    """
    Get current mock prices for symbols

    Args:
        symbols: List of asset symbols (e.g., ["USDT", "ALKIMI"])

    Returns:
        Dictionary mapping symbols to USD prices
    """
    prices = {}
    for symbol in symbols:
        if symbol in MOCK_PRICES:
            prices[symbol] = MOCK_PRICES[symbol]
        else:
            # Return a default price if not found
            prices[symbol] = 1.0

    return prices


def generate_random_trades(
    exchange: str,
    symbols: List[str],
    count: int,
    start_date: datetime,
    end_date: Optional[datetime] = None
) -> List[Trade]:
    """
    Generate random realistic trades for testing

    Args:
        exchange: Exchange name
        symbols: List of symbols to generate trades for (e.g., ["USDT", "ALKIMI"])
        count: Number of trades to generate per symbol
        start_date: Start date for trade history
        end_date: End date for trade history (defaults to now)

    Returns:
        List of Trade objects sorted by timestamp
    """
    if end_date is None:
        end_date = datetime.now()

    trades = []
    time_delta = (end_date - start_date).total_seconds()

    for symbol in symbols:
        # Skip ALKIMI on Kraken (not listed)
        if exchange.lower() == 'kraken' and symbol == 'ALKIMI':
            continue

        # Determine price range for this symbol
        price_range = PRICE_RANGES.get(symbol, (0.1, 1.0))

        for i in range(count):
            # Random timestamp within range
            random_seconds = random.uniform(0, time_delta)
            trade_timestamp = start_date + timedelta(seconds=random_seconds)

            # Alternate between buy and sell, with some randomness
            trade_side = TradeSide.BUY if (i % 2 == 0) else TradeSide.SELL
            if random.random() > 0.8:  # 20% chance to flip
                trade_side = TradeSide.SELL if trade_side == TradeSide.BUY else TradeSide.BUY

            # Generate price with some trend (slightly increasing over time)
            progress = random_seconds / time_delta
            price_min, price_max = price_range
            trend_factor = 1.0 + (progress * 0.2)  # Up to 20% increase over time
            base_price = random.uniform(price_min, price_max) * trend_factor
            # Add some volatility (±5%)
            price = base_price * random.uniform(0.95, 1.05)

            # Generate trade amount (varying sizes)
            if symbol == 'ALKIMI':
                # ALKIMI trades: 1000 to 50000 tokens
                amount = random.uniform(1000, 50000)
            elif symbol == 'USDT':
                # USDT trades: 100 to 10000
                amount = random.uniform(100, 10000)
            else:
                # Default
                amount = random.uniform(10, 1000)

            # Round to reasonable precision
            amount = round(amount, 2)
            price = round(price, 6)

            # Calculate fee (0.1% typical, in USDT equivalent)
            cost = price * amount
            fee = round(cost * 0.001, 4)

            # Determine fee currency (usually USDT)
            fee_currency = 'USDT'

            trade = Trade(
                timestamp=trade_timestamp,
                symbol=symbol,
                side=trade_side,
                amount=amount,
                price=price,
                fee=fee,
                fee_currency=fee_currency,
                trade_id=f"{exchange}_{symbol}_{uuid4().hex[:12]}"
            )

            trades.append(trade)

    # Sort by timestamp
    trades.sort(key=lambda t: t.timestamp)

    return trades


def get_mock_trades(
    exchange: str,
    since: datetime,
    symbols: Optional[List[str]] = None
) -> List[Trade]:
    """
    Get mock trades for an exchange

    Args:
        exchange: Exchange name
        since: Start date for trade history
        symbols: Optional list of symbols to fetch (defaults to tracked assets)

    Returns:
        List of Trade objects sorted by timestamp
    """
    exchange = exchange.lower()

    # Default to USDT and ALKIMI if not specified
    if symbols is None:
        symbols = ['USDT', 'ALKIMI']

    # Don't generate trades for ALKIMI on Kraken (not listed)
    if exchange == 'kraken':
        symbols = [s for s in symbols if s != 'ALKIMI']

    # Generate different number of trades per exchange
    trade_counts = {
        'mexc': 15,
        'kraken': 10,  # Fewer since ALKIMI not listed
        'kucoin': 12,
        'gateio': 13,
    }

    count = trade_counts.get(exchange, 10)

    # Generate trades
    trades = generate_random_trades(
        exchange=exchange,
        symbols=symbols,
        count=count,
        start_date=since
    )

    return trades


def get_all_mock_trades(
    since: datetime,
    symbols: Optional[List[str]] = None
) -> Dict[str, List[Trade]]:
    """
    Get all mock trades across all exchanges

    Args:
        since: Start date for trade history
        symbols: Optional list of symbols to fetch

    Returns:
        Dictionary mapping exchange names to lists of trades
    """
    if symbols is None:
        symbols = ['USDT', 'ALKIMI']

    all_trades = {}

    for exchange in MOCK_BALANCES.keys():
        trades = get_mock_trades(exchange, since, symbols)
        all_trades[exchange] = trades

    return all_trades


def get_mock_trade_summary(since: datetime) -> Dict[str, Dict]:
    """
    Get summary statistics of mock trades

    Args:
        since: Start date for trade history

    Returns:
        Dictionary with trade statistics per exchange
    """
    all_trades = get_all_mock_trades(since)

    summary = {}
    for exchange, trades in all_trades.items():
        buy_volume = sum(t.price * t.amount for t in trades if t.side == TradeSide.BUY)
        sell_volume = sum(t.price * t.amount for t in trades if t.side == TradeSide.SELL)
        total_fees = sum(t.fee for t in trades if t.fee_currency == 'USDT')

        # Separate by symbol
        usdt_trades = [t for t in trades if t.symbol == 'USDT']
        alkimi_trades = [t for t in trades if t.symbol == 'ALKIMI']

        summary[exchange] = {
            'total_trades': len(trades),
            'buy_trades': len([t for t in trades if t.side == TradeSide.BUY]),
            'sell_trades': len([t for t in trades if t.side == TradeSide.SELL]),
            'buy_volume_usd': round(buy_volume, 2),
            'sell_volume_usd': round(sell_volume, 2),
            'net_volume_usd': round(buy_volume - sell_volume, 2),
            'total_fees_usdt': round(total_fees, 4),
            'usdt_trades': len(usdt_trades),
            'alkimi_trades': len(alkimi_trades),
            'avg_alkimi_price': round(
                sum(t.price for t in alkimi_trades) / len(alkimi_trades), 6
            ) if alkimi_trades else 0,
        }

    return summary


def get_portfolio_summary() -> Dict:
    """
    Get summary of current portfolio across all exchanges

    Returns:
        Dictionary with portfolio statistics
    """
    total_usdt = sum(balances.get('USDT', 0) for balances in MOCK_BALANCES.values())
    total_alkimi = sum(balances.get('ALKIMI', 0) for balances in MOCK_BALANCES.values())

    alkimi_price = MOCK_PRICES['ALKIMI']
    usdt_price = MOCK_PRICES['USDT']

    total_value_usd = (total_usdt * usdt_price) + (total_alkimi * alkimi_price)

    return {
        'total_usdt': round(total_usdt, 2),
        'total_alkimi': round(total_alkimi, 2),
        'usdt_price': usdt_price,
        'alkimi_price': alkimi_price,
        'total_value_usd': round(total_value_usd, 2),
        'alkimi_value_usd': round(total_alkimi * alkimi_price, 2),
        'usdt_value_usd': round(total_usdt * usdt_price, 2),
        'exchanges': list(MOCK_BALANCES.keys()),
    }


# Pre-generate a consistent set of mock trades for repeatability
_CACHED_TRADES: Dict[str, List[Trade]] = {}


def initialize_mock_trades(seed: int = 42):
    """
    Initialize and cache mock trades with a specific random seed for consistency

    Args:
        seed: Random seed for reproducible data
    """
    global _CACHED_TRADES

    random.seed(seed)
    start_date = datetime(2025, 8, 19, 0, 0, 0)

    exchanges = ['mexc', 'kraken', 'kucoin', 'gateio']
    symbols = ['USDT', 'ALKIMI']

    for exchange in exchanges:
        key = exchange
        _CACHED_TRADES[key] = get_mock_trades(
            exchange=exchange,
            since=start_date,
            symbols=symbols
        )

    # Reset random seed
    random.seed()


def get_cached_trades(exchange: str, since: Optional[datetime] = None) -> List[Trade]:
    """
    Get cached trades for an exchange (for consistency across calls)

    Args:
        exchange: Exchange name
        since: Optional filter for trades since this date

    Returns:
        List of Trade objects
    """
    if exchange not in _CACHED_TRADES:
        initialize_mock_trades()

    trades = _CACHED_TRADES.get(exchange, [])

    # Filter by since date if specified
    if since:
        trades = [t for t in trades if t.timestamp >= since]

    return trades


# Initialize on import for consistency
initialize_mock_trades()


if __name__ == '__main__':
    """
    Demo script to show mock data capabilities
    """
    print("=" * 60)
    print("CEX Reporter - Mock Data Demo")
    print("=" * 60)

    # Show balances
    print("\n📊 Current Balances:")
    print("-" * 60)
    for exchange in MOCK_BALANCES.keys():
        balances = get_mock_balances(exchange)
        print(f"\n{exchange.upper()}:")
        for asset, amount in balances.items():
            if amount > 0:
                price = MOCK_PRICES.get(asset, 0)
                value = amount * price
                print(f"  {asset:10s}: {amount:>15,.2f} (${value:>12,.2f})")

    # Show portfolio summary
    print("\n" + "=" * 60)
    print("💼 Portfolio Summary:")
    print("-" * 60)
    portfolio = get_portfolio_summary()
    print(f"Total USDT:   {portfolio['total_usdt']:>15,.2f} @ ${portfolio['usdt_price']:.2f}")
    print(f"Total ALKIMI: {portfolio['total_alkimi']:>15,.0f} @ ${portfolio['alkimi_price']:.2f}")
    print(f"\nTotal Value:  ${portfolio['total_value_usd']:>14,.2f}")

    # Show trade summary
    print("\n" + "=" * 60)
    print("📈 Trade History Summary (since 2025-08-19):")
    print("-" * 60)
    start_date = datetime(2025, 8, 19, 0, 0, 0)
    trade_summary = get_mock_trade_summary(start_date)

    for exchange, stats in trade_summary.items():
        print(f"\n{exchange.upper()}:")
        print(f"  Total Trades:    {stats['total_trades']:>6}")
        print(f"  Buy/Sell:        {stats['buy_trades']:>3} / {stats['sell_trades']:<3}")
        print(f"  USDT/ALKIMI:     {stats['usdt_trades']:>3} / {stats['alkimi_trades']:<3}")
        print(f"  Buy Volume:      ${stats['buy_volume_usd']:>12,.2f}")
        print(f"  Sell Volume:     ${stats['sell_volume_usd']:>12,.2f}")
        print(f"  Net Volume:      ${stats['net_volume_usd']:>12,.2f}")
        print(f"  Total Fees:      ${stats['total_fees_usdt']:>12,.4f}")
        if stats['alkimi_trades'] > 0:
            print(f"  Avg ALKIMI Price: ${stats['avg_alkimi_price']:>11,.6f}")

    # Show sample trades
    print("\n" + "=" * 60)
    print("📝 Sample Trades (first 5 from MEXC):")
    print("-" * 60)
    mexc_trades = get_cached_trades('mexc')[:5]
    for trade in mexc_trades:
        print(f"\n{trade.timestamp.strftime('%Y-%m-%d %H:%M:%S')} | "
              f"{trade.symbol:6s} | {trade.side.value.upper():4s} | "
              f"Amount: {trade.amount:>10,.2f} | "
              f"Price: ${trade.price:>8,.6f} | "
              f"Fee: ${trade.fee:>7,.4f}")

    print("\n" + "=" * 60)
