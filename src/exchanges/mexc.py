"""
MEXC Exchange Client Implementation

Provides integration with MEXC exchange using ccxt library or mock data.
Supports balance checking, trade history, and price fetching with rate limiting.
"""

import ccxt.async_support as ccxt
from typing import Dict, List, Optional

from src.exchanges.base import CCXTExchangeClient
from config.settings import settings


class MEXCClient(CCXTExchangeClient):
    """
    MEXC exchange client implementation.

    Rate limiting: 20 requests per second
    Tracked assets: USDT, ALKIMI
    """

    RATE_LIMIT = 1.0 / 20.0  # 20 requests per second

    def __init__(self, config: Dict[str, str] = None, mock_mode: bool = None, account_name: str = None):
        """
        Initialize MEXC client.

        Args:
            config: API configuration dictionary with 'apiKey' and 'secret'
            mock_mode: If True, use mock data. If None, use settings.mock_mode
            account_name: Optional account identifier (e.g., 'MM1', 'TM1')
        """
        if mock_mode is None:
            mock_mode = settings.mock_mode

        if config is None:
            config = settings.mexc_config

        super().__init__(
            exchange_name='mexc',
            ccxt_class=ccxt.mexc,
            config=config,
            mock_mode=mock_mode,
            account_name=account_name,
            tracked_assets=settings.tracked_assets
        )
