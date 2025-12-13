"""
Gate.io Exchange Client Implementation

Provides integration with Gate.io exchange using ccxt library or mock data.
Supports balance checking, trade history, and price fetching with rate limiting.
"""

import ccxt.async_support as ccxt
from typing import Dict, List, Optional

from src.exchanges.base import CCXTExchangeClient
from config.settings import settings


class GateioClient(CCXTExchangeClient):
    """
    Gate.io exchange client implementation.

    Rate limiting: 100 requests per second
    Tracked assets: USDT, ALKIMI
    """

    RATE_LIMIT = 1.0 / 100.0  # 100 requests per second

    def __init__(self, config: Dict[str, str] = None, mock_mode: bool = None, account_name: str = None):
        """
        Initialize Gate.io client.

        Args:
            config: API configuration dictionary with 'apiKey' and 'secret'
            mock_mode: If True, use mock data. If None, use settings.mock_mode
            account_name: Optional account identifier (e.g., 'MM1', 'TM')
        """
        if mock_mode is None:
            mock_mode = settings.mock_mode

        if config is None:
            config = settings.gateio_config

        super().__init__(
            exchange_name='gateio',
            ccxt_class=ccxt.gateio,
            config=config,
            mock_mode=mock_mode,
            account_name=account_name,
            tracked_assets=settings.tracked_assets
        )
