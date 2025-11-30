"""Tests for Python executor and function store."""

import pytest
import pandas as pd
from datetime import datetime, timedelta
from src.bot.python_executor import (
    CodeValidator,
    SafePythonExecutor,
    ExecutionResult
)
from src.bot.function_store import FunctionStore, SavedFunction


class MockDataProvider:
    """Mock data provider for testing."""

    async def load_trades(self, **kwargs):
        """Return mock trade data."""
        return pd.DataFrame({
            'timestamp': [datetime.now() - timedelta(days=i) for i in range(10)],
            'exchange': ['binance'] * 5 + ['kraken'] * 5,
            'asset': ['BTC'] * 10,
            'amount': [1.0, 2.0, 3.0, 4.0, 5.0] * 2,
            'price': [50000.0] * 10,
            'side': ['buy'] * 10
        })

    async def get_all_balances(self):
        """Return mock balances."""
        return {
            'binance': {'BTC': 10.0, 'ETH': 100.0},
            'kraken': {'BTC': 5.0, 'ETH': 50.0}
        }

    async def get_balance_snapshots(self, days):
        """Return mock snapshots."""
        return [
            {
                'timestamp': datetime.now() - timedelta(days=i),
                'total_usd': 1000000 - i * 1000
            }
            for i in range(days)
        ]


class TestCodeValidator:
    """Test code validation."""

    def test_valid_simple_code(self):
        """Test validation of simple valid code."""
        validator = CodeValidator()
        code = "result = 1 + 1"
        is_valid, error = validator.validate(code)
        assert is_valid
        assert error == ""

    def test_valid_pandas_code(self):
        """Test validation of pandas code."""
        validator = CodeValidator()
        code = """
import pandas as pd
df = pd.DataFrame({'a': [1, 2, 3]})
result = df.sum()
"""
        is_valid, error = validator.validate(code)
        assert is_valid

    def test_forbidden_import_os(self):
        """Test blocking of os import."""
        validator = CodeValidator()
        code = "import os"
        is_valid, error = validator.validate(code)
        assert not is_valid
        assert "import os" in error.lower()

    def test_forbidden_import_sys(self):
        """Test blocking of sys import."""
        validator = CodeValidator()
        code = "import sys"
        is_valid, error = validator.validate(code)
        assert not is_valid

    def test_forbidden_open(self):
        """Test blocking of file open."""
        validator = CodeValidator()
        code = "f = open('/etc/passwd', 'r')"
        is_valid, error = validator.validate(code)
        assert not is_valid
        assert "open(" in error.lower()

    def test_forbidden_exec(self):
        """Test blocking of exec."""
        validator = CodeValidator()
        code = "exec('malicious code')"
        is_valid, error = validator.validate(code)
        assert not is_valid

    def test_forbidden_eval(self):
        """Test blocking of eval."""
        validator = CodeValidator()
        code = "result = eval('1+1')"
        is_valid, error = validator.validate(code)
        assert not is_valid

    def test_forbidden_lambda(self):
        """Test blocking of lambda functions."""
        validator = CodeValidator()
        code = "f = lambda x: x + 1"
        is_valid, error = validator.validate(code)
        assert not is_valid
        assert "lambda" in error.lower()

    def test_forbidden_dunder_access(self):
        """Test blocking of dangerous dunder attributes."""
        validator = CodeValidator()
        code = "x = object.__class__"
        is_valid, error = validator.validate(code)
        assert not is_valid
        assert "__class__" in error

    def test_allowed_math_operations(self):
        """Test allowed math operations."""
        validator = CodeValidator()
        code = """
import math
result = math.sqrt(16) + math.pi
"""
        is_valid, error = validator.validate(code)
        assert is_valid

    def test_extract_function_name(self):
        """Test function name extraction."""
        validator = CodeValidator()
        code = """
def calculate_total(df):
    return df['amount'].sum()
"""
        name = validator.extract_function_name(code)
        assert name == "calculate_total"

    def test_extract_function_name_no_function(self):
        """Test extraction when no function defined."""
        validator = CodeValidator()
        code = "result = 1 + 1"
        name = validator.extract_function_name(code)
        assert name is None

    def test_empty_code(self):
        """Test validation of empty code."""
        validator = CodeValidator()
        is_valid, error = validator.validate("")
        assert not is_valid
        assert "empty" in error.lower()

    def test_syntax_error(self):
        """Test handling of syntax errors."""
        validator = CodeValidator()
        code = "def broken(:\n    pass"
        is_valid, error = validator.validate(code)
        assert not is_valid
        assert "syntax" in error.lower()


@pytest.mark.asyncio
class TestSafePythonExecutor:
    """Test Python code execution."""

    async def test_simple_execution(self):
        """Test simple code execution."""
        provider = MockDataProvider()
        executor = SafePythonExecutor(provider)

        code = "result = 1 + 1"
        result = await executor.execute(code)

        assert result.success
        assert result.result == 2
        assert result.execution_time_ms > 0

    async def test_pandas_execution(self):
        """Test pandas code execution."""
        provider = MockDataProvider()
        executor = SafePythonExecutor(provider)

        code = """
import pandas as pd
df = pd.DataFrame({'a': [1, 2, 3]})
result = df['a'].sum()
"""
        result = await executor.execute(code)

        assert result.success
        assert result.result == 6

    async def test_load_trades(self):
        """Test loading trade data."""
        provider = MockDataProvider()
        executor = SafePythonExecutor(provider)

        code = """
df = load_trades()
result = len(df)
"""
        result = await executor.execute(code)

        assert result.success
        assert result.result == 10

    async def test_load_balances(self):
        """Test loading balance data."""
        provider = MockDataProvider()
        executor = SafePythonExecutor(provider)

        code = """
balances = load_balances()
result = balances['binance']['BTC']
"""
        result = await executor.execute(code)

        assert result.success
        assert result.result == 10.0

    async def test_complex_analysis(self):
        """Test complex data analysis."""
        provider = MockDataProvider()
        executor = SafePythonExecutor(provider)

        code = """
df = load_trades()
result = df.groupby('exchange')['amount'].sum().to_dict()
"""
        result = await executor.execute(code)

        assert result.success
        assert isinstance(result.result, dict)
        assert 'binance' in result.result
        assert 'kraken' in result.result

    async def test_print_output(self):
        """Test capturing print output."""
        provider = MockDataProvider()
        executor = SafePythonExecutor(provider)

        code = """
print("Hello, World!")
result = 42
"""
        result = await executor.execute(code)

        assert result.success
        assert result.result == 42
        assert "Hello, World!" in result.output

    async def test_execution_error(self):
        """Test handling of execution errors."""
        provider = MockDataProvider()
        executor = SafePythonExecutor(provider)

        code = "result = 1 / 0"
        result = await executor.execute(code)

        assert not result.success
        assert "ZeroDivisionError" in result.error

    async def test_validation_error(self):
        """Test handling of validation errors."""
        provider = MockDataProvider()
        executor = SafePythonExecutor(provider)

        code = "import os"
        result = await executor.execute(code)

        assert not result.success
        assert "Validation error" in result.error

    async def test_cache_usage(self):
        """Test data caching."""
        provider = MockDataProvider()
        executor = SafePythonExecutor(provider)

        code = "result = len(load_trades())"

        # First execution - should cache
        result1 = await executor.execute(code, use_cache=True)
        time1 = result1.execution_time_ms

        # Second execution - should use cache (faster)
        result2 = await executor.execute(code, use_cache=True)
        time2 = result2.execution_time_ms

        assert result1.success
        assert result2.success
        assert result1.result == result2.result

        # Clear cache and verify
        executor.clear_cache()


@pytest.mark.asyncio
class TestFunctionStore:
    """Test function storage."""

    async def test_save_and_get(self):
        """Test saving and retrieving a function."""
        store = FunctionStore(db_path=":memory:")

        success = await store.save(
            name="test_func",
            code="result = 1 + 1",
            description="Test function",
            created_by="U123"
        )
        assert success

        func = await store.get("test_func")
        assert func is not None
        assert func.name == "test_func"
        assert func.code == "result = 1 + 1"
        assert func.description == "Test function"
        assert func.created_by == "U123"
        assert func.use_count == 0

    async def test_update_existing(self):
        """Test updating an existing function."""
        store = FunctionStore(db_path=":memory:")

        # Save original
        await store.save(
            name="test_func",
            code="result = 1",
            description="Original",
            created_by="U123"
        )

        # Update
        await store.save(
            name="test_func",
            code="result = 2",
            description="Updated",
            created_by="U123"
        )

        func = await store.get("test_func")
        assert func.code == "result = 2"
        assert func.description == "Updated"

    async def test_list_all(self):
        """Test listing all functions."""
        store = FunctionStore(db_path=":memory:")

        await store.save("func1", "code1", "desc1", "U123")
        await store.save("func2", "code2", "desc2", "U456")

        functions = await store.list_all()
        assert len(functions) == 2

    async def test_delete(self):
        """Test deleting a function."""
        store = FunctionStore(db_path=":memory:")

        await store.save("test_func", "code", "desc", "U123")
        assert await store.get("test_func") is not None

        success = await store.delete("test_func")
        assert success
        assert await store.get("test_func") is None

    async def test_delete_nonexistent(self):
        """Test deleting non-existent function."""
        store = FunctionStore(db_path=":memory:")

        success = await store.delete("nonexistent")
        assert not success

    async def test_update_usage(self):
        """Test updating usage statistics."""
        store = FunctionStore(db_path=":memory:")

        await store.save("test_func", "code", "desc", "U123")

        func = await store.get("test_func")
        assert func.use_count == 0
        assert func.last_used is None

        await store.update_usage("test_func")

        func = await store.get("test_func")
        assert func.use_count == 1
        assert func.last_used is not None

    async def test_search(self):
        """Test searching functions."""
        store = FunctionStore(db_path=":memory:")

        await store.save("volume_calc", "code1", "Calculate volume", "U123")
        await store.save("price_avg", "code2", "Calculate average price", "U123")
        await store.save("balance_check", "code3", "Check balances", "U123")

        results = await store.search("calc")
        assert len(results) == 2

        results = await store.search("volume")
        assert len(results) == 1
        assert results[0].name == "volume_calc"

    async def test_get_stats(self):
        """Test getting statistics."""
        store = FunctionStore(db_path=":memory:")

        await store.save("func1", "code1", "desc1", "U123")
        await store.save("func2", "code2", "desc2", "U123")

        await store.update_usage("func1")
        await store.update_usage("func1")
        await store.update_usage("func2")

        stats = await store.get_stats()
        assert stats['total_functions'] == 2
        assert stats['total_uses'] == 3
        assert len(stats['top_functions']) == 2
        assert stats['top_functions'][0]['name'] == "func1"
        assert stats['top_functions'][0]['use_count'] == 2

    async def test_rename(self):
        """Test renaming a function."""
        store = FunctionStore(db_path=":memory:")

        await store.save("old_name", "code", "desc", "U123")

        success = await store.rename("old_name", "new_name")
        assert success

        assert await store.get("old_name") is None
        assert await store.get("new_name") is not None

    async def test_rename_to_existing(self):
        """Test renaming to an existing name."""
        store = FunctionStore(db_path=":memory:")

        await store.save("func1", "code1", "desc1", "U123")
        await store.save("func2", "code2", "desc2", "U123")

        success = await store.rename("func1", "func2")
        assert not success

    async def test_export_import(self):
        """Test exporting and importing functions."""
        store = FunctionStore(db_path=":memory:")

        await store.save("test_func", "code", "desc", "U123")

        exported = await store.export_all()
        assert len(exported) == 1
        assert exported[0]['name'] == "test_func"

        # Import into new store
        store2 = FunctionStore(db_path=":memory:")
        success = await store2.import_function(exported[0])
        assert success

        func = await store2.get("test_func")
        assert func is not None

    async def test_invalid_function_name(self):
        """Test validation of function names."""
        store = FunctionStore(db_path=":memory:")

        # Invalid characters
        success = await store.save("func-name", "code", "desc", "U123")
        assert not success

        success = await store.save("func.name", "code", "desc", "U123")
        assert not success

        # Valid name
        success = await store.save("func_name_123", "code", "desc", "U123")
        assert success
