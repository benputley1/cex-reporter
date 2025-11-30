#!/usr/bin/env python3
"""
Example usage of QueryEngine for the ALKIMI Slack bot.

This demonstrates how to:
1. Execute direct SQL queries
2. Generate SQL from natural language (requires Claude API)
3. Handle results and errors
4. Get schema and sample data
"""

import asyncio
import sys
import os
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Direct import to avoid dependency issues
import importlib.util
spec = importlib.util.spec_from_file_location('query_engine', 'src/bot/query_engine.py')
query_engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(query_engine)


async def example_direct_sql():
    """Example: Execute SQL directly."""
    print("\n" + "="*70)
    print("Example 1: Direct SQL Execution")
    print("="*70)

    engine = query_engine.QueryEngine(db_path="data/trade_cache.db")

    # Query 1: Get recent trades
    print("\n--- Recent Trades ---")
    sql = """
        SELECT
            timestamp, exchange, side, amount, price,
            (amount * price) as value_usd
        FROM trades
        ORDER BY timestamp DESC
        LIMIT 5
    """

    result = await engine.execute_sql(sql)

    if result.success:
        print(f"✓ Found {result.row_count} trades (took {result.execution_time_ms}ms)")
        print(result.data.to_string())
    else:
        print(f"✗ Error: {result.error}")

    # Query 2: Trading volume by exchange
    print("\n--- Volume by Exchange ---")
    sql = """
        SELECT
            exchange,
            COUNT(*) as trade_count,
            SUM(amount * price) as total_volume_usd,
            AVG(amount * price) as avg_trade_size_usd,
            MIN(timestamp) as first_trade,
            MAX(timestamp) as last_trade
        FROM trades
        GROUP BY exchange
        ORDER BY total_volume_usd DESC
        LIMIT 10
    """

    result = await engine.execute_sql(sql)

    if result.success:
        print(f"✓ Found {result.row_count} exchanges")
        print(result.data.to_string())
    else:
        print(f"✗ Error: {result.error}")


async def example_natural_language():
    """Example: Generate SQL from natural language using Claude API."""
    print("\n" + "="*70)
    print("Example 2: Natural Language Queries (requires Claude API)")
    print("="*70)

    # Check if API key is available
    api_key = os.getenv('ANTHROPIC_API_KEY')
    if not api_key:
        print("\n⚠ ANTHROPIC_API_KEY not set - skipping NL examples")
        print("  Set the API key to test natural language queries:")
        print("  export ANTHROPIC_API_KEY='sk-ant-...'")
        return

    # Import ClaudeClient
    try:
        from src.bot.prompts import ClaudeClient
    except ImportError as e:
        print(f"\n⚠ Could not import ClaudeClient: {e}")
        print("  This example requires the full application dependencies")
        return

    # Create engine with Claude client
    claude = ClaudeClient(api_key=api_key)
    engine = query_engine.QueryEngine(
        db_path="data/trade_cache.db",
        claude_client=claude
    )

    # Test natural language queries
    nl_queries = [
        "Show me the top 10 largest trades by value",
        "What is the average trade size for each exchange?",
        "How many trades happened in the last 7 days?",
        "Show me all sell trades over $1000",
    ]

    for nl_query in nl_queries:
        print(f"\n--- Query: {nl_query} ---")

        result = await engine.generate_and_execute(nl_query)

        if result.success:
            print(f"✓ Success! Generated SQL:")
            print(f"  {result.sql}")
            print(f"  Found {result.row_count} rows in {result.execution_time_ms}ms")
            print(result.data.to_string())
        else:
            print(f"✗ Error: {result.error}")


async def example_schema_inspection():
    """Example: Get schema and sample data."""
    print("\n" + "="*70)
    print("Example 3: Schema Inspection")
    print("="*70)

    engine = query_engine.QueryEngine(db_path="data/trade_cache.db")

    # Get schema info
    print("\n--- Database Schema ---")
    schema = await engine.get_schema_info()

    for table, columns in schema.items():
        print(f"\nTable: {table}")
        print(f"  Columns ({len(columns)}): {', '.join(columns)}")

    # Get sample data
    print("\n--- Sample Data from 'trades' ---")
    sample = await engine.sample_data('trades', limit=3)

    if not sample.empty:
        print(sample.to_string())
    else:
        print("No sample data available")

    # Get table stats
    print("\n--- Table Statistics ---")
    stats = await engine.get_table_stats('trades')

    for key, value in stats.items():
        print(f"  {key}: {value}")


async def example_error_handling():
    """Example: Proper error handling."""
    print("\n" + "="*70)
    print("Example 4: Error Handling")
    print("="*70)

    engine = query_engine.QueryEngine(db_path="data/trade_cache.db")

    # Test various error scenarios
    test_cases = [
        ("Empty query", ""),
        ("Not a SELECT", "UPDATE trades SET amount=0"),
        ("Invalid table", "SELECT * FROM fake_table"),
        ("SQL injection attempt", "SELECT * FROM trades WHERE 1=1; DROP TABLE trades"),
    ]

    for name, sql in test_cases:
        print(f"\n--- {name} ---")
        result = await engine.execute_sql(sql)

        if result.success:
            print(f"✗ UNEXPECTED: Query should have failed!")
        else:
            print(f"✓ Properly rejected: {result.error}")


async def example_slack_bot_integration():
    """Example: How this would be used in the Slack bot."""
    print("\n" + "="*70)
    print("Example 5: Slack Bot Integration Pattern")
    print("="*70)

    # This shows the pattern that would be used in slack_bot.py

    engine = query_engine.QueryEngine(db_path="data/trade_cache.db")

    # Simulate user asking a question
    user_query = "Show me trades from mexc exchange today"

    print(f"\nUser asks: {user_query}")
    print("\nBot response:")

    # Option 1: Direct SQL (if user is technical)
    sql = """
        SELECT timestamp, side, amount, price, (amount * price) as value_usd
        FROM trades
        WHERE exchange = 'mexc'
        AND date(timestamp) = date('now')
        ORDER BY timestamp DESC
        LIMIT 20
    """

    result = await engine.execute_sql(sql)

    if result.success:
        if result.row_count == 0:
            print("No trades found matching your criteria.")
        else:
            print(f"Found {result.row_count} trades from MEXC today:")
            print(result.data.to_string())
            print(f"\n(Query executed in {result.execution_time_ms}ms)")
    else:
        print(f"Sorry, I encountered an error: {result.error}")

    # Option 2: With natural language (requires Claude API)
    # result = await engine.generate_and_execute(user_query)


async def main():
    """Run all examples."""
    print("\n" + "="*70)
    print("QueryEngine Usage Examples for ALKIMI Slack Bot")
    print("="*70)

    await example_direct_sql()
    await example_schema_inspection()
    await example_error_handling()
    await example_slack_bot_integration()
    await example_natural_language()  # Last because it requires API key

    print("\n" + "="*70)
    print("Examples complete!")
    print("="*70)


if __name__ == "__main__":
    asyncio.run(main())
