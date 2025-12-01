"""Trading tools for MCP server."""

from datetime import datetime, timedelta
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.mcp.schemas import MCPResponse, TradeData
from src.mcp.server import mcp, get_data_provider


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse flexible date strings like 'today', 'this week', or ISO date."""
    if not date_str:
        return None

    date_str = date_str.lower().strip()
    now = datetime.now()

    if date_str == 'today':
        return datetime.combine(now.date(), datetime.min.time())
    elif date_str == 'yesterday':
        return datetime.combine(now.date() - timedelta(days=1), datetime.min.time())
    elif date_str in ('this week', 'week'):
        return now - timedelta(days=now.weekday())
    elif date_str in ('this month', 'month'):
        return datetime(now.year, now.month, 1)

    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None


@mcp.tool()
async def get_trades(
    since: Optional[str] = None,
    until: Optional[str] = None,
    exchange: Optional[str] = None,
    side: Optional[str] = None,
    limit: int = 20
) -> MCPResponse:
    """Get trade history with optional filters.

    Args:
        since: Start date ('today', 'this week', 'YYYY-MM-DD')
        until: End date (same formats as since)
        exchange: Filter by exchange (mexc, kraken, kucoin, gateio)
        side: Filter by trade side (buy, sell)
        limit: Maximum trades to return (default 20, max 100)
    """
    try:
        dp = get_data_provider()
        since_dt = _parse_date(since)
        until_dt = _parse_date(until)
        limit = min(limit, 100)

        df = await dp.get_trades_df(since=since_dt, until=until_dt, exchange=exchange)

        if side:
            df = df[df['side'] == side]

        if df.empty:
            return MCPResponse(
                success=True,
                data=[],
                metadata={"count": 0, "filters": {"since": since, "exchange": exchange, "side": side}}
            )

        df = df.head(limit)

        trades = []
        for _, row in df.iterrows():
            trades.append({
                "timestamp": row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else str(row['timestamp']),
                "exchange": row['exchange'],
                "side": row['side'],
                "amount": float(row['amount']),
                "price": float(row['price']),
                "value_usd": float(row['amount'] * row['price']),
                "trade_id": row.get('trade_id')
            })

        return MCPResponse(
            success=True,
            data=trades,
            metadata={"count": len(trades), "filters": {"since": since, "exchange": exchange, "side": side}}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_trades"})


@mcp.tool()
async def get_trade_summary(
    since: Optional[str] = None,
    until: Optional[str] = None
) -> MCPResponse:
    """Get aggregated trading statistics.

    Args:
        since: Start date for summary period
        until: End date for summary period
    """
    try:
        dp = get_data_provider()
        since_dt = _parse_date(since)
        until_dt = _parse_date(until)

        summary = await dp.get_trade_summary(since=since_dt, until=until_dt)

        return MCPResponse(
            success=True,
            data=summary,
            metadata={"period": {"since": since, "until": until}}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_trade_summary"})
