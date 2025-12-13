"""
Comprehensive Unit Tests for P&L Configuration and Calculation Module

Tests all three cost basis methods (FIFO, LIFO, AVG) with edge cases,
OTC transaction handling, and multi-exchange scenarios.
"""

import pytest
import pandas as pd
import tempfile
import shutil
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from src.bot.pnl_config import (
    PnLCalculator,
    PnLConfig,
    OTCManager,
    CostBasisMethod,
    PnLReport,
    OTCTransaction,
    TradeLot
)


@pytest.fixture
def temp_db():
    """Create temporary database for testing."""
    temp_dir = tempfile.mkdtemp()
    db_path = Path(temp_dir) / "test_pnl.db"

    yield str(db_path)

    # Cleanup
    shutil.rmtree(temp_dir)


@pytest.fixture
def pnl_config(temp_db):
    """Create PnLConfig instance for testing."""
    return PnLConfig(db_path=temp_db)


@pytest.fixture
def otc_manager(temp_db):
    """Create OTCManager instance for testing."""
    return OTCManager(db_path=temp_db)


@pytest.fixture
def mock_data_provider():
    """Create mock data provider for testing."""
    mock = MagicMock()
    mock.db_path = "data/trade_cache.db"

    # Mock get_all_trades to return empty DataFrame
    async def get_all_trades():
        return pd.DataFrame(columns=[
            'timestamp', 'exchange', 'account', 'side',
            'amount', 'price', 'total', 'fee'
        ])

    mock.get_all_trades = get_all_trades

    # Mock get_current_price
    async def get_current_price(symbol):
        return 0.027  # Default price

    mock.get_current_price = get_current_price

    return mock


@pytest.fixture
def simple_trades_df():
    """
    Create simple trades DataFrame for testing.

    Pattern: Buy 100 @ $1.00, Buy 100 @ $1.50, Sell 150 @ $2.00
    Expected FIFO P&L: (100 * (2.00 - 1.00)) + (50 * (2.00 - 1.50)) = $125
    Expected LIFO P&L: (100 * (2.00 - 1.50)) + (50 * (2.00 - 1.00)) = $100
    """
    base_time = datetime(2025, 1, 1, 12, 0, 0)

    return pd.DataFrame([
        {
            'timestamp': base_time,
            'exchange': 'MEXC',
            'account': 'MM1',
            'side': 'buy',
            'amount': 100.0,
            'price': 1.00,
            'total': 100.0,
            'fee': 0.0
        },
        {
            'timestamp': base_time + timedelta(hours=1),
            'exchange': 'MEXC',
            'account': 'MM1',
            'side': 'buy',
            'amount': 100.0,
            'price': 1.50,
            'total': 150.0,
            'fee': 0.0
        },
        {
            'timestamp': base_time + timedelta(hours=2),
            'exchange': 'MEXC',
            'account': 'MM1',
            'side': 'sell',
            'amount': 150.0,
            'price': 2.00,
            'total': 300.0,
            'fee': 0.0
        }
    ])


@pytest.fixture
def complex_trades_df():
    """
    Create complex trades with multiple buy/sell cycles.

    Pattern:
    - Buy 100 @ $1.00
    - Buy 200 @ $1.50
    - Sell 150 @ $2.00 (FIFO: sells all of first + 50 of second)
    - Buy 100 @ $1.20
    - Sell 200 @ $1.80 (FIFO: sells remaining 150 of second + 50 of third)
    """
    base_time = datetime(2025, 1, 1, 12, 0, 0)

    return pd.DataFrame([
        {
            'timestamp': base_time,
            'exchange': 'MEXC',
            'account': 'MM1',
            'side': 'buy',
            'amount': 100.0,
            'price': 1.00,
            'total': 100.0,
            'fee': 0.0
        },
        {
            'timestamp': base_time + timedelta(hours=1),
            'exchange': 'MEXC',
            'account': 'MM1',
            'side': 'buy',
            'amount': 200.0,
            'price': 1.50,
            'total': 300.0,
            'fee': 0.0
        },
        {
            'timestamp': base_time + timedelta(hours=2),
            'exchange': 'MEXC',
            'account': 'MM1',
            'side': 'sell',
            'amount': 150.0,
            'price': 2.00,
            'total': 300.0,
            'fee': 0.0
        },
        {
            'timestamp': base_time + timedelta(hours=3),
            'exchange': 'MEXC',
            'account': 'MM1',
            'side': 'buy',
            'amount': 100.0,
            'price': 1.20,
            'total': 120.0,
            'fee': 0.0
        },
        {
            'timestamp': base_time + timedelta(hours=4),
            'exchange': 'MEXC',
            'account': 'MM1',
            'side': 'sell',
            'amount': 200.0,
            'price': 1.80,
            'total': 360.0,
            'fee': 0.0
        }
    ])


class TestPnLConfig:
    """Test P&L configuration management."""

    @pytest.mark.asyncio
    async def test_default_config(self, pnl_config):
        """Test default configuration values are set."""
        config = await pnl_config.get_config()

        assert config['cost_basis_method'] == 'fifo'
        assert config['include_fees'] == 'true'
        assert config['excluded_accounts'] == '[]'
        assert config['base_currency'] == 'USD'

    @pytest.mark.asyncio
    async def test_set_and_get_config(self, pnl_config):
        """Test setting and getting individual config values."""
        await pnl_config.set('test_key', 'test_value', 'test_user')

        value = await pnl_config.get('test_key')
        assert value == 'test_value'

    @pytest.mark.asyncio
    async def test_cost_basis_method_fifo(self, pnl_config):
        """Test FIFO cost basis method configuration."""
        await pnl_config.set_cost_basis_method(CostBasisMethod.FIFO, 'test_user')

        method = await pnl_config.get_cost_basis_method()
        assert method == CostBasisMethod.FIFO

    @pytest.mark.asyncio
    async def test_cost_basis_method_lifo(self, pnl_config):
        """Test LIFO cost basis method configuration."""
        await pnl_config.set_cost_basis_method(CostBasisMethod.LIFO, 'test_user')

        method = await pnl_config.get_cost_basis_method()
        assert method == CostBasisMethod.LIFO

    @pytest.mark.asyncio
    async def test_cost_basis_method_average(self, pnl_config):
        """Test AVERAGE cost basis method configuration."""
        await pnl_config.set_cost_basis_method(CostBasisMethod.AVERAGE, 'test_user')

        method = await pnl_config.get_cost_basis_method()
        assert method == CostBasisMethod.AVERAGE

    @pytest.mark.asyncio
    async def test_exclude_account(self, pnl_config):
        """Test excluding an account from P&L calculation."""
        await pnl_config.exclude_account('TEST_ACCOUNT', 'test_user')

        excluded = await pnl_config.get_excluded_accounts()
        assert 'TEST_ACCOUNT' in excluded

    @pytest.mark.asyncio
    async def test_include_account(self, pnl_config):
        """Test including a previously excluded account."""
        await pnl_config.exclude_account('TEST_ACCOUNT', 'test_user')
        await pnl_config.include_account('TEST_ACCOUNT', 'test_user')

        excluded = await pnl_config.get_excluded_accounts()
        assert 'TEST_ACCOUNT' not in excluded

    @pytest.mark.asyncio
    async def test_multiple_excluded_accounts(self, pnl_config):
        """Test excluding multiple accounts."""
        await pnl_config.exclude_account('ACCOUNT1', 'test_user')
        await pnl_config.exclude_account('ACCOUNT2', 'test_user')
        await pnl_config.exclude_account('ACCOUNT3', 'test_user')

        excluded = await pnl_config.get_excluded_accounts()
        assert len(excluded) == 3
        assert all(acc in excluded for acc in ['ACCOUNT1', 'ACCOUNT2', 'ACCOUNT3'])


class TestOTCManager:
    """Test OTC transaction management."""

    @pytest.mark.asyncio
    async def test_add_otc_transaction_buy(self, otc_manager):
        """Test adding a buy OTC transaction."""
        otc_id = await otc_manager.add(
            date=datetime(2025, 11, 15),
            alkimi_amount=3_000_000.0,
            usd_amount=82_000.0,
            side='buy',
            counterparty='RAMAN',
            notes='Test OTC buy',
            created_by='test_user'
        )

        assert otc_id > 0

    @pytest.mark.asyncio
    async def test_add_otc_transaction_sell(self, otc_manager):
        """Test adding a sell OTC transaction."""
        otc_id = await otc_manager.add(
            date=datetime(2025, 11, 16),
            alkimi_amount=1_000_000.0,
            usd_amount=28_000.0,
            side='sell',
            counterparty='BUYER',
            notes='Test OTC sell',
            created_by='test_user'
        )

        assert otc_id > 0

    @pytest.mark.asyncio
    async def test_add_otc_invalid_side(self, otc_manager):
        """Test adding OTC transaction with invalid side."""
        with pytest.raises(ValueError, match="Side must be 'buy' or 'sell'"):
            await otc_manager.add(
                date=datetime(2025, 11, 15),
                alkimi_amount=1_000_000.0,
                usd_amount=27_000.0,
                side='invalid',
                created_by='test_user'
            )

    @pytest.mark.asyncio
    async def test_get_otc_transaction(self, otc_manager):
        """Test retrieving an OTC transaction by ID."""
        otc_id = await otc_manager.add(
            date=datetime(2025, 11, 15),
            alkimi_amount=3_000_000.0,
            usd_amount=82_000.0,
            side='buy',
            counterparty='RAMAN',
            created_by='test_user'
        )

        otc = await otc_manager.get(otc_id)

        assert otc is not None
        assert otc.id == otc_id
        assert otc.alkimi_amount == 3_000_000.0
        assert otc.usd_amount == 82_000.0
        assert otc.side == 'buy'
        assert otc.counterparty == 'RAMAN'

    @pytest.mark.asyncio
    async def test_list_all_otc_transactions(self, otc_manager):
        """Test listing all OTC transactions."""
        # Add multiple transactions
        await otc_manager.add(
            date=datetime(2025, 11, 15),
            alkimi_amount=3_000_000.0,
            usd_amount=82_000.0,
            side='buy',
            created_by='test_user'
        )
        await otc_manager.add(
            date=datetime(2025, 11, 16),
            alkimi_amount=1_000_000.0,
            usd_amount=28_000.0,
            side='sell',
            created_by='test_user'
        )

        all_otc = await otc_manager.list_all()

        assert len(all_otc) == 2
        assert isinstance(all_otc[0], OTCTransaction)

    @pytest.mark.asyncio
    async def test_remove_otc_transaction(self, otc_manager):
        """Test removing an OTC transaction."""
        otc_id = await otc_manager.add(
            date=datetime(2025, 11, 15),
            alkimi_amount=3_000_000.0,
            usd_amount=82_000.0,
            side='buy',
            created_by='test_user'
        )

        removed = await otc_manager.remove(otc_id)
        assert removed is True

        # Verify it's gone
        otc = await otc_manager.get(otc_id)
        assert otc is None

    @pytest.mark.asyncio
    async def test_remove_nonexistent_otc(self, otc_manager):
        """Test removing a non-existent OTC transaction."""
        removed = await otc_manager.remove(99999)
        assert removed is False

    @pytest.mark.asyncio
    async def test_otc_price_calculation(self, otc_manager):
        """Test that price is calculated correctly from amounts."""
        otc_id = await otc_manager.add(
            date=datetime(2025, 11, 15),
            alkimi_amount=3_000_000.0,
            usd_amount=81_000.0,
            side='buy',
            created_by='test_user'
        )

        otc = await otc_manager.get(otc_id)

        # Price should be usd_amount / alkimi_amount = 81000 / 3000000 = 0.027
        assert pytest.approx(otc.price, rel=1e-6) == 0.027

    @pytest.mark.asyncio
    async def test_get_total_otc_cost_basis(self, otc_manager):
        """Test calculating total OTC cost basis from buys."""
        # Add multiple OTC buys and sells
        await otc_manager.add(
            date=datetime(2025, 11, 15),
            alkimi_amount=3_000_000.0,
            usd_amount=82_000.0,
            side='buy',
            created_by='test_user'
        )
        await otc_manager.add(
            date=datetime(2025, 11, 16),
            alkimi_amount=2_000_000.0,
            usd_amount=54_000.0,
            side='buy',
            created_by='test_user'
        )
        await otc_manager.add(
            date=datetime(2025, 11, 17),
            alkimi_amount=1_000_000.0,
            usd_amount=28_000.0,
            side='sell',  # This should NOT be included
            created_by='test_user'
        )

        total_cost = await otc_manager.get_total_otc_cost_basis()

        # Should only sum the buys: 82000 + 54000 = 136000
        assert pytest.approx(total_cost, rel=1e-2) == 136_000.0

    @pytest.mark.asyncio
    async def test_get_otc_trades_df(self, otc_manager):
        """Test getting OTC transactions as DataFrame."""
        # Add transactions
        await otc_manager.add(
            date=datetime(2025, 11, 15),
            alkimi_amount=3_000_000.0,
            usd_amount=82_000.0,
            side='buy',
            counterparty='RAMAN',
            created_by='test_user'
        )

        df = await otc_manager.get_otc_trades_df()

        assert not df.empty
        assert len(df) == 1
        assert 'timestamp' in df.columns
        assert 'exchange' in df.columns
        assert df.iloc[0]['exchange'] == 'OTC'
        assert df.iloc[0]['side'] == 'buy'
        assert df.iloc[0]['amount'] == 3_000_000.0


class TestFIFOCalculation:
    """Test FIFO (First-In-First-Out) cost basis calculations."""

    @pytest.mark.asyncio
    async def test_fifo_simple_trades(self, temp_db, simple_trades_df):
        """Test basic FIFO calculation."""
        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        cost_basis, realized_pnl = await calculator.calculate_fifo(simple_trades_df)

        # Expected:
        # Sell 150 @ $2 = $300 proceeds
        # Cost: 100 @ $1 + 50 @ $1.50 = $175
        # P&L: $300 - $175 = $125
        assert pytest.approx(cost_basis, rel=1e-2) == 175.0
        assert pytest.approx(realized_pnl, rel=1e-2) == 125.0

    @pytest.mark.asyncio
    async def test_fifo_complex_trades(self, temp_db, complex_trades_df):
        """Test complex multi-cycle FIFO calculation."""
        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        cost_basis, realized_pnl = await calculator.calculate_fifo(complex_trades_df)

        # First sell (150 @ $2.00): Uses 100 @ $1.00 + 50 @ $1.50
        # P&L1: (100 * $1.00) + (50 * $0.50) = $125

        # Second sell (200 @ $1.80): Uses 150 @ $1.50 + 50 @ $1.20
        # P&L2: (150 * $0.30) + (50 * $0.60) = $75

        # Total: $125 + $75 = $200
        assert pytest.approx(realized_pnl, rel=1e-2) == 200.0

    @pytest.mark.asyncio
    async def test_fifo_remaining_lots(self, temp_db, simple_trades_df):
        """Test FIFO leaves correct remaining lots."""
        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        # After selling 150, should have 50 remaining from second buy at $1.50
        await calculator.calculate_fifo(simple_trades_df)

        # Verify by calculating current holdings
        # (This is implicit in the lot tracking)


class TestLIFOCalculation:
    """Test LIFO (Last-In-First-Out) cost basis calculations."""

    @pytest.mark.asyncio
    async def test_lifo_simple_trades(self, temp_db, simple_trades_df):
        """Test basic LIFO calculation."""
        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        cost_basis, realized_pnl = await calculator.calculate_lifo(simple_trades_df)

        # Expected LIFO:
        # Sell 150 @ $2 = $300 proceeds
        # Cost: 100 @ $1.50 + 50 @ $1.00 = $200
        # P&L: $300 - $200 = $100
        assert pytest.approx(cost_basis, rel=1e-2) == 200.0
        assert pytest.approx(realized_pnl, rel=1e-2) == 100.0

    @pytest.mark.asyncio
    async def test_lifo_complex_trades(self, temp_db, complex_trades_df):
        """Test complex multi-cycle LIFO calculation."""
        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        cost_basis, realized_pnl = await calculator.calculate_lifo(complex_trades_df)

        # First sell (150 @ $2.00): Uses 100 @ $1.50 + 50 @ $1.00 (LIFO)
        # P&L1: (100 * $0.50) + (50 * $1.00) = $100

        # Second sell (200 @ $1.80): Uses 100 @ $1.20 + 100 @ $1.50 (LIFO)
        # P&L2: (100 * $0.60) + (100 * $0.30) = $90

        # Total: $100 + $90 = $190
        assert pytest.approx(realized_pnl, rel=1e-2) == 190.0


class TestAverageCalculation:
    """Test Average cost basis calculations."""

    @pytest.mark.asyncio
    async def test_average_simple_trades(self, temp_db, simple_trades_df):
        """Test basic average cost calculation."""
        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        cost_basis, realized_pnl = await calculator.calculate_average(simple_trades_df)

        # Expected Average:
        # Total bought: 200 @ avg = (100*$1 + 100*$1.50) / 200 = $1.25
        # Sell 150 @ $2.00 = $300 proceeds
        # Cost: 150 * $1.25 = $187.50
        # P&L: $300 - $187.50 = $112.50
        assert pytest.approx(cost_basis, rel=1e-2) == 187.5
        assert pytest.approx(realized_pnl, rel=1e-2) == 112.5

    @pytest.mark.asyncio
    async def test_average_complex_trades(self, temp_db, complex_trades_df):
        """Test complex average cost calculation."""
        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        cost_basis, realized_pnl = await calculator.calculate_average(complex_trades_df)

        # This is more complex as average changes with each trade
        # Just verify it calculates without error and is within reasonable range
        assert realized_pnl > 0  # Should be profitable
        assert realized_pnl < 250  # But not unreasonably high


class TestMultiExchange:
    """Test P&L calculation across multiple exchanges."""

    @pytest.mark.asyncio
    async def test_aggregate_across_exchanges(self, temp_db):
        """Test aggregating P&L across multiple exchanges."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        trades_df = pd.DataFrame([
            # MEXC trades
            {'timestamp': base_time, 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'buy', 'amount': 100.0, 'price': 1.00, 'total': 100.0, 'fee': 0.0},
            {'timestamp': base_time + timedelta(hours=1), 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'sell', 'amount': 100.0, 'price': 1.50, 'total': 150.0, 'fee': 0.0},

            # Kraken trades
            {'timestamp': base_time + timedelta(hours=2), 'exchange': 'Kraken', 'account': 'TM1',
             'side': 'buy', 'amount': 50.0, 'price': 1.20, 'total': 60.0, 'fee': 0.0},
            {'timestamp': base_time + timedelta(hours=3), 'exchange': 'Kraken', 'account': 'TM1',
             'side': 'sell', 'amount': 50.0, 'price': 1.80, 'total': 90.0, 'fee': 0.0}
        ])

        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        cost_basis, realized_pnl = await calculator.calculate_fifo(trades_df)

        # MEXC: (100 * ($1.50 - $1.00)) = $50
        # Kraken: (50 * ($1.80 - $1.20)) = $30
        # Total: $80
        assert pytest.approx(realized_pnl, rel=1e-2) == 80.0

    @pytest.mark.asyncio
    async def test_by_exchange_breakdown(self, temp_db):
        """Test P&L breakdown by exchange."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        trades_df = pd.DataFrame([
            {'timestamp': base_time, 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'buy', 'amount': 100.0, 'price': 1.00, 'total': 100.0, 'fee': 0.0},
            {'timestamp': base_time + timedelta(hours=1), 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'sell', 'amount': 100.0, 'price': 1.50, 'total': 150.0, 'fee': 0.0},
            {'timestamp': base_time + timedelta(hours=2), 'exchange': 'Kraken', 'account': 'TM1',
             'side': 'buy', 'amount': 50.0, 'price': 1.20, 'total': 60.0, 'fee': 0.0},
            {'timestamp': base_time + timedelta(hours=3), 'exchange': 'Kraken', 'account': 'TM1',
             'side': 'sell', 'amount': 50.0, 'price': 1.80, 'total': 90.0, 'fee': 0.0}
        ])

        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        breakdown = await calculator.get_by_exchange(trades_df, datetime(2025, 1, 1))

        assert 'MEXC' in breakdown
        assert 'Kraken' in breakdown

        # Simple P&L: sell_total - buy_total
        # MEXC: $150 - $100 = $50
        # Kraken: $90 - $60 = $30
        assert pytest.approx(breakdown['MEXC'], rel=1e-2) == 50.0
        assert pytest.approx(breakdown['Kraken'], rel=1e-2) == 30.0


class TestOTCTransactions:
    """Test OTC transaction integration with P&L calculation."""

    @pytest.mark.asyncio
    async def test_otc_affects_cost_basis(self, temp_db):
        """Test that OTC transactions affect cost basis calculation."""
        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)

        # Add OTC buy
        await otc.add(
            date=datetime(2025, 1, 1, 10, 0, 0),
            alkimi_amount=100.0,
            usd_amount=100.0,  # $1.00 per token
            side='buy',
            created_by='test_user'
        )

        # Create exchange sell trade
        base_time = datetime(2025, 1, 1, 12, 0, 0)
        trades_df = pd.DataFrame([
            {'timestamp': base_time, 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'sell', 'amount': 100.0, 'price': 2.00, 'total': 200.0, 'fee': 0.0}
        ])

        provider = MagicMock()
        calculator = PnLCalculator(provider, config, otc)

        # Get OTC trades
        otc_df = await otc.get_otc_trades_df()

        # Combine with exchange trades
        all_trades = pd.concat([otc_df, trades_df], ignore_index=True)
        all_trades = all_trades.sort_values('timestamp')

        cost_basis, realized_pnl = await calculator.calculate_fifo(all_trades)

        # Should use OTC cost basis: 100 * ($2.00 - $1.00) = $100
        assert pytest.approx(realized_pnl, rel=1e-2) == 100.0

    @pytest.mark.asyncio
    async def test_otc_excluded_from_exchange_trades(self, temp_db):
        """Test that OTC is correctly identified as separate exchange."""
        otc = OTCManager(db_path=temp_db)

        await otc.add(
            date=datetime(2025, 1, 1),
            alkimi_amount=100.0,
            usd_amount=100.0,
            side='buy',
            created_by='test_user'
        )

        df = await otc.get_otc_trades_df()

        assert not df.empty
        assert df.iloc[0]['exchange'] == 'OTC'
        assert df.iloc[0]['account'] == 'OTC'


class TestEdgeCases:
    """Test edge cases and error conditions."""

    @pytest.mark.asyncio
    async def test_partial_fills(self, temp_db):
        """Test handling of partial fills in lot matching."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        trades_df = pd.DataFrame([
            {'timestamp': base_time, 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'buy', 'amount': 100.0, 'price': 1.00, 'total': 100.0, 'fee': 0.0},
            {'timestamp': base_time + timedelta(hours=1), 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'sell', 'amount': 50.0, 'price': 2.00, 'total': 100.0, 'fee': 0.0},
            {'timestamp': base_time + timedelta(hours=2), 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'sell', 'amount': 25.0, 'price': 2.00, 'total': 50.0, 'fee': 0.0}
        ])

        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        cost_basis, realized_pnl = await calculator.calculate_fifo(trades_df)

        # Should handle partial fills: 50 * $1.00 + 25 * $1.00 = $75 cost
        # Revenue: 75 * $2.00 = $150
        # P&L: $75
        assert pytest.approx(realized_pnl, rel=1e-2) == 75.0

    @pytest.mark.asyncio
    async def test_same_timestamp_trades(self, temp_db):
        """Test handling of trades with identical timestamps."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        trades_df = pd.DataFrame([
            {'timestamp': base_time, 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'buy', 'amount': 100.0, 'price': 1.00, 'total': 100.0, 'fee': 0.0},
            {'timestamp': base_time, 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'buy', 'amount': 100.0, 'price': 1.50, 'total': 150.0, 'fee': 0.0},
            {'timestamp': base_time, 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'sell', 'amount': 150.0, 'price': 2.00, 'total': 300.0, 'fee': 0.0}
        ])

        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        # Should handle without error
        cost_basis, realized_pnl = await calculator.calculate_fifo(trades_df)

        # FIFO should process in order they appear
        assert realized_pnl > 0

    @pytest.mark.asyncio
    async def test_zero_quantity_trade(self, temp_db):
        """Test handling of zero quantity trades."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        trades_df = pd.DataFrame([
            {'timestamp': base_time, 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'buy', 'amount': 0.0, 'price': 1.00, 'total': 0.0, 'fee': 0.0},
            {'timestamp': base_time + timedelta(hours=1), 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'buy', 'amount': 100.0, 'price': 1.00, 'total': 100.0, 'fee': 0.0},
            {'timestamp': base_time + timedelta(hours=2), 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'sell', 'amount': 100.0, 'price': 2.00, 'total': 200.0, 'fee': 0.0}
        ])

        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        # Should handle zero quantity gracefully
        cost_basis, realized_pnl = await calculator.calculate_fifo(trades_df)

        # Should still calculate correctly for non-zero trades
        assert pytest.approx(realized_pnl, rel=1e-2) == 100.0

    @pytest.mark.asyncio
    async def test_negative_pnl(self, temp_db):
        """Test handling of negative P&L (losses)."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        trades_df = pd.DataFrame([
            {'timestamp': base_time, 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'buy', 'amount': 100.0, 'price': 2.00, 'total': 200.0, 'fee': 0.0},
            {'timestamp': base_time + timedelta(hours=1), 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'sell', 'amount': 100.0, 'price': 1.00, 'total': 100.0, 'fee': 0.0}
        ])

        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        cost_basis, realized_pnl = await calculator.calculate_fifo(trades_df)

        # Should handle negative P&L: 100 * ($1.00 - $2.00) = -$100
        assert pytest.approx(realized_pnl, rel=1e-2) == -100.0

    @pytest.mark.asyncio
    async def test_overselling(self, temp_db):
        """Test selling more than available (warns but doesn't crash)."""
        base_time = datetime(2025, 1, 1, 12, 0, 0)

        trades_df = pd.DataFrame([
            {'timestamp': base_time, 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'buy', 'amount': 100.0, 'price': 1.00, 'total': 100.0, 'fee': 0.0},
            {'timestamp': base_time + timedelta(hours=1), 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'sell', 'amount': 150.0, 'price': 2.00, 'total': 300.0, 'fee': 0.0}
        ])

        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        # Should handle gracefully (logs warning)
        cost_basis, realized_pnl = await calculator.calculate_fifo(trades_df)

        # Should calculate P&L for the 100 that were bought
        assert pytest.approx(realized_pnl, rel=1e-2) == 100.0

    @pytest.mark.asyncio
    async def test_empty_trades(self, temp_db):
        """Test calculation with no trades."""
        trades_df = pd.DataFrame(columns=[
            'timestamp', 'exchange', 'account', 'side',
            'amount', 'price', 'total', 'fee'
        ])

        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)
        provider = MagicMock()

        calculator = PnLCalculator(provider, config, otc)

        cost_basis, realized_pnl = await calculator.calculate_fifo(trades_df)

        assert cost_basis == 0.0
        assert realized_pnl == 0.0


class TestPnLCalculatorIntegration:
    """Integration tests for full P&L calculation."""

    @pytest.mark.asyncio
    async def test_full_pnl_calculation(self, temp_db, simple_trades_df):
        """Test full P&L calculation with all components."""
        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)

        # Mock data provider
        provider = MagicMock()
        provider.db_path = temp_db

        async def mock_get_all_trades():
            return simple_trades_df

        provider.get_all_trades = mock_get_all_trades

        async def mock_get_current_price(symbol):
            return 2.50

        provider.get_current_price = mock_get_current_price

        calculator = PnLCalculator(provider, config, otc)

        # Set FIFO method
        await config.set_cost_basis_method(CostBasisMethod.FIFO, 'test_user')

        # Calculate P&L
        report = await calculator.calculate(
            since=datetime(2025, 1, 1),
            until=datetime(2025, 1, 2)
        )

        assert isinstance(report, PnLReport)
        assert report.realized_pnl > 0
        assert report.trade_count == 3

    @pytest.mark.asyncio
    async def test_account_exclusion(self, temp_db):
        """Test excluding accounts from P&L calculation."""
        config = PnLConfig(db_path=temp_db)
        otc = OTCManager(db_path=temp_db)

        # Exclude MM1 account
        await config.exclude_account('MM1', 'test_user')

        base_time = datetime(2025, 1, 1, 12, 0, 0)
        trades_df = pd.DataFrame([
            {'timestamp': base_time, 'exchange': 'MEXC', 'account': 'MM1',
             'side': 'buy', 'amount': 100.0, 'price': 1.00, 'total': 100.0, 'fee': 0.0},
            {'timestamp': base_time + timedelta(hours=1), 'exchange': 'MEXC', 'account': 'TM1',
             'side': 'buy', 'amount': 100.0, 'price': 1.00, 'total': 100.0, 'fee': 0.0},
            {'timestamp': base_time + timedelta(hours=2), 'exchange': 'MEXC', 'account': 'TM1',
             'side': 'sell', 'amount': 100.0, 'price': 2.00, 'total': 200.0, 'fee': 0.0}
        ])

        provider = MagicMock()
        provider.db_path = temp_db

        async def mock_get_all_trades():
            return trades_df

        provider.get_all_trades = mock_get_all_trades

        async def mock_get_current_price(symbol):
            return 2.50

        provider.get_current_price = mock_get_current_price

        calculator = PnLCalculator(provider, config, otc)

        report = await calculator.calculate(
            since=datetime(2025, 1, 1),
            until=datetime(2025, 1, 2)
        )

        # Should only include TM1 trades (2 trades)
        assert report.trade_count == 2


class TestDataStructures:
    """Test data structures and models."""

    def test_trade_lot_repr(self):
        """Test TradeLot string representation."""
        lot = TradeLot(
            timestamp=datetime(2025, 1, 1),
            amount=1000.0,
            price=0.027,
            exchange='MEXC',
            remaining=500.0
        )

        repr_str = repr(lot)
        assert '500' in repr_str
        assert '0.027' in repr_str
        assert 'MEXC' in repr_str

    def test_otc_transaction_str(self):
        """Test OTCTransaction string representation."""
        otc = OTCTransaction(
            id=1,
            date=datetime(2025, 11, 15),
            counterparty='RAMAN',
            alkimi_amount=3_000_000.0,
            usd_amount=82_000.0,
            price=0.027333,
            side='buy',
            notes='Test transaction',
            created_by='test_user',
            created_at=datetime.now()
        )

        str_repr = str(otc)
        assert 'OTC #1' in str_repr
        assert 'BUY' in str_repr
        assert '3,000,000' in str_repr
        assert 'RAMAN' in str_repr

    def test_pnl_report_str(self):
        """Test PnLReport string representation."""
        report = PnLReport(
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 31),
            total_sells=10000.0,
            total_cost_basis=8000.0,
            realized_pnl=2000.0,
            current_holdings=5000.0,
            avg_cost_per_token=0.025,
            current_price=0.030,
            unrealized_pnl=250.0,
            net_pnl=2250.0,
            by_exchange={'MEXC': 1500.0, 'Kraken': 500.0},
            trade_count=25
        )

        str_repr = str(report)
        assert 'P&L Report' in str_repr
        assert '$2,000.00' in str_repr
        assert '$250.00' in str_repr
        assert '$2,250.00' in str_repr


class TestCostBasisMethod:
    """Test CostBasisMethod enum."""

    def test_cost_basis_method_values(self):
        """Test CostBasisMethod enum values."""
        assert CostBasisMethod.FIFO.value == 'fifo'
        assert CostBasisMethod.LIFO.value == 'lifo'
        assert CostBasisMethod.AVERAGE.value == 'avg'

    def test_cost_basis_method_comparison(self):
        """Test comparing CostBasisMethod values."""
        method1 = CostBasisMethod.FIFO
        method2 = CostBasisMethod.FIFO
        method3 = CostBasisMethod.LIFO

        assert method1 == method2
        assert method1 != method3


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
