"""
ALKIMI MCP Server

Model Context Protocol server for ALKIMI trading bot.
Provides standardized access to trading data, analytics, and blockchain info.

All tools return MCPResponse with consistent format:
- success: bool
- data: Any (tool-specific response data)
- error: Optional[str] (error message if success=False)
- metadata: Dict (timestamps, counts, etc.)
"""

from mcp.server.fastmcp import FastMCP
from typing import Optional
import sys
import os

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.mcp.schemas import MCPResponse

# Initialize FastMCP server
mcp = FastMCP("alkimi-trading")

# Global data provider (initialized on startup)
data_provider = None


def get_data_provider():
    """Get or initialize the data provider."""
    global data_provider
    if data_provider is None:
        from src.bot.data_provider import DataProvider
        from config.settings import settings
        data_provider = DataProvider(
            db_path=settings.trade_cache_db,
            sui_config=settings.sui_config
        )
    return data_provider


@mcp.tool()
async def health_check() -> MCPResponse:
    """Check if the MCP server is running and healthy."""
    return MCPResponse(
        success=True,
        data={"status": "healthy", "server": "alkimi-mcp"},
        metadata={"version": "1.0.0"}
    )


# =============================================================================
# Tool Registration
# =============================================================================
# Import tool modules to register all @mcp.tool() decorated functions.
# Each module imports 'mcp' from this file and uses @mcp.tool() decorator.

def register_all_tools():
    """Import all tool modules to register their tools with the MCP server."""
    # Trading tools: get_trades, get_trade_summary
    from src.mcp.tools import trading  # noqa: F401

    # Snapshot tools: get_balances, get_snapshots, take_snapshot
    from src.mcp.tools import snapshots  # noqa: F401

    # Market tools: get_current_price, get_market_data
    from src.mcp.tools import market  # noqa: F401

    # DEX tools: get_dex_trades, get_alkimi_pools, get_onchain_analytics
    from src.mcp.tools import dex  # noqa: F401

    # Blockchain tools: get_treasury_value, get_top_holders, get_wallet_activity
    from src.mcp.tools import blockchain  # noqa: F401

    # Storage tools: execute_sql, list_saved_functions, run_saved_function, get_query_history
    from src.mcp.tools import storage  # noqa: F401

    # P&L tools: get_pnl_report, get_pnl_config, set_cost_basis_method
    from src.mcp.tools import pnl  # noqa: F401

    # OTC tools: get_otc_transactions, add_otc_transaction
    from src.mcp.tools import otc  # noqa: F401


# =============================================================================
# Direct Tool Access (for internal use by ConversationalAgent)
# =============================================================================
# These functions allow calling MCP tools directly without MCP protocol.
# Returns MCPResponse for consistent error handling.

async def call_tool(tool_name: str, **kwargs) -> MCPResponse:
    """
    Call an MCP tool by name with keyword arguments.

    This provides a unified interface for the ConversationalAgent to call
    any MCP tool without a large if/elif block.

    Args:
        tool_name: Name of the tool to call
        **kwargs: Tool-specific arguments

    Returns:
        MCPResponse with success/data/error/metadata
    """
    # Ensure tools are registered
    register_all_tools()

    # Tool function mapping (built dynamically from registered tools)
    from src.mcp.tools.trading import get_trades, get_trade_summary
    from src.mcp.tools.snapshots import get_balances, get_snapshots, take_snapshot
    from src.mcp.tools.market import get_current_price, get_market_data
    from src.mcp.tools.dex import get_dex_trades, get_alkimi_pools, get_onchain_analytics
    from src.mcp.tools.blockchain import get_treasury_value, get_top_holders, get_wallet_activity
    from src.mcp.tools.storage import execute_sql, list_saved_functions, run_saved_function, get_query_history
    from src.mcp.tools.pnl import get_pnl_report, get_pnl_config, set_cost_basis_method
    from src.mcp.tools.otc import get_otc_transactions, add_otc_transaction

    tool_map = {
        "health_check": health_check,
        "get_trades": get_trades,
        "get_trade_summary": get_trade_summary,
        "get_balances": get_balances,
        "get_snapshots": get_snapshots,
        "take_snapshot": take_snapshot,
        "get_current_price": get_current_price,
        "get_market_data": get_market_data,
        "get_dex_trades": get_dex_trades,
        "get_alkimi_pools": get_alkimi_pools,
        "get_onchain_analytics": get_onchain_analytics,
        "get_treasury_value": get_treasury_value,
        "get_top_holders": get_top_holders,
        "get_wallet_activity": get_wallet_activity,
        "execute_sql": execute_sql,
        "list_saved_functions": list_saved_functions,
        "run_saved_function": run_saved_function,
        "get_query_history": get_query_history,
        "get_pnl_report": get_pnl_report,
        "get_pnl_config": get_pnl_config,
        "set_cost_basis_method": set_cost_basis_method,
        "get_otc_transactions": get_otc_transactions,
        "add_otc_transaction": add_otc_transaction,
    }

    if tool_name not in tool_map:
        return MCPResponse(
            success=False,
            error=f"Unknown tool: {tool_name}",
            metadata={"available_tools": list(tool_map.keys())}
        )

    try:
        tool_func = tool_map[tool_name]
        result = await tool_func(**kwargs)
        return result
    except TypeError as e:
        # Handle missing/invalid arguments
        return MCPResponse(
            success=False,
            error=f"Invalid arguments for {tool_name}: {str(e)}",
            metadata={"tool": tool_name}
        )
    except Exception as e:
        return MCPResponse(
            success=False,
            error=f"Error executing {tool_name}: {str(e)}",
            metadata={"tool": tool_name}
        )


def run_server():
    """Run the MCP server with all tools registered."""
    register_all_tools()
    mcp.run(transport="stdio")


if __name__ == "__main__":
    run_server()
