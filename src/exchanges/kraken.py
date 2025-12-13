"""
Kraken Exchange Client Implementation

Provides integration with Kraken exchange using ccxt library or mock data.
Note: ALKIMI is not listed on Kraken, so ALKIMI balance will always be 0.
"""

import ccxt.async_support as ccxt
from typing import Dict, List, Optional

from src.exchanges.base import CCXTExchangeClient
from config.settings import settings


class KrakenClient(CCXTExchangeClient):
    """
    Kraken exchange client implementation.

    Rate limiting: 15 requests per second
    Tracked assets: USDT only (ALKIMI not listed on Kraken)
    """

    RATE_LIMIT = 1.0 / 15.0  # 15 requests per second

    def __init__(self, config: Dict[str, str] = None, mock_mode: bool = None, account_name: str = None):
        """
        Initialize Kraken client.

        Args:
            config: API configuration dictionary with 'apiKey' and 'secret'
            mock_mode: If True, use mock data. If None, use settings.mock_mode
            account_name: Optional account identifier (e.g., 'MAIN')
        """
        if mock_mode is None:
            mock_mode = settings.mock_mode

        if config is None:
            config = settings.kraken_config

        super().__init__(
            exchange_name='kraken',
            ccxt_class=ccxt.kraken,
            config=config,
            mock_mode=mock_mode,
            account_name=account_name,
            tracked_assets=settings.tracked_assets
        )

    def _map_asset_symbol(self, asset: str) -> str:
        """
        Map standard asset symbol to Kraken-specific symbol.
        Kraken uses 'USD' instead of 'USDT' for the fiat currency.

        Args:
            asset: Standard asset symbol

        Returns:
            Kraken-specific asset symbol
        """
        # Use settings if available, otherwise default mapping
        if hasattr(settings, 'get_exchange_asset'):
            return settings.get_exchange_asset('kraken', asset)

        # Fallback mapping
        if asset == 'USDT':
            return 'USD'
        return asset

    def _get_trading_pairs(self, asset: str) -> List[str]:
        """
        Get list of trading pairs to try for an asset on Kraken.

        Args:
            asset: Asset symbol

        Returns:
            List of trading pair strings to try
        """
        kraken_symbol = self._map_asset_symbol(asset)

        if asset == 'ALKIMI':
            return [f"{kraken_symbol}/USD"]
        else:
            return [f"{kraken_symbol}/USD", f"{kraken_symbol}/EUR"]

    def _get_price_pairs(self, symbol: str) -> List[str]:
        """
        Get list of price pairs to try for a symbol on Kraken.

        Args:
            symbol: Asset symbol

        Returns:
            List of price pair strings to try
        """
        # USD/USDT is pegged to 1.0, handled in base class
        return [f"{symbol}/USD", f"{symbol}/USDT"]

    def _is_symbol_available(self, symbol: str) -> bool:
        """
        Check if symbol is available on Kraken.
        ALKIMI is not listed on Kraken.

        Args:
            symbol: Asset symbol

        Returns:
            True if available, False otherwise
        """
        if symbol == 'ALKIMI':
            return False
        return True
