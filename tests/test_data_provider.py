"""
Unit tests for DataProvider class.

Tests the unified data access layer functionality.
"""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from pathlib import Path
import tempfile
import shutil

from src.bot.data_provider import DataProvider
from src.exchanges.base import Trade, TradeSide


class TestDataProvider:
    """Test suite for DataProvider class."""

    @pytest.fixture
    async def provider(self):
        """Create a temporary DataProvider instance for testing."""
        # Create temporary directories
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_cache.db"
        snapshots_dir = Path(temp_dir) / "snapshots"
        snapshots_dir.mkdir()

        # Initialize provider
        provider = DataProvider(
            db_path=str(db_path),
            snapshots_dir=str(snapshots_dir),
            sui_config=None  # Disable Sui for unit tests
        )

        yield provider

        # Cleanup
        await provider.close()
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_initialization(self, provider):
        """Test DataProvider initialization."""
        assert provider is not None
        assert provider.trade_cache is not None
        assert provider.snapshot_manager is not None
        assert provider.coingecko is not None

    @pytest.mark.asyncio
    async def test_database_migrations(self, provider):
        """Test that all required tables are created."""
        import sqlite3

        with sqlite3.connect(provider.db_path) as conn:
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )
            tables = {row[0] for row in cursor.fetchall()}

            # Check all expected tables exist
            assert 'trades' in tables
            assert 'query_history' in tables
            assert 'saved_functions' in tables
            assert 'pnl_config' in tables
            assert 'otc_transactions' in tables

    @pytest.mark.asyncio
    async def test_get_trades_df_empty(self, provider):
        """Test getting trades when database is empty."""
        df = await provider.get_trades_df()

        assert isinstance(df, pd.DataFrame)
        assert df.empty
        # Check schema is correct
        expected_columns = [
            'timestamp', 'exchange', 'account_name', 'symbol',
            'side', 'amount', 'price', 'fee', 'fee_currency', 'trade_id'
        ]
        assert list(df.columns) == expected_columns

    @pytest.mark.asyncio
    async def test_get_trades_df_with_data(self, provider):
        """Test getting trades with data in cache."""
        # Add test trades
        test_trades = [
            Trade(
                timestamp=datetime.now() - timedelta(hours=1),
                symbol='ALKIMI',
                side=TradeSide.BUY,
                amount=1000.0,
                price=0.027,
                fee=0.027,
                fee_currency='USDT',
                trade_id='test_1',
                exchange='test_exchange'
            ),
            Trade(
                timestamp=datetime.now() - timedelta(hours=2),
                symbol='ALKIMI',
                side=TradeSide.SELL,
                amount=500.0,
                price=0.028,
                fee=0.014,
                fee_currency='USDT',
                trade_id='test_2',
                exchange='test_exchange'
            )
        ]

        provider.trade_cache.save_trades(test_trades, 'test_exchange', 'TEST')

        # Get trades
        df = await provider.get_trades_df()

        assert len(df) == 2
        assert df['exchange'].iloc[0] == 'test_exchange'
        assert df['symbol'].iloc[0] == 'ALKIMI'
        assert df['side'].iloc[0] == 'buy'

    @pytest.mark.asyncio
    async def test_get_trade_summary(self, provider):
        """Test trade summary calculation."""
        # Add test trades
        test_trades = [
            Trade(
                timestamp=datetime.now() - timedelta(hours=1),
                symbol='ALKIMI',
                side=TradeSide.BUY,
                amount=1000.0,
                price=0.027,
                fee=0.027,
                fee_currency='USDT',
                trade_id='test_1',
                exchange='exchange1'
            ),
            Trade(
                timestamp=datetime.now() - timedelta(hours=2),
                symbol='ALKIMI',
                side=TradeSide.SELL,
                amount=500.0,
                price=0.028,
                fee=0.014,
                fee_currency='USDT',
                trade_id='test_2',
                exchange='exchange2'
            )
        ]

        provider.trade_cache.save_trades(test_trades[:1], 'exchange1', 'TEST')
        provider.trade_cache.save_trades(test_trades[1:], 'exchange2', 'TEST')

        # Get summary
        summary = await provider.get_trade_summary()

        assert summary['trade_count'] == 2
        assert summary['buy_count'] == 1
        assert summary['sell_count'] == 1
        assert summary['buy_volume'] == pytest.approx(1000 * 0.027)
        assert summary['sell_volume'] == pytest.approx(500 * 0.028)
        assert 'exchange1' in summary['by_exchange']
        assert 'exchange2' in summary['by_exchange']

    @pytest.mark.asyncio
    async def test_save_and_get_query_history(self, provider):
        """Test saving and retrieving query history."""
        # Save a query
        query_id = await provider.save_query_history(
            user_id='U12345',
            user_name='Test User',
            query_text='Show trades',
            query_type='trades',
            execution_time_ms=100,
            success=True
        )

        assert query_id > 0

        # Retrieve history
        history = await provider.get_query_history(user_id='U12345')

        assert len(history) == 1
        assert history[0]['user_id'] == 'U12345'
        assert history[0]['query_text'] == 'Show trades'
        assert history[0]['success'] == 1  # SQLite stores as int

    @pytest.mark.asyncio
    async def test_save_and_get_function(self, provider):
        """Test saving and retrieving functions."""
        # Save a function
        success = await provider.save_function(
            name='test_func',
            code='print("test")',
            description='Test function',
            created_by='U12345'
        )

        assert success is True

        # Try to save duplicate (should fail)
        success2 = await provider.save_function(
            name='test_func',
            code='print("duplicate")',
            created_by='U12345'
        )

        assert success2 is False

        # Retrieve function
        func = await provider.get_function('test_func')

        assert func is not None
        assert func['name'] == 'test_func'
        assert func['code'] == 'print("test")'
        assert func['use_count'] == 1  # Should increment on retrieval

        # Get again to test use_count increment
        func2 = await provider.get_function('test_func')
        assert func2['use_count'] == 2

    @pytest.mark.asyncio
    async def test_list_functions(self, provider):
        """Test listing all functions."""
        # Save multiple functions
        await provider.save_function('func1', 'code1', 'user1', 'Func 1')
        await provider.save_function('func2', 'code2', 'user1', 'Func 2')

        # List functions
        functions = await provider.list_functions()

        assert len(functions) == 2
        assert functions[0]['name'] in ['func1', 'func2']

    @pytest.mark.asyncio
    async def test_save_otc_transaction(self, provider):
        """Test saving OTC transactions."""
        otc_id = await provider.save_otc_transaction(
            date_str='2025-11-30',
            alkimi_amount=100000.0,
            usd_amount=2700.0,
            price=0.027,
            side='buy',
            counterparty='Test Buyer',
            notes='Test transaction',
            created_by='U12345'
        )

        assert otc_id > 0

    @pytest.mark.asyncio
    async def test_get_otc_transactions(self, provider):
        """Test retrieving OTC transactions."""
        # Save transactions
        await provider.save_otc_transaction(
            date_str='2025-11-30',
            alkimi_amount=100000.0,
            usd_amount=2700.0,
            price=0.027,
            side='buy'
        )
        await provider.save_otc_transaction(
            date_str='2025-11-29',
            alkimi_amount=50000.0,
            usd_amount=1350.0,
            price=0.027,
            side='sell'
        )

        # Get all
        df = await provider.get_otc_transactions()
        assert len(df) == 2

        # Get filtered
        df_filtered = await provider.get_otc_transactions(since='2025-11-30')
        assert len(df_filtered) == 1

    @pytest.mark.asyncio
    async def test_get_balances_empty(self, provider):
        """Test getting balances when no snapshots exist."""
        balances = await provider.get_balances()
        assert balances == {}

    @pytest.mark.asyncio
    async def test_get_snapshots(self, provider):
        """Test getting snapshots."""
        # Create a test snapshot
        from datetime import date
        import json

        snapshot_data = {
            'date': date.today().isoformat(),
            'timestamp': datetime.now().isoformat(),
            'balances': {'ALKIMI': 100000.0, 'USDT': 2700.0}
        }

        snapshot_path = provider.snapshots_dir / f"snapshot_{date.today().isoformat()}.json"
        with open(snapshot_path, 'w') as f:
            json.dump(snapshot_data, f)

        # Get snapshots
        snapshots = await provider.get_snapshots(days=7)

        assert len(snapshots) >= 1
        assert snapshots[-1]['balances']['ALKIMI'] == 100000.0

    @pytest.mark.asyncio
    async def test_context_manager(self):
        """Test using DataProvider as context manager."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / "test_cache.db"
        snapshots_dir = Path(temp_dir) / "snapshots"
        snapshots_dir.mkdir()

        async with DataProvider(str(db_path), str(snapshots_dir)) as provider:
            df = await provider.get_trades_df()
            assert isinstance(df, pd.DataFrame)

        # Cleanup
        shutil.rmtree(temp_dir)

    @pytest.mark.asyncio
    async def test_get_current_price(self, provider):
        """Test getting current price from CoinGecko."""
        # Note: This is a live API call, may fail in CI
        price = await provider.get_current_price()

        # Price could be None if API fails, that's ok
        if price is not None:
            assert isinstance(price, float)
            assert price > 0

    @pytest.mark.asyncio
    async def test_get_dex_trades_without_sui(self, provider):
        """Test getting DEX trades when Sui monitor is not configured."""
        df = await provider.get_dex_trades()

        # Should return empty DataFrame with correct schema
        assert isinstance(df, pd.DataFrame)
        assert df.empty
        expected_columns = [
            'timestamp', 'exchange', 'symbol', 'side',
            'amount', 'price', 'fee', 'fee_currency', 'trade_id'
        ]
        assert list(df.columns) == expected_columns


# Integration test (requires actual data)
@pytest.mark.integration
class TestDataProviderIntegration:
    """Integration tests that require actual data."""

    @pytest.mark.asyncio
    async def test_full_workflow(self):
        """Test complete workflow with real database."""
        provider = DataProvider(
            db_path="data/trade_cache.db",
            snapshots_dir="data/snapshots"
        )

        try:
            # This should work with the actual database
            df = await provider.get_trades_df()
            assert isinstance(df, pd.DataFrame)

            summary = await provider.get_trade_summary()
            assert isinstance(summary, dict)
            assert 'trade_count' in summary

        finally:
            await provider.close()


if __name__ == "__main__":
    # Run tests with: pytest tests/test_data_provider.py -v
    pytest.main([__file__, "-v"])
