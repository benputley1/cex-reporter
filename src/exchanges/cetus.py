"""
Cetus Protocol Client Implementation

Provides integration with Cetus DEX on Sui blockchain for tracking
liquidity positions, pending rewards, and position values.
"""

import asyncio
import aiohttp
from datetime import datetime
from typing import Dict, List
from decimal import Decimal

from src.exchanges.base import (
    ExchangeInterface,
    Trade,
    TradeSide,
    Transaction,
    ExchangeError,
    ExchangeConnectionError,
    ExchangeAuthError,
    ExchangeRateLimitError,
)
from src.utils.cache import cached
from src.utils.logging import get_logger
from src.utils.retry import retry_with_backoff
from config.settings import settings


logger = get_logger(__name__)


class CetusClient(ExchangeInterface):
    """
    Cetus Protocol client implementation for Sui blockchain.

    Tracks liquidity positions and pending rewards via REST APIs.
    """

    # API endpoints
    EXPAND_API_BASE = "https://api.expand.network/dex"
    CETUS_API_BASE = "https://api-sui.cetus.zone"
    SUI_RPC = "https://fullnode.mainnet.sui.io"

    # DEX ID for Cetus on expand.network
    DEX_ID = "3300"  # Mainnet

    RATE_LIMIT = 1.0  # 1 request per second for safety

    def __init__(self, config: Dict[str, str] = None, mock_mode: bool = None, account_name: str = None):
        """
        Initialize Cetus client.

        Args:
            config: Configuration dictionary with 'wallet_address'
            mock_mode: If True, use mock data. If None, use settings.mock_mode
            account_name: Optional account identifier (e.g., 'MAIN')
        """
        if mock_mode is None:
            mock_mode = settings.mock_mode

        if config is None:
            config = {}

        super().__init__(exchange_name='cetus', config=config, mock_mode=mock_mode, account_name=account_name)

        self.wallet_address = config.get('wallet_address', '')
        self.session = None
        self._last_request_time = 0

        # Track position data
        self.positions_data = {
            'total_value_usd': 0.0,
            'pending_rewards_usd': 0.0,
            'positions': []
        }

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    async def initialize(self) -> None:
        """
        Initialize Cetus client connection.

        Raises:
            ExchangeConnectionError: If connection fails
            ExchangeAuthError: If wallet address is invalid
        """
        if self._initialized:
            logger.debug("Cetus client already initialized")
            return

        try:
            if self.mock_mode:
                logger.info(f"Cetus client ({self.account_name}) initialized in MOCK mode")
                self._initialized = True
                return

            # Validate wallet address
            if not self.wallet_address:
                raise ExchangeAuthError("Cetus wallet address not configured")

            # Create aiohttp session
            self.session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )

            logger.info(f"Cetus client initialized successfully for wallet: {self.wallet_address[:8]}...")
            self._initialized = True

        except Exception as e:
            self._handle_error(e, "initialize")

    async def _rate_limit(self) -> None:
        """Apply rate limiting between requests"""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self.RATE_LIMIT:
            await asyncio.sleep(self.RATE_LIMIT - time_since_last)

        self._last_request_time = asyncio.get_event_loop().time()

    async def _fetch_user_liquidity(self) -> Dict:
        """
        Fetch user liquidity positions from expand.network API.

        Returns:
            Dictionary with position data
        """
        await self._rate_limit()

        try:
            params = {
                'dexId': self.DEX_ID,
                'address': self.wallet_address
            }

            async with self.session.get(
                f"{self.EXPAND_API_BASE}/getuserliquidity",
                params=params
            ) as response:
                if response.status == 200:
                    data = await response.json()
                    return data
                else:
                    logger.warning(f"Cetus API returned status {response.status}")
                    return {}

        except Exception as e:
            logger.error(f"Error fetching Cetus liquidity: {e}")
            return {}

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    @cached(ttl=60)
    async def get_balances(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch Cetus position values as "balances".

        Returns balances representing liquidity positions:
        - CETUS_LP: Total liquidity position value
        - CETUS_REWARDS: Pending rewards value

        Returns:
            Dictionary mapping asset symbols to balance details
            Example: {
                "CETUS_LP": {"free": 5000.0, "locked": 0.0, "total": 5000.0},
                "CETUS_REWARDS": {"free": 50.0, "locked": 0.0, "total": 50.0}
            }

        Raises:
            ExchangeConnectionError: If connection fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            if self.mock_mode:
                logger.debug("Fetching Cetus positions (mock mode)")
                return {
                    "CETUS_LP": {"free": 1000.0, "locked": 0.0, "total": 1000.0},
                    "CETUS_REWARDS": {"free": 25.0, "locked": 0.0, "total": 25.0}
                }

            # Fetch liquidity data
            liquidity_data = await self._fetch_user_liquidity()

            # Parse and calculate total position value
            total_lp_value = 0.0
            total_rewards = 0.0
            positions = []

            if liquidity_data and 'data' in liquidity_data:
                for position in liquidity_data.get('data', []):
                    # Extract position details
                    pool_name = position.get('poolName', 'Unknown')
                    liquidity_usd = float(position.get('liquidityUSD', 0))
                    rewards_usd = float(position.get('rewardsUSD', 0))

                    total_lp_value += liquidity_usd
                    total_rewards += rewards_usd

                    positions.append({
                        'pool': pool_name,
                        'liquidity_usd': liquidity_usd,
                        'rewards_usd': rewards_usd
                    })

            # Store for reporting
            self.positions_data = {
                'total_value_usd': total_lp_value,
                'pending_rewards_usd': total_rewards,
                'positions': positions
            }

            balances = {
                "CETUS_LP": {
                    "free": total_lp_value,
                    "locked": 0.0,
                    "total": total_lp_value
                },
                "CETUS_REWARDS": {
                    "free": total_rewards,
                    "locked": 0.0,
                    "total": total_rewards
                }
            }

            logger.info(f"Cetus positions fetched: LP=${total_lp_value:.2f}, Rewards=${total_rewards:.2f}")
            return balances

        except Exception as e:
            self._handle_error(e, "get_balances")

    @retry_with_backoff(max_retries=3, initial_delay=2.0)
    @cached(ttl=60)
    async def get_trades(self, since: datetime) -> List[Trade]:
        """
        Cetus doesn't provide trade history in the same way as CEXs.
        Returns empty list as we're tracking positions, not trades.

        Args:
            since: Datetime to fetch trades from (unused for Cetus)

        Returns:
            Empty list (Cetus tracks positions, not individual trades)
        """
        if not self._initialized:
            await self.initialize()

        logger.debug("Cetus: get_trades called but not applicable for DeFi positions")
        return []

    async def get_deposits(self, since: datetime) -> List[Transaction]:
        """
        Cetus doesn't track deposits in the traditional sense.
        Returns empty list.

        Args:
            since: Datetime to fetch deposits from (unused)

        Returns:
            Empty list
        """
        return []

    async def get_withdrawals(self, since: datetime) -> List[Transaction]:
        """
        Cetus doesn't track withdrawals in the traditional sense.
        Returns empty list.

        Args:
            since: Datetime to fetch withdrawals from (unused)

        Returns:
            Empty list
        """
        return []

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    @cached(ttl=60)
    async def get_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Get current prices for Cetus-tracked assets.

        For Cetus, we return 1.0 for LP and REWARDS tokens since they're
        already denominated in USD.

        Args:
            symbols: List of asset symbols

        Returns:
            Dictionary mapping symbols to USD prices
        """
        if not self._initialized:
            await self.initialize()

        try:
            if self.mock_mode:
                return {"CETUS_LP": 1.0, "CETUS_REWARDS": 1.0}

            # For Cetus, our "balances" are already in USD
            # So we return 1.0 as the price
            prices = {}
            for symbol in symbols:
                if symbol in ["CETUS_LP", "CETUS_REWARDS"]:
                    prices[symbol] = 1.0
                else:
                    prices[symbol] = 0.0

            return prices

        except Exception as e:
            self._handle_error(e, "get_prices")

    async def close(self) -> None:
        """
        Close Cetus client connection and cleanup resources.
        """
        try:
            if self.session:
                await self.session.close()
                logger.info("Cetus client closed successfully")
        except Exception as e:
            logger.warning(f"Error closing Cetus client: {e}")
        finally:
            self._initialized = False
            self.session = None
