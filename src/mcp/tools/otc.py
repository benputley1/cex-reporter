"""OTC (Over-The-Counter) transaction tools for MCP server."""

from datetime import datetime
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.mcp.schemas import MCPResponse
from src.mcp.server import mcp, get_data_provider
from src.bot.pnl_config import OTCManager


# Shared OTC manager instance
_otc_manager = None


def get_otc_manager():
    """Get or initialize OTC manager."""
    global _otc_manager
    if _otc_manager is None:
        _otc_manager = OTCManager()
    return _otc_manager


@mcp.tool()
async def get_otc_transactions() -> MCPResponse:
    """List all OTC (over-the-counter) transactions."""
    try:
        otc = get_otc_manager()
        transactions = await otc.list_all()

        if not transactions:
            return MCPResponse(
                success=True,
                data=[],
                metadata={"message": "No OTC transactions recorded."}
            )

        otc_list = []
        for t in transactions:
            otc_list.append({
                "id": t.id,
                "date": t.date.isoformat() if hasattr(t.date, 'isoformat') else str(t.date),
                "side": t.side,
                "alkimi_amount": t.alkimi_amount,
                "usd_amount": t.usd_amount,
                "price": t.price,
                "counterparty": t.counterparty
            })

        return MCPResponse(
            success=True,
            data=otc_list,
            metadata={"count": len(otc_list)}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_otc_transactions"})


@mcp.tool()
async def add_otc_transaction(
    date: str,
    alkimi_amount: float,
    usd_amount: float,
    side: str,
    counterparty: Optional[str] = None,
    notes: Optional[str] = None,
    user_id: str = "mcp_user"
) -> MCPResponse:
    """Record a new OTC transaction.

    Args:
        date: Transaction date (YYYY-MM-DD)
        alkimi_amount: Amount of ALKIMI tokens
        usd_amount: USD value of the transaction
        side: 'buy' or 'sell'
        counterparty: Name of the counterparty (optional)
        notes: Additional notes (optional)
        user_id: User recording the transaction
    """
    try:
        otc = get_otc_manager()

        # Validate side
        side_lower = side.lower()
        if side_lower not in ('buy', 'sell'):
            return MCPResponse(
                success=False,
                error=f"Invalid side '{side}'. Use 'buy' or 'sell'.",
                metadata={"tool": "add_otc_transaction"}
            )

        # Parse date
        try:
            otc_date = datetime.fromisoformat(date)
        except ValueError:
            return MCPResponse(
                success=False,
                error=f"Invalid date format '{date}'. Use YYYY-MM-DD.",
                metadata={"tool": "add_otc_transaction"}
            )

        otc_id = await otc.add(
            date=otc_date,
            alkimi_amount=alkimi_amount,
            usd_amount=usd_amount,
            side=side_lower,
            counterparty=counterparty,
            notes=notes,
            created_by=user_id
        )

        return MCPResponse(
            success=True,
            data={
                "otc_id": otc_id,
                "message": f"OTC transaction #{otc_id} recorded successfully."
            },
            metadata={"created_by": user_id}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "add_otc_transaction"})
