"""
KuCoin Exchange Client Implementation

Provides integration with KuCoin exchange using ccxt library or mock data.
Note: KuCoin requires apiKey, secret, and passphrase for authentication.
"""

import asyncio
import ccxt.async_support as ccxt
from datetime import datetime
from typing import Dict, List

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
from src.utils.mock_data import get_mock_balances, get_mock_prices, get_cached_trades
from config.settings import settings


logger = get_logger(__name__)


class KuCoinClient(ExchangeInterface):
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

        super().__init__(exchange_name='kucoin', config=config, mock_mode=mock_mode, account_name=account_name)
        self.exchange = None
        self._last_request_time = 0

    async def initialize(self) -> None:
        """
        Initialize KuCoin exchange connection.

        Raises:
            ExchangeConnectionError: If connection fails
            ExchangeAuthError: If authentication fails
        """
        if self._initialized:
            logger.debug("KuCoin client already initialized")
            return

        try:
            if self.mock_mode:
                logger.info("KuCoin client initialized in MOCK mode")
                self._initialized = True
                return

            # Initialize ccxt KuCoin exchange
            self.exchange = ccxt.kucoin({
                'apiKey': self.config.get('apiKey'),
                'secret': self.config.get('secret'),
                'password': self.config.get('password'),  # KuCoin passphrase
                'enableRateLimit': True,
                'options': {
                    'defaultType': 'spot',
                }
            })

            # Test connection by fetching markets
            await self.exchange.load_markets()

            logger.info("KuCoin client initialized successfully")
            self._initialized = True

        except ccxt.AuthenticationError as e:
            self._handle_error(e, "initialize - authentication failed")
        except ccxt.NetworkError as e:
            self._handle_error(e, "initialize - network error")
        except Exception as e:
            self._handle_error(e, "initialize")

    async def _rate_limit(self) -> None:
        """Apply rate limiting between requests"""
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self.RATE_LIMIT:
            await asyncio.sleep(self.RATE_LIMIT - time_since_last)

        self._last_request_time = asyncio.get_event_loop().time()

    @cached(ttl=60)
    async def get_balances(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch current account balances for tracked assets with breakdown.

        Returns:
            Dictionary mapping asset symbols to balance details
            Example: {
                "USDT": {"free": 25000.0, "locked": 5000.0, "total": 30000.0},
                "ALKIMI": {"free": 750000.0, "locked": 50000.0, "total": 800000.0}
            }

        Raises:
            ExchangeConnectionError: If connection fails
            ExchangeAuthError: If authentication fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            if self.mock_mode:
                logger.debug("Fetching KuCoin balances (mock mode)")
                return get_mock_balances('kucoin')

            await self._rate_limit()

            # Fetch balance from KuCoin
            balance_response = await self.exchange.fetch_balance()

            # Extract tracked assets with detailed breakdown
            balances = {}
            for asset in settings.tracked_assets:
                free = float(balance_response.get('free', {}).get(asset, 0.0))
                used = float(balance_response.get('used', {}).get(asset, 0.0))
                total = float(balance_response.get('total', {}).get(asset, 0.0))

                balances[asset] = {
                    'free': free,
                    'locked': used,
                    'total': total
                }

            logger.info(f"KuCoin balances fetched: {balances}")
            return balances

        except ccxt.AuthenticationError as e:
            self._handle_error(e, "get_balances - authentication failed")
        except ccxt.NetworkError as e:
            self._handle_error(e, "get_balances - network error")
        except ccxt.RateLimitExceeded as e:
            self._handle_error(e, "get_balances - rate limit exceeded")
        except Exception as e:
            self._handle_error(e, "get_balances")

    @cached(ttl=60)
    async def get_trades(self, since: datetime) -> List[Trade]:
        """
        Fetch trade history since a specific datetime.

        Args:
            since: Fetch trades from this datetime onwards

        Returns:
            List of Trade objects sorted by timestamp (oldest first)

        Raises:
            ExchangeConnectionError: If connection fails
            ExchangeAuthError: If authentication fails
        """
        if not self._initialized:
            await self.initialize()

        try:
            if self.mock_mode:
                logger.debug(f"Fetching KuCoin trades since {since} (mock mode)")
                return get_cached_trades('kucoin', since)

            await self._rate_limit()

            all_trades = []
            since_timestamp = int(since.timestamp() * 1000)  # Convert to milliseconds

            # Fetch trades for each tracked asset
            for asset in settings.tracked_assets:
                # Try common trading pairs
                symbols_to_try = [
                    f"{asset}/USDT",
                    f"{asset}/USD",
                ]

                for symbol in symbols_to_try:
                    try:
                        # Paginate through all trades
                        current_since = since_timestamp
                        page_count = 0
                        max_pages = 20  # Safety limit to prevent infinite loops

                        while page_count < max_pages:
                            await self._rate_limit()

                            # Fetch trades for this symbol
                            trades = await self.exchange.fetch_my_trades(
                                symbol=symbol,
                                since=current_since,
                                limit=500
                            )

                            if not trades:
                                break  # No more trades

                            # Convert to Trade objects
                            for trade_data in trades:
                                trade = Trade(
                                    timestamp=datetime.fromtimestamp(trade_data['timestamp'] / 1000),
                                    symbol=asset,
                                    side=TradeSide.BUY if trade_data['side'] == 'buy' else TradeSide.SELL,
                                    amount=float(trade_data['amount']),
                                    price=float(trade_data['price']),
                                    fee=float(trade_data.get('fee', {}).get('cost', 0.0)),
                                    fee_currency=trade_data.get('fee', {}).get('currency', 'USDT'),
                                    trade_id=str(trade_data.get('id', ''))
                                )
                                all_trades.append(trade)

                            # Check if we got less than the limit (last page)
                            if len(trades) < 500:
                                break

                            # Update since to the timestamp of the last trade + 1ms for next page
                            last_timestamp = trades[-1]['timestamp']
                            current_since = int(last_timestamp) + 1
                            page_count += 1

                        if page_count > 0:
                            logger.debug(f"Fetched {len(all_trades)} trades across {page_count + 1} pages for {symbol}")

                        break  # If successful, no need to try other symbols

                    except ccxt.BadSymbol:
                        # Symbol not available, try next one
                        continue
                    except Exception as e:
                        logger.warning(f"Error fetching trades for {symbol}: {e}")
                        continue

            # Sort by timestamp
            all_trades.sort(key=lambda t: t.timestamp)

            logger.info(f"KuCoin trades fetched: {len(all_trades)} trades since {since}")
            return all_trades

        except ccxt.AuthenticationError as e:
            self._handle_error(e, "get_trades - authentication failed")
        except ccxt.NetworkError as e:
            self._handle_error(e, "get_trades - network error")
        except ccxt.RateLimitExceeded as e:
            self._handle_error(e, "get_trades - rate limit exceeded")
        except Exception as e:
            self._handle_error(e, "get_trades")

    async def get_deposits(self, since: datetime) -> List[Transaction]:
        """Fetch deposit history since a specific datetime"""
        if self.mock_mode:
            return []

        try:
            await self._rate_limit()

            all_deposits = []
            since_ts = int(since.timestamp() * 1000)

            for asset in settings.tracked_assets:
                try:
                    deposits = await self.exchange.fetch_deposits(
                        code=asset,
                        since=since_ts,
                        limit=500
                    )

                    for deposit in deposits:
                        if deposit.get('status') == 'ok':
                            all_deposits.append(Transaction(
                                timestamp=datetime.fromtimestamp(deposit['timestamp'] / 1000),
                                symbol=asset,
                                type='deposit',
                                amount=float(deposit['amount']),
                                fee=float(deposit.get('fee', {}).get('cost', 0.0)),
                                status=deposit['status'],
                                tx_id=deposit.get('txid'),
                                address=deposit.get('address'),
                                network=deposit.get('network')
                            ))

                except Exception as e:
                    logger.debug(f"Error fetching deposits for {asset}: {e}")
                    continue

            all_deposits.sort(key=lambda t: t.timestamp)
            logger.info(f"KuCoin deposits fetched: {len(all_deposits)} since {since}")
            return all_deposits

        except Exception as e:
            logger.error(f"Error fetching KuCoin deposits: {e}")
            return []

    async def get_withdrawals(self, since: datetime) -> List[Transaction]:
        """Fetch withdrawal history since a specific datetime"""
        if self.mock_mode:
            return []

        try:
            await self._rate_limit()

            all_withdrawals = []
            since_ts = int(since.timestamp() * 1000)

            for asset in settings.tracked_assets:
                try:
                    withdrawals = await self.exchange.fetch_withdrawals(
                        code=asset,
                        since=since_ts,
                        limit=500
                    )

                    for withdrawal in withdrawals:
                        if withdrawal.get('status') == 'ok':
                            all_withdrawals.append(Transaction(
                                timestamp=datetime.fromtimestamp(withdrawal['timestamp'] / 1000),
                                symbol=asset,
                                type='withdrawal',
                                amount=float(withdrawal['amount']),
                                fee=float(withdrawal.get('fee', {}).get('cost', 0.0)),
                                status=withdrawal['status'],
                                tx_id=withdrawal.get('txid'),
                                address=withdrawal.get('address'),
                                network=withdrawal.get('network')
                            ))

                except Exception as e:
                    logger.debug(f"Error fetching withdrawals for {asset}: {e}")
                    continue

            all_withdrawals.sort(key=lambda t: t.timestamp)
            logger.info(f"KuCoin withdrawals fetched: {len(all_withdrawals)} since {since}")
            return all_withdrawals

        except Exception as e:
            logger.error(f"Error fetching KuCoin withdrawals: {e}")
            return []

    @cached(ttl=60)
    async def get_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Fetch current USD prices for specified symbols.

        Args:
            symbols: List of asset symbols (e.g., ['USDT', 'ALKIMI'])

        Returns:
            Dictionary mapping symbols to USD prices
            Example: {"USDT": 1.0, "ALKIMI": 0.20}

        Raises:
            ExchangeConnectionError: If connection fails
        """
        if not self._initialized:
            await self.initialize()

        # Validate symbols
        self._validate_symbols(symbols, settings.tracked_assets)

        try:
            if self.mock_mode:
                logger.debug(f"Fetching KuCoin prices for {symbols} (mock mode)")
                return get_mock_prices(symbols)

            await self._rate_limit()

            prices = {}

            for symbol in symbols:
                if symbol == 'USDT':
                    # USDT is pegged to USD
                    prices[symbol] = 1.0
                    continue

                # Try different trading pairs to get USD price
                pairs_to_try = [
                    f"{symbol}/USDT",
                    f"{symbol}/USD",
                ]

                price_found = False
                for pair in pairs_to_try:
                    try:
                        ticker = await self.exchange.fetch_ticker(pair)
                        prices[symbol] = float(ticker['last'])
                        price_found = True
                        break
                    except ccxt.BadSymbol:
                        continue
                    except Exception as e:
                        logger.warning(f"Error fetching price for {pair}: {e}")
                        continue

                if not price_found:
                    logger.warning(f"Could not fetch price for {symbol} on KuCoin, using 0.0")
                    prices[symbol] = 0.0

            logger.info(f"KuCoin prices fetched: {prices}")
            return prices

        except ccxt.NetworkError as e:
            self._handle_error(e, "get_prices - network error")
        except ccxt.RateLimitExceeded as e:
            self._handle_error(e, "get_prices - rate limit exceeded")
        except Exception as e:
            self._handle_error(e, "get_prices")

    async def close(self) -> None:
        """
        Close exchange connection and cleanup resources.
        """
        try:
            if self.exchange:
                await self.exchange.close()
                logger.info("KuCoin client closed successfully")
        except Exception as e:
            logger.warning(f"Error closing KuCoin client: {e}")
        finally:
            self._initialized = False
            self.exchange = None
