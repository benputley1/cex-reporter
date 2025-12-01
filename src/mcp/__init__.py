"""
MCP (Model Context Protocol) Server Package

Provides structured tools for accessing ALKIMI trading bot data via MCP.
"""

__version__ = "0.1.0"

from .schemas import (
    MCPResponse,
    TradeData,
    BalanceData,
    PoolInfo,
    HolderInfo,
    PnLReport,
)

__all__ = [
    "MCPResponse",
    "TradeData",
    "BalanceData",
    "PoolInfo",
    "HolderInfo",
    "PnLReport",
]
