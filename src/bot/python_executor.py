"""Sandboxed Python execution for ALKIMI Slack bot."""

from typing import Any, Dict, List, Tuple, Optional
from dataclasses import dataclass
import ast
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import math
import statistics
import asyncio
import sys
from io import StringIO
import logging

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of Python code execution."""
    success: bool
    result: Any = None
    output: str = ""
    execution_time_ms: int = 0
    error: Optional[str] = None


class CodeValidator:
    """Validate Python code for safety."""

    ALLOWED_MODULES = {
        'pandas', 'numpy', 'datetime', 'timedelta',
        'math', 'statistics', 'collections', 'itertools',
        'functools', 'decimal', 'json'
    }

    FORBIDDEN_PATTERNS = [
        'import os', 'import sys', 'import subprocess',
        'import socket', 'import requests', 'import urllib',
        'open(', 'file(', 'exec(', 'eval(', 'compile(',
        '__import__', 'globals(', 'locals(', 'vars(',
        'getattr(', 'setattr(', 'delattr(',
        'input(', 'raw_input(',
        'os.', 'sys.', 'subprocess.',
        'socket.', 'requests.', 'urllib.',
        '__builtins__', '__code__', '__globals__',
        'lambda', 'yield from'
    ]

    FORBIDDEN_NAMES = {
        '__builtins__', '__import__', 'exec', 'eval', 'compile',
        'open', 'file', 'input', 'raw_input',
        'globals', 'locals', 'vars', 'dir',
        'getattr', 'setattr', 'delattr', 'hasattr',
        'exit', 'quit', 'help', 'copyright', 'license', 'credits',
        'memoryview', 'bytes', 'bytearray'
    }

    FORBIDDEN_ATTRIBUTES = {
        '__class__', '__base__', '__subclasses__', '__mro__',
        '__dict__', '__code__', '__globals__', '__closure__',
        'func_globals', 'func_code', 'gi_code', 'gi_frame'
    }

    def validate(self, code: str) -> Tuple[bool, str]:
        """
        Validate Python code is safe to execute.
        Returns (is_valid, error_message).
        """
        if not code or not code.strip():
            return False, "Code cannot be empty"

        # Check for forbidden patterns (string matching)
        code_lower = code.lower()
        for pattern in self.FORBIDDEN_PATTERNS:
            if pattern.lower() in code_lower:
                return False, f"Forbidden pattern detected: {pattern}"

        # Parse and check AST
        return self._check_ast(code)

    def _check_ast(self, code: str) -> Tuple[bool, str]:
        """Use AST to check for dangerous constructs."""
        try:
            tree = ast.parse(code)
        except SyntaxError as e:
            return False, f"Syntax error: {str(e)}"

        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name not in self.ALLOWED_MODULES:
                        return False, f"Import not allowed: {alias.name}"

            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module not in self.ALLOWED_MODULES:
                    return False, f"Import not allowed: {node.module}"

            # Check function calls
            elif isinstance(node, ast.Call):
                # Check for forbidden function names
                if isinstance(node.func, ast.Name):
                    if node.func.id in self.FORBIDDEN_NAMES:
                        return False, f"Forbidden function: {node.func.id}"

            # Check name usage
            elif isinstance(node, ast.Name):
                if node.id in self.FORBIDDEN_NAMES:
                    return False, f"Forbidden name: {node.id}"

            # Check attribute access
            elif isinstance(node, ast.Attribute):
                if node.attr in self.FORBIDDEN_ATTRIBUTES:
                    return False, f"Forbidden attribute: {node.attr}"
                # Check for dunder access
                if node.attr.startswith('__') and node.attr.endswith('__'):
                    if node.attr not in ['__add__', '__sub__', '__mul__', '__div__']:
                        return False, f"Forbidden dunder attribute: {node.attr}"

            # Block lambda functions (can be used to bypass restrictions)
            elif isinstance(node, ast.Lambda):
                return False, "Lambda functions are not allowed"

            # Block async/await (harder to control)
            elif isinstance(node, (ast.AsyncFunctionDef, ast.Await)):
                return False, "Async functions are not allowed in user code"

            # Block generators with yield from (can be exploited)
            elif isinstance(node, ast.YieldFrom):
                return False, "yield from is not allowed"

        return True, ""

    def extract_function_name(self, code: str) -> Optional[str]:
        """Extract the function name from code."""
        try:
            tree = ast.parse(code)
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    return node.name
        except SyntaxError:
            pass
        return None


class SafePythonExecutor:
    """Execute Python code in a restricted sandbox."""

    def __init__(self, data_provider):
        """
        Initialize executor.

        Args:
            data_provider: DataProvider instance for loading trade data
        """
        self.data_provider = data_provider
        self.validator = CodeValidator()
        self.timeout = 30  # seconds
        self._cache = {}  # Cache for loaded data

    async def execute(self, code: str, use_cache: bool = True) -> ExecutionResult:
        """
        Execute Python code in sandbox.
        The code must assign its result to a variable called 'result'.

        Args:
            code: Python code to execute
            use_cache: Whether to use cached data (default True)

        Returns:
            ExecutionResult with success status, result, output, and timing
        """
        start_time = datetime.now()

        # 1. Validate code
        is_valid, error = self.validator.validate(code)
        if not is_valid:
            logger.warning(f"Code validation failed: {error}")
            return ExecutionResult(success=False, error=f"Validation error: {error}")

        # 2. Build restricted globals
        safe_globals = self._build_safe_globals(use_cache)

        # 3. Capture stdout
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        # 4. Execute with timeout
        try:
            local_vars = {}

            # Run in thread pool with timeout
            await asyncio.wait_for(
                asyncio.get_event_loop().run_in_executor(
                    None, self._execute_code, code, safe_globals, local_vars
                ),
                timeout=self.timeout
            )

            # Get result and output
            result = local_vars.get('result')
            output = captured_output.getvalue()
            exec_time = int((datetime.now() - start_time).total_seconds() * 1000)

            logger.info(f"Code executed successfully in {exec_time}ms")

            return ExecutionResult(
                success=True,
                result=result,
                output=output,
                execution_time_ms=exec_time
            )

        except asyncio.TimeoutError:
            error_msg = f"Execution timed out after {self.timeout}s"
            logger.error(error_msg)
            return ExecutionResult(success=False, error=error_msg)

        except MemoryError:
            error_msg = "Execution exceeded memory limits"
            logger.error(error_msg)
            return ExecutionResult(success=False, error=error_msg)

        except Exception as e:
            error_msg = f"{type(e).__name__}: {str(e)}"
            logger.error(f"Execution error: {error_msg}")
            return ExecutionResult(success=False, error=error_msg)

        finally:
            # Restore stdout
            sys.stdout = old_stdout

    def _build_safe_globals(self, use_cache: bool) -> Dict[str, Any]:
        """Build restricted globals for code execution."""
        return {
            # Data loading functions
            'load_trades': lambda **kwargs: self._sync_load_trades(use_cache, **kwargs),
            'load_balances': lambda: self._sync_load_balances(use_cache),
            'load_snapshots': lambda days=30: self._sync_load_snapshots(use_cache, days),

            # Safe modules
            'pd': pd,
            'np': np,
            'datetime': datetime,
            'timedelta': timedelta,
            'math': math,
            'statistics': statistics,

            # Minimal builtins
            'len': len,
            'range': range,
            'enumerate': enumerate,
            'zip': zip,
            'map': map,
            'filter': filter,
            'sorted': sorted,
            'reversed': reversed,
            'min': min,
            'max': max,
            'sum': sum,
            'abs': abs,
            'round': round,
            'int': int,
            'float': float,
            'str': str,
            'bool': bool,
            'list': list,
            'dict': dict,
            'set': set,
            'tuple': tuple,
            'print': print,
            'isinstance': isinstance,
            'issubclass': issubclass,
            'type': type,
            'all': all,
            'any': any,

            # Constants
            'True': True,
            'False': False,
            'None': None,

            # Prevent access to dangerous builtins
            '__builtins__': {
                'len': len,
                'range': range,
                'True': True,
                'False': False,
                'None': None,
            }
        }

    def _sync_load_trades(self, use_cache: bool, **kwargs) -> pd.DataFrame:
        """
        Synchronous wrapper for async data loading.

        Args:
            use_cache: Whether to use cached data
            **kwargs: Arguments for load_trades (days, exchange, asset)
        """
        cache_key = f"trades_{json.dumps(kwargs, sort_keys=True)}"

        if use_cache and cache_key in self._cache:
            logger.debug(f"Using cached trades: {cache_key}")
            return self._cache[cache_key]

        # Run async function in event loop
        loop = asyncio.new_event_loop()
        try:
            df = loop.run_until_complete(self.data_provider.load_trades(**kwargs))
            if use_cache:
                self._cache[cache_key] = df
            return df
        finally:
            loop.close()

    def _sync_load_balances(self, use_cache: bool) -> Dict:
        """
        Synchronous wrapper for balance loading.

        Args:
            use_cache: Whether to use cached data
        """
        cache_key = "balances"

        if use_cache and cache_key in self._cache:
            logger.debug("Using cached balances")
            return self._cache[cache_key]

        loop = asyncio.new_event_loop()
        try:
            balances = loop.run_until_complete(self.data_provider.get_all_balances())
            if use_cache:
                self._cache[cache_key] = balances
            return balances
        finally:
            loop.close()

    def _sync_load_snapshots(self, use_cache: bool, days: int = 30) -> List[Dict]:
        """
        Synchronous wrapper for snapshot loading.

        Args:
            use_cache: Whether to use cached data
            days: Number of days of snapshots to load
        """
        cache_key = f"snapshots_{days}"

        if use_cache and cache_key in self._cache:
            logger.debug(f"Using cached snapshots: {days} days")
            return self._cache[cache_key]

        loop = asyncio.new_event_loop()
        try:
            snapshots = loop.run_until_complete(
                self.data_provider.get_balance_snapshots(days)
            )
            if use_cache:
                self._cache[cache_key] = snapshots
            return snapshots
        finally:
            loop.close()

    def _execute_code(self, code: str, globals_dict: Dict, locals_dict: Dict):
        """
        Execute code in restricted environment.

        Args:
            code: Python code to execute
            globals_dict: Global namespace
            locals_dict: Local namespace (will contain 'result' after execution)
        """
        exec(code, globals_dict, locals_dict)

    def clear_cache(self):
        """Clear the data cache."""
        self._cache.clear()
        logger.info("Execution cache cleared")


# Import json for cache key generation
import json
