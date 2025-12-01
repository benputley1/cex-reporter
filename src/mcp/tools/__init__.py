"""
MCP Tools Package

All tools return MCPResponse with consistent format:
- success: bool
- data: Any (tool-specific response data)
- error: Optional[str] (error message if success=False)
- metadata: Dict (timestamps, counts, etc.)

Tools available:
- Trading: get_trades, get_trade_summary
- Snapshots: get_balances, get_snapshots, take_snapshot
- Market: get_current_price, get_market_data
- DEX: get_dex_trades, get_alkimi_pools, get_onchain_analytics
- Blockchain: get_treasury_value, get_top_holders, get_wallet_activity
- Storage: execute_sql, list_saved_functions, run_saved_function, get_query_history
- P&L: get_pnl_report, get_pnl_config, set_cost_basis_method
- OTC: get_otc_transactions, add_otc_transaction
"""

# Import all tool modules (this registers them with the MCP server)
from src.mcp.tools import trading
from src.mcp.tools import snapshots
from src.mcp.tools import market
from src.mcp.tools import dex
from src.mcp.tools import blockchain
from src.mcp.tools import storage
from src.mcp.tools import pnl
from src.mcp.tools import otc

__all__ = [
    "trading",
    "snapshots",
    "market",
    "dex",
    "blockchain",
    "storage",
    "pnl",
    "otc",
]
