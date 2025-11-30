"""
Example usage of Python executor and function store.

This demonstrates how to integrate sandboxed Python execution
into the ALKIMI Slack bot for custom trader analysis.
"""

import asyncio
from datetime import datetime
from src.bot.python_executor import SafePythonExecutor
from src.bot.function_store import FunctionStore


class ExampleDataProvider:
    """Example data provider (replace with real implementation)."""

    async def load_trades(self, **kwargs):
        """Load trade data."""
        import pandas as pd
        from datetime import timedelta

        # Mock data - replace with actual database queries
        return pd.DataFrame({
            'timestamp': [datetime.now() - timedelta(days=i) for i in range(30)],
            'exchange': ['binance'] * 15 + ['kraken'] * 15,
            'asset': ['BTC'] * 10 + ['ETH'] * 10 + ['BTC'] * 10,
            'amount': [1.0 + i * 0.1 for i in range(30)],
            'price': [50000.0 + i * 100 for i in range(30)],
            'side': ['buy', 'sell'] * 15
        })

    async def get_all_balances(self):
        """Get current balances."""
        return {
            'binance': {'BTC': 10.5, 'ETH': 150.0, 'USDT': 50000},
            'kraken': {'BTC': 5.2, 'ETH': 75.5, 'USDT': 25000}
        }

    async def get_balance_snapshots(self, days):
        """Get balance history."""
        from datetime import timedelta
        return [
            {
                'timestamp': datetime.now() - timedelta(days=i),
                'total_usd': 1000000 + i * 1000,
                'binance_usd': 600000 + i * 600,
                'kraken_usd': 400000 + i * 400
            }
            for i in range(days)
        ]


async def example_basic_execution():
    """Example: Basic code execution."""
    print("\n=== Example 1: Basic Execution ===")

    provider = ExampleDataProvider()
    executor = SafePythonExecutor(provider)

    # Simple calculation
    code = """
result = sum(range(1, 101))
print(f"Sum of 1-100: {result}")
"""

    result = await executor.execute(code)
    if result.success:
        print(f"Result: {result.result}")
        print(f"Output: {result.output}")
        print(f"Execution time: {result.execution_time_ms}ms")
    else:
        print(f"Error: {result.error}")


async def example_load_trades():
    """Example: Load and analyze trade data."""
    print("\n=== Example 2: Trade Analysis ===")

    provider = ExampleDataProvider()
    executor = SafePythonExecutor(provider)

    code = """
# Load all trades
df = load_trades()

# Calculate volume by exchange
volume_by_exchange = df.groupby('exchange')['amount'].sum()

# Calculate total volume
total_volume = df['amount'].sum()

# Calculate average trade size
avg_trade_size = df['amount'].mean()

result = {
    'total_volume': total_volume,
    'avg_trade_size': avg_trade_size,
    'by_exchange': volume_by_exchange.to_dict()
}

print(f"Total trades: {len(df)}")
print(f"Total volume: {total_volume:.2f}")
"""

    result = await executor.execute(code)
    if result.success:
        print(f"Analysis result: {result.result}")
        print(f"Console output:\n{result.output}")
    else:
        print(f"Error: {result.error}")


async def example_balance_analysis():
    """Example: Balance analysis."""
    print("\n=== Example 3: Balance Analysis ===")

    provider = ExampleDataProvider()
    executor = SafePythonExecutor(provider)

    code = """
import pandas as pd

# Load balances
balances = load_balances()

# Calculate total BTC across exchanges
total_btc = sum(
    exchange_balances.get('BTC', 0)
    for exchange_balances in balances.values()
)

# Calculate total ETH
total_eth = sum(
    exchange_balances.get('ETH', 0)
    for exchange_balances in balances.values()
)

result = {
    'total_btc': total_btc,
    'total_eth': total_eth,
    'exchanges': len(balances)
}

print(f"Total BTC: {total_btc}")
print(f"Total ETH: {total_eth}")
"""

    result = await executor.execute(code)
    if result.success:
        print(f"Balance summary: {result.result}")
        print(f"Output: {result.output}")


async def example_time_series_analysis():
    """Example: Time series analysis of balance snapshots."""
    print("\n=== Example 4: Time Series Analysis ===")

    provider = ExampleDataProvider()
    executor = SafePythonExecutor(provider)

    code = """
import pandas as pd
import statistics

# Load 30 days of snapshots
snapshots = load_snapshots(days=30)

# Convert to DataFrame
df = pd.DataFrame(snapshots)
df['timestamp'] = pd.to_datetime(df['timestamp'])

# Calculate daily change
df = df.sort_values('timestamp')
df['daily_change'] = df['total_usd'].diff()
df['daily_change_pct'] = df['total_usd'].pct_change() * 100

# Statistics
avg_balance = df['total_usd'].mean()
max_balance = df['total_usd'].max()
min_balance = df['total_usd'].min()
volatility = df['daily_change_pct'].std()

result = {
    'avg_balance': avg_balance,
    'max_balance': max_balance,
    'min_balance': min_balance,
    'volatility_pct': volatility,
    'current_balance': df.iloc[-1]['total_usd'],
    'change_30d': df.iloc[-1]['total_usd'] - df.iloc[0]['total_usd']
}

print(f"30-day statistics:")
print(f"  Average: ${avg_balance:,.2f}")
print(f"  Max: ${max_balance:,.2f}")
print(f"  Min: ${min_balance:,.2f}")
print(f"  Volatility: {volatility:.2f}%")
"""

    result = await executor.execute(code)
    if result.success:
        print(f"Results: {result.result}")
        print(f"\nOutput:\n{result.output}")


async def example_function_store():
    """Example: Save and reuse functions."""
    print("\n=== Example 5: Function Store ===")

    provider = ExampleDataProvider()
    executor = SafePythonExecutor(provider)
    store = FunctionStore(db_path=":memory:")

    # Save a function
    volume_code = """
df = load_trades()
result = df.groupby('exchange')['amount'].sum().to_dict()
"""

    await store.save(
        name="volume_by_exchange",
        code=volume_code,
        description="Calculate trading volume by exchange",
        created_by="U123456"
    )

    # Save another function
    balance_code = """
balances = load_balances()
result = {
    'btc': sum(b.get('BTC', 0) for b in balances.values()),
    'eth': sum(b.get('ETH', 0) for b in balances.values())
}
"""

    await store.save(
        name="total_crypto",
        code=balance_code,
        description="Calculate total BTC and ETH across exchanges",
        created_by="U123456"
    )

    # List all functions
    print("Saved functions:")
    functions = await store.list_all()
    for func in functions:
        print(f"  - {func.name}: {func.description}")

    # Execute a saved function
    print("\nExecuting 'volume_by_exchange'...")
    func = await store.get("volume_by_exchange")
    result = await executor.execute(func.code)
    await store.update_usage("volume_by_exchange")

    if result.success:
        print(f"Result: {result.result}")

    # Get stats
    stats = await store.get_stats()
    print(f"\nStore stats:")
    print(f"  Total functions: {stats['total_functions']}")
    print(f"  Total uses: {stats['total_uses']}")


async def example_complex_analysis():
    """Example: Complex multi-step analysis."""
    print("\n=== Example 6: Complex Analysis ===")

    provider = ExampleDataProvider()
    executor = SafePythonExecutor(provider)

    code = """
import pandas as pd
import numpy as np
from datetime import timedelta

# Load trades
trades = load_trades()
trades['timestamp'] = pd.to_datetime(trades['timestamp'])

# Load balances
balances = load_balances()

# Calculate trade statistics by asset
trade_stats = trades.groupby('asset').agg({
    'amount': ['count', 'sum', 'mean'],
    'price': ['mean', 'min', 'max']
}).round(2)

# Calculate current holdings value
current_value = {}
for exchange, assets in balances.items():
    for asset, amount in assets.items():
        if asset != 'USDT':
            # Get latest price from trades
            asset_trades = trades[trades['asset'] == asset]
            if len(asset_trades) > 0:
                latest_price = asset_trades.iloc[0]['price']
                current_value[asset] = current_value.get(asset, 0) + (amount * latest_price)

# Calculate win rate (simplified)
trades['value'] = trades['amount'] * trades['price']
buy_value = trades[trades['side'] == 'buy']['value'].sum()
sell_value = trades[trades['side'] == 'sell']['value'].sum()
pnl = sell_value - buy_value

result = {
    'total_trades': len(trades),
    'assets_traded': trades['asset'].nunique(),
    'exchanges': trades['exchange'].nunique(),
    'total_buy_value': buy_value,
    'total_sell_value': sell_value,
    'pnl': pnl,
    'current_holdings_value': sum(current_value.values()),
    'trade_stats': trade_stats.to_dict()
}

print(f"Analyzed {len(trades)} trades across {trades['exchange'].nunique()} exchanges")
print(f"P&L: ${pnl:,.2f}")
"""

    result = await executor.execute(code)
    if result.success:
        print(f"Analysis complete!")
        print(f"Output: {result.output}")
        print(f"Execution time: {result.execution_time_ms}ms")
        print(f"\nP&L: ${result.result['pnl']:,.2f}")
    else:
        print(f"Error: {result.error}")


async def example_error_handling():
    """Example: Error handling."""
    print("\n=== Example 7: Error Handling ===")

    provider = ExampleDataProvider()
    executor = SafePythonExecutor(provider)

    # Example 1: Validation error
    print("1. Testing forbidden import...")
    code = "import os\nresult = os.getcwd()"
    result = await executor.execute(code)
    print(f"   Success: {result.success}")
    print(f"   Error: {result.error}")

    # Example 2: Runtime error
    print("\n2. Testing runtime error...")
    code = "result = 1 / 0"
    result = await executor.execute(code)
    print(f"   Success: {result.success}")
    print(f"   Error: {result.error}")

    # Example 3: Valid code
    print("\n3. Testing valid code...")
    code = "result = 42"
    result = await executor.execute(code)
    print(f"   Success: {result.success}")
    print(f"   Result: {result.result}")


async def example_search_functions():
    """Example: Search saved functions."""
    print("\n=== Example 8: Search Functions ===")

    store = FunctionStore(db_path=":memory:")

    # Create sample functions
    functions = [
        ("calc_volume", "df = load_trades(); result = df['amount'].sum()", "Calculate total volume"),
        ("calc_avg_price", "df = load_trades(); result = df['price'].mean()", "Calculate average price"),
        ("check_balance", "result = load_balances()", "Check current balances"),
        ("volume_by_day", "df = load_trades(); result = df.groupby(df['timestamp'].dt.date)['amount'].sum()", "Daily volume")
    ]

    for name, code, desc in functions:
        await store.save(name, code, desc, "U123")

    # Search for volume-related functions
    print("Searching for 'volume'...")
    results = await store.search("volume")
    for func in results:
        print(f"  - {func.name}: {func.description}")

    # Search for calc functions
    print("\nSearching for 'calc'...")
    results = await store.search("calc")
    for func in results:
        print(f"  - {func.name}: {func.description}")


async def main():
    """Run all examples."""
    print("=" * 60)
    print("Python Executor Examples for ALKIMI Slack Bot")
    print("=" * 60)

    await example_basic_execution()
    await example_load_trades()
    await example_balance_analysis()
    await example_time_series_analysis()
    await example_function_store()
    await example_complex_analysis()
    await example_error_handling()
    await example_search_functions()

    print("\n" + "=" * 60)
    print("Examples complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
