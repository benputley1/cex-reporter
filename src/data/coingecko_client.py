"""
CoinGecko API Client for ALKIMI price data
"""
import aiohttp
from datetime import datetime
from typing import Optional, Dict


class CoinGeckoClient:
    """Client for fetching ALKIMI price data from CoinGecko API"""

    BASE_URL = "https://api.coingecko.com/api/v3"
    ALKIMI_ID = "alkimi"  # CoinGecko ID for ALKIMI

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self):
        """Ensure aiohttp session exists"""
        if self.session is None or self.session.closed:
            self.session = aiohttp.ClientSession()

    async def get_current_price(self) -> Optional[float]:
        """
        Get current ALKIMI price in USD

        Returns:
            Current price in USD, or None if fetch fails
        """
        try:
            await self._ensure_session()

            url = f"{self.BASE_URL}/simple/price"
            params = {
                'ids': self.ALKIMI_ID,
                'vs_currencies': 'usd'
            }

            async with self.session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get(self.ALKIMI_ID, {}).get('usd')
                else:
                    print(f"CoinGecko API error: {response.status}")
                    return None

        except Exception as e:
            print(f"Error fetching current price from CoinGecko: {e}")
            return None

    async def get_historical_price(self, date: datetime) -> Optional[float]:
        """
        Get ALKIMI price on a specific date (opening price)

        Args:
            date: The date to fetch price for

        Returns:
            Price in USD on that date, or None if fetch fails
        """
        try:
            await self._ensure_session()

            # Format date as DD-MM-YYYY for CoinGecko
            date_str = date.strftime("%d-%m-%Y")

            url = f"{self.BASE_URL}/coins/{self.ALKIMI_ID}/history"
            params = {
                'date': date_str,
                'localization': 'false'
            }

            async with self.session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    return data.get('market_data', {}).get('current_price', {}).get('usd')
                else:
                    print(f"CoinGecko API error: {response.status}")
                    return None

        except Exception as e:
            print(f"Error fetching historical price from CoinGecko: {e}")
            return None

    async def get_market_data(self) -> Optional[Dict]:
        """
        Get comprehensive market data for ALKIMI

        Returns:
            Dictionary with price, volume, market cap, etc.
        """
        try:
            await self._ensure_session()

            url = f"{self.BASE_URL}/coins/{self.ALKIMI_ID}"
            params = {
                'localization': 'false',
                'tickers': 'false',
                'community_data': 'false',
                'developer_data': 'false',
                'sparkline': 'false'
            }

            async with self.session.get(url, params=params, timeout=10) as response:
                if response.status == 200:
                    data = await response.json()
                    market_data = data.get('market_data', {})

                    return {
                        'current_price': market_data.get('current_price', {}).get('usd'),
                        'total_volume': market_data.get('total_volume', {}).get('usd'),
                        'market_cap': market_data.get('market_cap', {}).get('usd'),
                        'price_change_24h': market_data.get('price_change_24h'),
                        'price_change_percentage_24h': market_data.get('price_change_percentage_24h'),
                    }
                else:
                    print(f"CoinGecko API error: {response.status}")
                    return None

        except Exception as e:
            print(f"Error fetching market data from CoinGecko: {e}")
            return None

    async def close(self):
        """Close the aiohttp session"""
        if self.session and not self.session.closed:
            await self.session.close()
