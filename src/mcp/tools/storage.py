"""Storage and SQL tools for MCP server."""

from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.mcp.schemas import MCPResponse
from src.mcp.server import mcp, get_data_provider
from src.bot.query_engine import QueryEngine
from src.bot.function_store import FunctionStore
from src.bot.python_executor import SafePythonExecutor


# Shared instances
_query_engine = None
_function_store = None
_executor = None


def get_query_engine():
    """Get or initialize the query engine."""
    global _query_engine
    if _query_engine is None:
        _query_engine = QueryEngine()
    return _query_engine


async def get_function_store():
    """Get or initialize the function store."""
    global _function_store
    if _function_store is None:
        _function_store = FunctionStore()
    return _function_store


def get_executor():
    """Get or initialize the Python executor."""
    global _executor
    if _executor is None:
        _executor = SafePythonExecutor(get_data_provider())
    return _executor


@mcp.tool()
async def execute_sql(sql: str) -> MCPResponse:
    """Run a read-only SQL query against the trades database.

    Only SELECT queries are allowed. Use for custom data analysis.
    Tables: trades, otc_transactions, query_history

    Args:
        sql: SQL SELECT query to execute
    """
    try:
        qe = get_query_engine()
        result = await qe.execute_sql(sql)

        if result.error:
            return MCPResponse(
                success=False,
                error=f"SQL Error: {result.error}",
                metadata={"query": sql[:100]}
            )

        if result.data is None or result.data.empty:
            return MCPResponse(
                success=True,
                data={"rows": [], "columns": []},
                metadata={"message": "Query returned no results.", "query": sql[:100]}
            )

        records = result.data.to_dict('records')
        return MCPResponse(
            success=True,
            data={
                "row_count": len(records),
                "columns": list(result.data.columns),
                "rows": records[:50]  # Limit to 50 rows
            },
            metadata={"query": sql[:100]}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "execute_sql"})


@mcp.tool()
async def list_saved_functions() -> MCPResponse:
    """List all saved Python analysis functions that users have created."""
    try:
        fs = await get_function_store()
        functions = await fs.list_all()

        if not functions:
            return MCPResponse(
                success=True,
                data=[],
                metadata={"message": "No saved functions found."}
            )

        func_list = []
        for f in functions:
            func_list.append({
                "name": f.name,
                "description": f.description,
                "created_by": f.created_by,
                "use_count": f.use_count
            })

        return MCPResponse(
            success=True,
            data=func_list,
            metadata={"count": len(func_list)}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "list_saved_functions"})


@mcp.tool()
async def run_saved_function(name: str) -> MCPResponse:
    """Execute a previously saved Python analysis function by name.

    Args:
        name: Name of the saved function to run
    """
    try:
        fs = await get_function_store()
        func = await fs.get(name)

        if not func:
            return MCPResponse(
                success=False,
                error=f"Function '{name}' not found.",
                metadata={"tool": "run_saved_function"}
            )

        executor = get_executor()
        result = await executor.execute(func.code)
        await fs.increment_usage(name)

        if result.error:
            return MCPResponse(
                success=False,
                error=f"Execution error: {result.error}",
                metadata={"function": name}
            )

        return MCPResponse(
            success=True,
            data={
                "function": name,
                "result": result.result,
                "output": result.output
            },
            metadata={"function": name}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "run_saved_function"})


@mcp.tool()
async def get_query_history(user_id: Optional[str] = None, limit: int = 10) -> MCPResponse:
    """Get history of recent queries made to the bot.

    Args:
        user_id: Filter by specific user (optional)
        limit: Number of queries to return (default 10, max 50)
    """
    try:
        dp = get_data_provider()
        limit = min(limit, 50)

        history = await dp.get_query_history(user_id=user_id, limit=limit)

        if not history:
            return MCPResponse(
                success=True,
                data=[],
                metadata={"message": "No query history found."}
            )

        return MCPResponse(
            success=True,
            data=history,
            metadata={"count": len(history)}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_query_history"})
