"""
KuCoin Exchange Client Implementation

Provides integration with KuCoin exchange using ccxt library or mock data.
Note: KuCoin requires apiKey, secret, and passphrase for authentication.
"""

import ccxt.async_support as ccxt
from typing import Dict, List, Optional

from src.exchanges.base import CCXTExchangeClient
from config.settings import settings


class KuCoinClient(CCXTExchangeClient):
    """
    KuCoin exchange client implementation.

    Rate limiting: 30 requests per second
    Tracked assets: USDT, ALKIMI
    Authentication: Requires apiKey, secret, and passphrase
    """

    RATE_LIMIT = 1.0 / 30.0  # 30 requests per second

    def __init__(self, config: Dict[str, str] = None, mock_mode: bool = None, account_name: str = None):
        """
        Initialize KuCoin client.

        Args:
            config: API configuration dictionary with 'apiKey', 'secret', and 'password' (passphrase)
            mock_mode: If True, use mock data. If None, use settings.mock_mode
            account_name: Optional account identifier (e.g., 'MAIN')
        """
        if mock_mode is None:
            mock_mode = settings.mock_mode

        if config is None:
            config = settings.kucoin_config

        super().__init__(
            exchange_name='kucoin',
            ccxt_class=ccxt.kucoin,
            config=config,
            mock_mode=mock_mode,
            account_name=account_name,
            tracked_assets=settings.tracked_assets
        )
