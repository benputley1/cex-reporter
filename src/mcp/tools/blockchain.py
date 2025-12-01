"""Blockchain analytics tools for MCP server."""

from datetime import datetime, timedelta
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.mcp.schemas import MCPResponse
from src.mcp.server import mcp, get_data_provider


@mcp.tool()
async def get_treasury_value() -> MCPResponse:
    """Get the total treasury value including USDT and ALKIMI holdings.

    Aggregates balances across all monitored wallets.
    """
    try:
        dp = get_data_provider()

        if not dp.sui_monitor:
            return MCPResponse(
                success=False,
                error="Sui DEX monitor not configured. Set ALKIMI_TOKEN_CONTRACT environment variable.",
                metadata={"tool": "get_treasury_value"}
            )

        treasury = await dp.sui_monitor.get_treasury_value()

        if not treasury:
            return MCPResponse(
                success=False,
                error="Unable to fetch treasury value.",
                metadata={"tool": "get_treasury_value"}
            )

        return MCPResponse(
            success=True,
            data={
                "total_value_usd": float(treasury.total_value_usd) if hasattr(treasury, 'total_value_usd') else float(treasury.get('total_value_usd', 0)),
                "usdt_balance": float(treasury.usdt_balance) if hasattr(treasury, 'usdt_balance') else float(treasury.get('usdt_balance', 0)),
                "alkimi_balance": float(treasury.alkimi_balance) if hasattr(treasury, 'alkimi_balance') else float(treasury.get('alkimi_balance', 0)),
                "alkimi_value_usd": float(treasury.alkimi_value_usd) if hasattr(treasury, 'alkimi_value_usd') else float(treasury.get('alkimi_value_usd', 0)),
                "alkimi_price": float(treasury.alkimi_price) if hasattr(treasury, 'alkimi_price') else float(treasury.get('alkimi_price', 0)),
                "timestamp": treasury.timestamp.isoformat() if hasattr(treasury, 'timestamp') and hasattr(treasury.timestamp, 'isoformat') else str(treasury.get('timestamp', datetime.now().isoformat()))
            },
            metadata={"source": "sui_wallets"}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_treasury_value"})


@mcp.tool()
async def get_top_holders(limit: int = 10) -> MCPResponse:
    """Get list of top ALKIMI token holders on Sui blockchain.

    Args:
        limit: Number of top holders to return (default 10, max 50)
    """
    try:
        dp = get_data_provider()

        if not dp.sui_monitor:
            return MCPResponse(
                success=False,
                error="Sui DEX monitor not configured. Set ALKIMI_TOKEN_CONTRACT environment variable.",
                metadata={"tool": "get_top_holders"}
            )

        limit = min(limit, 50)
        holders = await dp.sui_monitor.get_top_holders(limit=limit)

        if not holders:
            return MCPResponse(
                success=True,
                data=[],
                metadata={"message": "Unable to fetch top holders."}
            )

        holder_data = []
        for h in holders:
            holder_data.append({
                "address": h.address if hasattr(h, 'address') else str(h.get('address', '')),
                "balance": float(h.balance) if hasattr(h, 'balance') else float(h.get('balance', 0)),
                "percentage": float(h.percentage) if hasattr(h, 'percentage') else float(h.get('percentage', 0)),
                "label": h.label if hasattr(h, 'label') else h.get('label')
            })

        return MCPResponse(
            success=True,
            data=holder_data,
            metadata={"count": len(holder_data)}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_top_holders"})


@mcp.tool()
async def get_wallet_activity(address: str) -> MCPResponse:
    """Get recent activity for a specific wallet address.

    Includes transactions, swaps, and balance changes.

    Args:
        address: Sui wallet address to track
    """
    try:
        dp = get_data_provider()

        if not dp.sui_monitor:
            return MCPResponse(
                success=False,
                error="Sui DEX monitor not configured. Set ALKIMI_TOKEN_CONTRACT environment variable.",
                metadata={"tool": "get_wallet_activity"}
            )

        if not address:
            return MCPResponse(
                success=False,
                error="Wallet address is required.",
                metadata={"tool": "get_wallet_activity"}
            )

        activity = await dp.sui_monitor.get_wallet_activity(address)

        if not activity:
            return MCPResponse(
                success=True,
                data={},
                metadata={"message": f"No activity found for wallet {address}."}
            )

        return MCPResponse(
            success=True,
            data=activity,
            metadata={"address": address}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_wallet_activity"})
