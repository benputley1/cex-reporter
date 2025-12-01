"""Market data tools for MCP server."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from src.mcp.schemas import MCPResponse
from src.mcp.server import mcp, get_data_provider


@mcp.tool()
async def get_current_price() -> MCPResponse:
    """Get the current ALKIMI token price from CoinGecko.

    Returns current price in USD with 24h change data if available.
    """
    try:
        dp = get_data_provider()
        price = await dp.get_current_price()

        if price is None:
            return MCPResponse(
                success=False,
                error="Unable to fetch current price. CoinGecko may be unavailable.",
                metadata={"source": "coingecko"}
            )

        return MCPResponse(
            success=True,
            data={
                "price_usd": price,
                "formatted": f"${price:.6f}"
            },
            metadata={"source": "coingecko"}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_current_price"})


@mcp.tool()
async def get_market_data() -> MCPResponse:
    """Get comprehensive market data for ALKIMI from CoinGecko.

    Returns price, 24h change, volume, and market cap data.
    """
    try:
        dp = get_data_provider()
        market_data = await dp.get_market_data()

        if not market_data:
            return MCPResponse(
                success=False,
                error="Unable to fetch market data from CoinGecko.",
                metadata={"source": "coingecko"}
            )

        return MCPResponse(
            success=True,
            data=market_data,
            metadata={"source": "coingecko"}
        )
    except Exception as e:
        return MCPResponse(success=False, error=str(e), metadata={"tool": "get_market_data"})
