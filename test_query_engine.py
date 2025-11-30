#!/usr/bin/env python3
"""
Quick test script for query_engine.py

Tests:
1. SQL validation (safe vs unsafe queries)
2. Table extraction
3. Query execution (if database exists)
4. Schema inspection
"""

import asyncio
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.bot.query_engine import SQLValidator, QueryEngine, validate_sql


def test_sql_validation():
    """Test SQL validation logic."""
    print("\n=== Testing SQL Validation ===")

    validator = SQLValidator()

    # Test safe queries
    safe_queries = [
        "SELECT * FROM trades LIMIT 10",
        "SELECT COUNT(*) FROM trades WHERE exchange='mexc'",
        "SELECT exchange, SUM(amount) FROM trades GROUP BY exchange LIMIT 100",
        "SELECT * FROM trades WHERE timestamp >= datetime('now', '-7 days') LIMIT 50",
    ]

    for sql in safe_queries:
        is_valid, error = validator.validate(sql)
        status = "✓" if is_valid else "✗"
        print(f"{status} {sql[:60]}...")
        if not is_valid:
            print(f"  ERROR: {error}")

    # Test unsafe queries
    print("\n--- Testing Unsafe Queries (should fail) ---")
    unsafe_queries = [
        "DROP TABLE trades",
        "DELETE FROM trades WHERE id=1",
        "UPDATE trades SET amount=0",
        "INSERT INTO trades VALUES (...)",
        "SELECT * FROM trades; DROP TABLE trades",
        "SELECT * FROM unknown_table",
        "CREATE TABLE foo (id INT)",
    ]

    for sql in unsafe_queries:
        is_valid, error = validator.validate(sql)
        status = "✓" if not is_valid else "✗"
        print(f"{status} {sql[:60]}... → {error}")


def test_table_extraction():
    """Test table name extraction."""
    print("\n=== Testing Table Extraction ===")

    validator = SQLValidator()

    test_cases = [
        ("SELECT * FROM trades", ["trades"]),
        ("SELECT * FROM trades t JOIN pnl_config p ON t.id=p.id", ["trades", "pnl_config"]),
        ("SELECT COUNT(*) FROM query_history", ["query_history"]),
    ]

    for sql, expected in test_cases:
        tables = validator.extract_tables(sql)
        match = set(tables) == set(expected)
        status = "✓" if match else "✗"
        print(f"{status} {sql[:50]}... → {tables}")


def test_sanitization():
    """Test SQL sanitization (LIMIT enforcement)."""
    print("\n=== Testing SQL Sanitization ===")

    validator = SQLValidator()

    test_cases = [
        ("SELECT * FROM trades", "LIMIT"),
        ("SELECT * FROM trades LIMIT 50", "LIMIT 50"),
        ("SELECT * FROM trades LIMIT 200", f"LIMIT {validator.MAX_ROWS}"),  # Should reduce to MAX_ROWS
    ]

    for sql, expected_in_result in test_cases:
        sanitized = validator.sanitize(sql)
        has_expected = expected_in_result in sanitized
        status = "✓" if has_expected else "✗"
        print(f"{status} {sql[:40]}... → {sanitized}")


async def test_query_execution():
    """Test actual query execution if database exists."""
    print("\n=== Testing Query Execution ===")

    db_path = "data/trade_cache.db"
    if not Path(db_path).exists():
        print(f"⚠ Database not found at {db_path}, skipping execution tests")
        return

    engine = QueryEngine(db_path=db_path)

    # Test simple query
    print("\n--- Simple SELECT ---")
    result = await engine.execute_sql("SELECT * FROM trades LIMIT 3")

    if result.success:
        print(f"✓ Query succeeded: {result.row_count} rows in {result.execution_time_ms}ms")
        print(f"  Columns: {list(result.data.columns)}")
        print(f"  SQL: {result.sql}")
    else:
        print(f"✗ Query failed: {result.error}")

    # Test schema info
    print("\n--- Schema Info ---")
    schema = await engine.get_schema_info()
    for table, columns in schema.items():
        print(f"  {table}: {len(columns)} columns")
        print(f"    {', '.join(columns[:5])}...")

    # Test table stats
    print("\n--- Table Stats ---")
    stats = await engine.get_table_stats('trades')
    for key, value in stats.items():
        print(f"  {key}: {value}")


async def main():
    """Run all tests."""
    print("=" * 70)
    print("Query Engine Test Suite")
    print("=" * 70)

    test_sql_validation()
    test_table_extraction()
    test_sanitization()
    await test_query_execution()

    print("\n" + "=" * 70)
    print("Tests complete!")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(main())
