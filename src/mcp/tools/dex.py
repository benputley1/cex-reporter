"""DEX (Decentralized Exchange) tools for MCP server."""

from datetime import datetime, timedelta
from typing import Optional
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.mcp.schemas import MCPResponse
from src.mcp.server import mcp, get_data_provider


def _parse_date(date_str: str) -> Optional[datetime]:
    """Parse flexible date strings."""
    if not date_str:
        return None
    date_str = date_str.lower().strip()
    now = datetime.now()
    if date_str == 'today':
        return datetime.combine(now.date(), datetime.min.time())
    elif date_str in ('this week', 'week'):
        return now - timedelta(days=now.weekday())
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return None


@mcp.tool()
async def get_dex_trades(
    since: Optional[str] = None,
    limit: int = 50
) -> MCPResponse:
    """Get DEX trades for ALKIMI on Sui blockchain.

    Shows swap activity across Cetus, Turbos, BlueMove, and Aftermath DEXs.

    Args:
        since: Start date (YYYY-MM-DD or 'today', 'this week'). Default: 7 days ago
        limit: Maximum trades to return (default 50, max 100)
    """
    try:
        dp = get_data_provider()
        since_dt = _parse_date(since)
        if since_dt is None:
            since_dt = datetime.now() - timedelta(days=7)
        limit = min(limit, 100)

        df = await dp.get_dex_trades(since=since_dt)

        if df.empty:
            return MCPResponse(
                success=True,
                data=[],
                metadata={"message": "No DEX trades found. Sui DEX monitor may not be configured or no recent swaps occurred."}
            )

        trades = []
        for _, row in df.head(limit).iterrows():
            trades.append({
                "timestamp": row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else str(row['timestamp']),
                "exchange": row.get('exchange', 'sui_dex'),
                "side": row.get('side', 'unknown'),
                "amount": float(row['amount']) if 'amount' in row else 0,
                "price": float(row['price']) if 'price' in row else 0,
                "value_usd": float(row['amount'] * row['price']) if 'amount' in row and 'price' in row else 0
            })

        return MCPResponse(
            success=True,
            data=trades,
            metadata={"count": len(trades), "dex": "Sui (Cetus, Turbos, BlueMove, Aftermath)"}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_dex_trades"})


@mcp.tool()
async def get_alkimi_pools() -> MCPResponse:
    """Get liquidity pool data for ALKIMI across Sui DEXs.

    Shows TVL, 24h volume, price, and liquidity depth for each pool.
    """
    try:
        dp = get_data_provider()

        if not dp.sui_monitor:
            return MCPResponse(
                success=False,
                error="Sui DEX monitor not configured. Set ALKIMI_TOKEN_CONTRACT environment variable.",
                metadata={"tool": "get_alkimi_pools"}
            )

        pools = await dp.sui_monitor.get_alkimi_pools()

        if not pools:
            return MCPResponse(
                success=True,
                data=[],
                metadata={"message": "No liquidity pools found for ALKIMI on Sui DEXs."}
            )

        # Convert to serializable format
        pool_data = []
        for pool in pools:
            pool_data.append({
                "pool_id": pool.pool_id if hasattr(pool, 'pool_id') else str(pool.get('pool_id', '')),
                "dex": pool.dex if hasattr(pool, 'dex') else str(pool.get('dex', '')),
                "name": pool.name if hasattr(pool, 'name') else str(pool.get('name', '')),
                "tvl_usd": float(pool.tvl_usd) if hasattr(pool, 'tvl_usd') else float(pool.get('tvl_usd', 0)),
                "volume_24h": float(pool.volume_24h) if hasattr(pool, 'volume_24h') else float(pool.get('volume_24h', 0)),
                "price": float(pool.price) if hasattr(pool, 'price') else float(pool.get('price', 0))
            })

        return MCPResponse(
            success=True,
            data=pool_data,
            metadata={"count": len(pool_data)}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_alkimi_pools"})


@mcp.tool()
async def get_onchain_analytics() -> MCPResponse:
    """Get on-chain analytics for ALKIMI token.

    Returns holder count, top holders, supply distribution, and wallet activity.
    """
    try:
        dp = get_data_provider()

        if not dp.sui_monitor:
            return MCPResponse(
                success=False,
                error="Sui DEX monitor not configured. Set ALKIMI_TOKEN_CONTRACT environment variable.",
                metadata={"tool": "get_onchain_analytics"}
            )

        analytics = await dp.sui_monitor.get_onchain_analytics()

        if not analytics:
            return MCPResponse(
                success=False,
                error="Unable to fetch on-chain analytics.",
                metadata={"tool": "get_onchain_analytics"}
            )

        return MCPResponse(
            success=True,
            data=analytics,
            metadata={"source": "sui_blockchain"}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_onchain_analytics"})
