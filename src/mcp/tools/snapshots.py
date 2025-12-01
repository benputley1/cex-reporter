"""Snapshot and balance tools for MCP server."""

from datetime import date
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.mcp.schemas import MCPResponse
from src.mcp.server import mcp, get_data_provider


@mcp.tool()
async def get_balances() -> MCPResponse:
    """Get current token balances across all exchanges and accounts.

    Returns the latest snapshot of holdings with breakdown by exchange/account.
    """
    try:
        dp = get_data_provider()
        balances = await dp.get_balances()

        if not balances:
            return MCPResponse(
                success=True,
                data={},
                metadata={"message": "No balance data available. A snapshot may need to be taken."}
            )

        return MCPResponse(
            success=True,
            data=balances,
            metadata={"source": "latest_snapshot"}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_balances"})


@mcp.tool()
async def get_snapshots(days: int = 7) -> MCPResponse:
    """Get historical daily balance snapshots.

    Args:
        days: Number of days to look back (default 7, max 30)
    """
    try:
        dp = get_data_provider()
        days = min(days, 30)

        snapshots = await dp.get_snapshots(days=days)

        if not snapshots:
            return MCPResponse(
                success=True,
                data=[],
                metadata={"message": "No snapshots found for the specified period."}
            )

        return MCPResponse(
            success=True,
            data=snapshots,
            metadata={"count": len(snapshots), "days_requested": days}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_snapshots"})


@mcp.tool()
async def take_snapshot() -> MCPResponse:
    """Take a manual balance snapshot right now.

    Fetches current balances from cached data and saves them as today's snapshot.
    """
    try:
        dp = get_data_provider()
        balances = await dp.get_balances()

        if balances:
            dp.snapshot_manager.save_snapshot(balances)
            return MCPResponse(
                success=True,
                data={"date": date.today().isoformat(), "balances": balances},
                metadata={"message": "Snapshot saved successfully."}
            )
        else:
            return MCPResponse(
                success=False,
                error="No balance data available to snapshot. Run a refresh cycle first.",
                metadata={"tool": "take_snapshot"}
            )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "take_snapshot"})
