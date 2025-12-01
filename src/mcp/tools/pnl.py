"""P&L (Profit & Loss) tools for MCP server."""

from datetime import datetime, timedelta
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.mcp.schemas import MCPResponse
from src.mcp.server import mcp, get_data_provider
from src.bot.pnl_config import PnLConfig, OTCManager, PnLCalculator, CostBasisMethod


# Shared instances
_pnl_config = None
_otc_manager = None
_pnl_calculator = None


def get_pnl_components():
    """Get or initialize P&L components."""
    global _pnl_config, _otc_manager, _pnl_calculator

    if _pnl_config is None:
        _pnl_config = PnLConfig()
        _otc_manager = OTCManager()
        _pnl_calculator = PnLCalculator(
            data_provider=get_data_provider(),
            pnl_config=_pnl_config,
            otc_manager=_otc_manager
        )

    return _pnl_config, _otc_manager, _pnl_calculator


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse flexible date strings."""
    if not date_str:
        return None
    date_str = date_str.lower().strip()
    now = datetime.now()
    if date_str == 'today':
        return datetime.combine(now.date(), datetime.min.time())
    elif date_str in ('this month', 'month'):
        return datetime(now.year, now.month, 1)
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None


@mcp.tool()
async def get_pnl_report(
    since: Optional[str] = None,
    until: Optional[str] = None
) -> MCPResponse:
    """Calculate Profit & Loss report for a time period.

    Includes realized P&L from completed trades and unrealized P&L from current holdings.

    Args:
        since: Start date for P&L calculation (default: all time)
        until: End date for P&L calculation (default: now)
    """
    try:
        _, _, pnl_calc = get_pnl_components()
        since_dt = _parse_date(since)
        until_dt = _parse_date(until)

        report = await pnl_calc.calculate(since=since_dt, until=until_dt)

        return MCPResponse(
            success=True,
            data={
                "period": f"{report.period_start.date()} to {report.period_end.date()}",
                "realized_pnl": report.realized_pnl,
                "unrealized_pnl": report.unrealized_pnl,
                "net_pnl": report.net_pnl,
                "total_sells": report.total_sells,
                "cost_basis": report.total_cost_basis,
                "current_holdings": report.current_holdings,
                "avg_cost_per_token": report.avg_cost_per_token,
                "current_price": report.current_price,
                "trade_count": report.trade_count,
                "by_exchange": report.by_exchange
            },
            metadata={"period": {"since": since, "until": until}}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_pnl_report"})


@mcp.tool()
async def get_pnl_config() -> MCPResponse:
    """Get current P&L calculation configuration including cost basis method."""
    try:
        pnl_config, _, _ = get_pnl_components()
        config = await pnl_config.get_config()
        method = await pnl_config.get_cost_basis_method()

        return MCPResponse(
            success=True,
            data={
                "cost_basis_method": method.value,
                "config": config
            },
            metadata={"tool": "get_pnl_config"}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_pnl_config"})


@mcp.tool()
async def set_cost_basis_method(method: str, user_id: str = "mcp_user") -> MCPResponse:
    """Set the cost basis calculation method for P&L reports.

    Args:
        method: Cost basis method - 'fifo', 'lifo', or 'average'
        user_id: User making the change (for audit)
    """
    try:
        pnl_config, _, _ = get_pnl_components()

        method_map = {
            "fifo": CostBasisMethod.FIFO,
            "lifo": CostBasisMethod.LIFO,
            "average": CostBasisMethod.AVERAGE,
            "avg": CostBasisMethod.AVERAGE
        }

        method_lower = method.lower()
        if method_lower not in method_map:
            return MCPResponse(
                success=False,
                error=f"Invalid method '{method}'. Use 'fifo', 'lifo', or 'average'.",
                metadata={"tool": "set_cost_basis_method"}
            )

        cost_basis_method = method_map[method_lower]
        await pnl_config.set_cost_basis_method(cost_basis_method, user_id)

        return MCPResponse(
            success=True,
            data={
                "method": cost_basis_method.value,
                "message": f"Cost basis method set to {cost_basis_method.value.upper()}."
            },
            metadata={"changed_by": user_id}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "set_cost_basis_method"})
