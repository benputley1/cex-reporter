"""
Pydantic schemas for MCP server responses.

Defines standardized data structures for all MCP tools to ensure
consistent response formats and type safety.
"""

from pydantic import BaseModel, Field
from typing import Any, Optional, Dict, List
from datetime import datetime


class MCPResponse(BaseModel):
    """Standardized response format for all MCP tools."""

    success: bool = Field(
        description="Whether the operation completed successfully"
    )
    data: Any = Field(
        default=None,
        description="The response data, structure varies by tool"
    )
    error: Optional[str] = Field(
        default=None,
        description="Error message if operation failed"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict,
        description="Additional metadata about the response (timestamps, counts, etc.)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "success": True,
                "data": {"trades": [], "count": 0},
                "error": None,
                "metadata": {"query_time_ms": 45, "timestamp": "2025-12-01T00:00:00Z"}
            }
        }


class TradeData(BaseModel):
    """Trade record structure."""

    timestamp: datetime = Field(
        description="When the trade was executed"
    )
    exchange: str = Field(
        description="Exchange name (e.g., 'mexc', 'kucoin', 'cetus')"
    )
    side: str = Field(
        description="Trade side: 'buy' or 'sell'"
    )
    amount: float = Field(
        description="Amount of asset traded"
    )
    price: float = Field(
        description="Price per unit in USD or quote currency"
    )
    value_usd: float = Field(
        description="Total USD value of the trade"
    )
    trade_id: Optional[str] = Field(
        default=None,
        description="Unique trade identifier from exchange"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2025-12-01T12:00:00Z",
                "exchange": "mexc",
                "side": "buy",
                "amount": 10000.0,
                "price": 0.0234,
                "value_usd": 234.0,
                "trade_id": "12345"
            }
        }


class BalanceData(BaseModel):
    """Balance record structure."""

    exchange: str = Field(
        description="Exchange or wallet name"
    )
    asset: str = Field(
        description="Asset symbol (e.g., 'ALKIMI', 'USDT')"
    )
    free: float = Field(
        description="Available balance for trading"
    )
    locked: float = Field(
        description="Balance locked in orders"
    )
    total: float = Field(
        description="Total balance (free + locked)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "exchange": "mexc",
                "asset": "ALKIMI",
                "free": 45000.0,
                "locked": 5000.0,
                "total": 50000.0
            }
        }


class PoolInfo(BaseModel):
    """DEX liquidity pool information."""

    pool_id: str = Field(
        description="Unique pool identifier (address or ID)"
    )
    dex: str = Field(
        description="DEX name (e.g., 'cetus', 'turbos')"
    )
    name: str = Field(
        description="Human-readable pool name"
    )
    token_a: str = Field(
        description="First token symbol"
    )
    token_b: str = Field(
        description="Second token symbol"
    )
    tvl_usd: float = Field(
        description="Total Value Locked in USD"
    )
    volume_24h: float = Field(
        description="24-hour trading volume in USD"
    )
    price: float = Field(
        description="Current price of token_a in terms of token_b"
    )
    fee_tier: str = Field(
        description="Pool fee tier (e.g., '0.3%', '1%')"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "pool_id": "0x7d21a...",
                "dex": "cetus",
                "name": "ALKIMI-USDC",
                "token_a": "ALKIMI",
                "token_b": "USDC",
                "tvl_usd": 125000.0,
                "volume_24h": 15000.0,
                "price": 0.0234,
                "fee_tier": "0.3%"
            }
        }


class HolderInfo(BaseModel):
    """Token holder information."""

    address: str = Field(
        description="Wallet address"
    )
    balance: float = Field(
        description="Token balance held"
    )
    percentage: float = Field(
        description="Percentage of total supply held"
    )
    rank: int = Field(
        description="Holder rank by balance (1 = largest)"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "address": "0x742d35Cc...",
                "balance": 1500000.0,
                "percentage": 1.5,
                "rank": 1
            }
        }


class PnLReport(BaseModel):
    """Profit and Loss report structure."""

    period_start: datetime = Field(
        description="Start of reporting period"
    )
    period_end: datetime = Field(
        description="End of reporting period"
    )
    realized_pnl: float = Field(
        description="Realized profit/loss from closed positions"
    )
    unrealized_pnl: float = Field(
        description="Unrealized profit/loss from open positions"
    )
    net_pnl: float = Field(
        description="Total P&L (realized + unrealized)"
    )
    trade_count: int = Field(
        description="Number of trades in the period"
    )
    cost_basis_method: str = Field(
        description="Cost basis calculation method (e.g., 'FIFO', 'LIFO', 'Average')"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "period_start": "2025-11-01T00:00:00Z",
                "period_end": "2025-11-30T23:59:59Z",
                "realized_pnl": 5420.50,
                "unrealized_pnl": -230.25,
                "net_pnl": 5190.25,
                "trade_count": 142,
                "cost_basis_method": "FIFO"
            }
        }
