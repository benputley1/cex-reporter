"""
Exchange Base Interface Module

Defines the abstract base class for all exchange implementations,
including data models for trades and error handling utilities.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import asyncio
import functools

# Import retry decorator and circuit breaker from utils
from src.utils.retry import retry_with_backoff
from src.utils.circuit_breaker import CircuitBreaker, CircuitBreakerConfig, CircuitBreakerOpenError


class TradeSide(Enum):
    """Enumeration for trade side"""
    BUY = "buy"
    SELL = "sell"


@dataclass
class Trade:
    """
    Data class representing a single trade transaction.

    Attributes:
        timestamp: When the trade occurred
        symbol: Asset symbol (e.g., 'USDT', 'ALKIMI')
        side: Trade direction (BUY or SELL)
        amount: Quantity traded
        price: Price per unit in USD
        fee: Transaction fee amount
        fee_currency: Currency of the fee (optional)
        trade_id: Unique identifier for the trade (optional)
        exchange: Exchange where trade occurred (optional)
    """
    timestamp: datetime
    symbol: str
    side: TradeSide
    amount: float
    price: float
    fee: float
    fee_currency: Optional[str] = None
    trade_id: Optional[str] = None
    exchange: Optional[str] = None

    def __post_init__(self):
        """Ensure side is TradeSide enum"""
        if isinstance(self.side, str):
            self.side = TradeSide(self.side.lower())

    def to_dict(self) -> Dict:
        """Convert trade to dictionary representation"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'side': self.side.value,
            'amount': self.amount,
            'price': self.price,
            'fee': self.fee,
            'fee_currency': self.fee_currency,
            'trade_id': self.trade_id,
            'exchange': self.exchange,
        }


@dataclass
class Transaction:
    """
    Data class representing a deposit or withdrawal transaction.

    Attributes:
        timestamp: When the transaction occurred
        symbol: Asset symbol (e.g., 'USDT', 'ALKIMI')
        type: Transaction type ('deposit' or 'withdrawal')
        amount: Quantity deposited or withdrawn
        fee: Transaction fee amount
        status: Transaction status ('ok', 'pending', 'failed', etc.)
        tx_id: Transaction ID/hash (optional)
        address: Deposit/withdrawal address (optional)
        network: Blockchain network used (optional)
    """
    timestamp: datetime
    symbol: str
    type: str  # 'deposit' or 'withdrawal'
    amount: float
    fee: float
    status: str
    tx_id: Optional[str] = None
    address: Optional[str] = None
    network: Optional[str] = None

    def to_dict(self) -> Dict:
        """Convert transaction to dictionary representation"""
        return {
            'timestamp': self.timestamp.isoformat(),
            'symbol': self.symbol,
            'type': self.type,
            'amount': self.amount,
            'fee': self.fee,
            'status': self.status,
            'tx_id': self.tx_id,
            'address': self.address,
            'network': self.network,
        }


class ExchangeError(Exception):
    """Base exception for exchange-related errors"""
    pass


class ExchangeConnectionError(ExchangeError):
    """Raised when connection to exchange fails"""
    pass


class ExchangeAuthError(ExchangeError):
    """Raised when authentication fails"""
    pass


class ExchangeRateLimitError(ExchangeError):
    """Raised when rate limit is exceeded"""
    pass


class ExchangeInterface(ABC):
    """
    Abstract base class defining the interface for all exchange implementations.

    All exchange adapters must implement this interface to ensure consistent
    behavior across different exchanges.
    """

    def __init__(self, exchange_name: str, config: Dict[str, str], mock_mode: bool = False, account_name: Optional[str] = None):
        """
        Initialize exchange interface.

        Args:
            exchange_name: Name of the exchange (e.g., 'mexc', 'kraken')
            config: Configuration dictionary with API keys
            mock_mode: If True, use mock data instead of real API calls
            account_name: Optional account identifier (e.g., 'MM1', 'TM1')
        """
        self.exchange_name = exchange_name
        self.account_name = account_name or 'MAIN'
        self.config = config
        self.mock_mode = mock_mode
        self._initialized = False

    @property
    def full_name(self) -> str:
        """Get the full exchange name including account identifier"""
        if self.account_name and self.account_name != 'MAIN':
            return f"{self.exchange_name}_{self.account_name.lower()}"
        return self.exchange_name

    @abstractmethod
    async def initialize(self) -> None:
        """
        Initialize the exchange connection.

        Should be called before any other methods. Performs setup like
        establishing connections, validating credentials, etc.

        Raises:
            ExchangeConnectionError: If connection fails
            ExchangeAuthError: If authentication fails
        """
        pass

    @abstractmethod
    async def get_balances(self) -> Dict[str, float]:
        """
        Fetch current account balances for all assets.

        Returns:
            Dictionary mapping asset symbols to amounts
            Example: {"USDT": 1000.0, "ALKIMI": 5000.0}

        Raises:
            ExchangeConnectionError: If connection fails
            ExchangeAuthError: If authentication fails
        """
        pass

    @abstractmethod
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
        pass

    @abstractmethod
    async def get_deposits(self, since: datetime) -> List['Transaction']:
        """
        Fetch deposit history since a specific datetime.

        Args:
            since: Fetch deposits from this datetime onwards

        Returns:
            List of Transaction objects sorted by timestamp (oldest first)

        Raises:
            ExchangeConnectionError: If connection fails
            ExchangeAuthError: If authentication fails
        """
        pass

    @abstractmethod
    async def get_withdrawals(self, since: datetime) -> List['Transaction']:
        """
        Fetch withdrawal history since a specific datetime.

        Args:
            since: Fetch withdrawals from this datetime onwards

        Returns:
            List of Transaction objects sorted by timestamp (oldest first)

        Raises:
            ExchangeConnectionError: If connection fails
            ExchangeAuthError: If authentication fails
        """
        pass

    @abstractmethod
    async def get_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Fetch current USD prices for specified symbols.

        Args:
            symbols: List of asset symbols (e.g., ['USDT', 'ALKIMI'])

        Returns:
            Dictionary mapping symbols to USD prices
            Example: {"USDT": 1.0, "ALKIMI": 0.0245}

        Raises:
            ExchangeConnectionError: If connection fails
        """
        pass

    @abstractmethod
    async def close(self) -> None:
        """
        Close exchange connection and cleanup resources.

        Should be called when done with the exchange to properly
        release connections and resources.
        """
        pass

    async def __aenter__(self):
        """Async context manager entry"""
        await self.initialize()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.close()

    def _validate_symbols(self, symbols: List[str], tracked_assets: List[str]) -> None:
        """
        Validate that requested symbols are in tracked assets.

        Args:
            symbols: Symbols to validate
            tracked_assets: List of allowed tracked assets

        Raises:
            ValueError: If any symbol is not in tracked assets
        """
        invalid_symbols = [s for s in symbols if s not in tracked_assets]
        if invalid_symbols:
            raise ValueError(
                f"Invalid symbols {invalid_symbols}. "
                f"Only tracking: {tracked_assets}"
            )

    def _handle_error(self, error: Exception, operation: str) -> None:
        """
        Centralized error handling for exchange operations.

        Args:
            error: The exception that occurred
            operation: Description of the operation that failed

        Raises:
            ExchangeConnectionError: For connection-related errors
            ExchangeAuthError: For authentication errors
            ExchangeRateLimitError: For rate limit errors
            ExchangeError: For other exchange errors
        """
        error_msg = f"{self.exchange_name} - {operation}: {str(error)}"

        # Map common error types
        error_str = str(error).lower()

        if any(term in error_str for term in ['connection', 'timeout', 'network', 'unreachable']):
            raise ExchangeConnectionError(error_msg) from error

        if any(term in error_str for term in ['auth', 'authentication', 'invalid key', 'permission']):
            raise ExchangeAuthError(error_msg) from error

        if any(term in error_str for term in ['rate limit', 'too many requests', 'throttle']):
            raise ExchangeRateLimitError(error_msg) from error

        # Generic exchange error
        raise ExchangeError(error_msg) from error

    def _generate_mock_balances(self) -> Dict[str, float]:
        """
        Generate mock balance data for testing.

        Returns:
            Dictionary of mock balances
        """
        import random
        return {
            'USDT': round(random.uniform(1000, 10000), 2),
            'ALKIMI': round(random.uniform(5000, 50000), 2),
        }

    def _generate_mock_trades(self, since: datetime) -> List[Trade]:
        """
        Generate mock trade data for testing.

        Args:
            since: Start datetime for mock trades

        Returns:
            List of mock Trade objects
        """
        import random
        from datetime import timedelta

        trades = []
        current_time = since
        num_trades = random.randint(5, 15)

        for i in range(num_trades):
            # Generate random time between trades
            current_time += timedelta(hours=random.uniform(1, 24))

            symbol = random.choice(['USDT', 'ALKIMI'])
            side = random.choice([TradeSide.BUY, TradeSide.SELL])

            if symbol == 'USDT':
                amount = round(random.uniform(100, 1000), 2)
                price = round(random.uniform(0.99, 1.01), 4)
            else:  # ALKIMI
                amount = round(random.uniform(1000, 10000), 2)
                price = round(random.uniform(0.02, 0.03), 4)

            trades.append(Trade(
                timestamp=current_time,
                symbol=symbol,
                side=side,
                amount=amount,
                price=price,
                fee=round(amount * price * 0.001, 4),  # 0.1% fee
                fee_currency='USDT',
                trade_id=f'mock_{self.exchange_name}_{i}',
                exchange=self.exchange_name
            ))

        return trades

    def _generate_mock_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Generate mock price data for testing.

        Args:
            symbols: List of symbols to generate prices for

        Returns:
            Dictionary of mock prices
        """
        import random

        mock_prices = {
            'USDT': 1.0,
            'ALKIMI': round(random.uniform(0.024, 0.026), 4),
        }

        return {symbol: mock_prices.get(symbol, 0.0) for symbol in symbols}


class CCXTExchangeClient(ExchangeInterface):
    """
    Base class for CCXT-based exchange clients.

    Provides common implementation for MEXC, Kraken, KuCoin, and Gate.io.
    Reduces code duplication by centralizing:
    - CCXT initialization
    - Rate limiting
    - Trade fetching with pagination
    - Balance fetching
    - Price fetching
    - Deposit/withdrawal fetching
    - Error handling
    - Retry logic (via decorator)
    - Logging
    """

    RATE_LIMIT = 1.0 / 20.0  # Default: 20 requests per second, override in subclass

    def __init__(
        self,
        exchange_name: str,
        ccxt_class,
        config: Dict[str, str],
        mock_mode: bool,
        account_name: Optional[str] = None,
        tracked_assets: Optional[List[str]] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize CCXT exchange client.

        Args:
            exchange_name: Exchange identifier (e.g., 'mexc', 'kraken')
            ccxt_class: CCXT exchange class (e.g., ccxt.mexc)
            config: API credentials dictionary
            mock_mode: Whether to use mock data
            account_name: Optional account identifier
            tracked_assets: List of asset symbols to track
            circuit_breaker_config: Optional circuit breaker configuration
        """
        super().__init__(exchange_name, config, mock_mode, account_name)
        self.ccxt_class = ccxt_class
        self.exchange = None
        self._last_request_time = 0
        self.tracked_assets = tracked_assets
        self._logger = None

        # Initialize circuit breaker for this exchange
        circuit_name = f"{exchange_name}_{account_name or 'main'}"
        self.circuit_breaker = CircuitBreaker(
            circuit_name,
            circuit_breaker_config or CircuitBreakerConfig()
        )

    @property
    def logger(self):
        """Lazy-loaded logger for the exchange client"""
        if self._logger is None:
            from src.utils.logging import get_logger
            self._logger = get_logger(f"{__name__}.{self.exchange_name}")
        return self._logger

    async def _rate_limit(self) -> None:
        """Apply rate limiting between requests"""
        import asyncio
        current_time = asyncio.get_event_loop().time()
        time_since_last = current_time - self._last_request_time

        if time_since_last < self.RATE_LIMIT:
            await asyncio.sleep(self.RATE_LIMIT - time_since_last)

        self._last_request_time = asyncio.get_event_loop().time()

    async def _execute_with_rate_limit(self, method: Callable, *args, **kwargs) -> Any:
        """
        Execute an API call with rate limiting and circuit breaker protection.

        Args:
            method: Async method to execute
            *args: Positional arguments for the method
            **kwargs: Keyword arguments for the method

        Returns:
            Result of the method execution

        Raises:
            ExchangeError: On execution failure
            CircuitBreakerOpenError: If circuit breaker is open
        """
        # Wrap the method execution with circuit breaker
        async def execute():
            await self._rate_limit()
            try:
                return await method(*args, **kwargs)
            except Exception as e:
                self._handle_ccxt_error(e, method.__name__)

        # Execute through circuit breaker
        return await self.circuit_breaker.call(execute)

    def _handle_ccxt_error(self, error: Exception, operation: str = "operation") -> None:
        """
        Standardized CCXT error handling with detailed error mapping.

        Maps CCXT-specific exceptions to our custom exception types.

        Args:
            error: The exception that occurred
            operation: Description of the operation that failed

        Raises:
            ExchangeConnectionError: For connection-related errors
            ExchangeAuthError: For authentication errors
            ExchangeRateLimitError: For rate limit errors
            ExchangeError: For other exchange errors
        """
        import ccxt.async_support as ccxt

        error_msg = f"{self.exchange_name.title()} - {operation}: {str(error)}"

        # Map CCXT-specific exceptions first
        if isinstance(error, ccxt.AuthenticationError):
            raise ExchangeAuthError(error_msg) from error
        elif isinstance(error, ccxt.RateLimitExceeded):
            raise ExchangeRateLimitError(error_msg) from error
        elif isinstance(error, ccxt.NetworkError):
            raise ExchangeConnectionError(error_msg) from error
        elif isinstance(error, ccxt.ExchangeNotAvailable):
            raise ExchangeConnectionError(error_msg) from error
        elif isinstance(error, ccxt.RequestTimeout):
            raise ExchangeConnectionError(error_msg) from error
        elif isinstance(error, ccxt.DDoSProtection):
            raise ExchangeRateLimitError(error_msg) from error

        # Fall back to base class error handling for non-CCXT errors
        self._handle_error(error, operation)

    async def _paginate(
        self,
        fetch_method: Callable,
        params: Optional[Dict] = None,
        max_pages: int = 20,
        limit_per_page: int = 500,
        since: Optional[int] = None
    ) -> List[Any]:
        """
        Generic pagination utility for fetching multiple pages of data.

        Args:
            fetch_method: Async method to call for fetching data (should support since/limit)
            params: Additional parameters to pass to the fetch method
            max_pages: Maximum number of pages to fetch (prevents infinite loops)
            limit_per_page: Number of items to fetch per page
            since: Optional timestamp to start fetching from (milliseconds)

        Returns:
            List of all fetched items across all pages

        Example:
            results = await self._paginate(
                self.exchange.fetch_my_trades,
                params={'symbol': 'BTC/USDT'},
                max_pages=10,
                since=since_timestamp
            )
        """
        all_items = []
        current_since = since
        page_count = 0
        params = params or {}

        while page_count < max_pages:
            await self._rate_limit()

            # Prepare request parameters
            request_params = {
                **params,
                'limit': limit_per_page
            }
            if current_since is not None:
                request_params['since'] = current_since

            try:
                items = await fetch_method(**request_params)

                if not items:
                    break

                all_items.extend(items)

                # Check if we received fewer items than requested (last page)
                if len(items) < limit_per_page:
                    break

                # Update since timestamp for next page
                # Assumes items have 'timestamp' field
                if hasattr(items[-1], 'timestamp'):
                    current_since = items[-1].timestamp + 1
                elif isinstance(items[-1], dict) and 'timestamp' in items[-1]:
                    current_since = items[-1]['timestamp'] + 1
                else:
                    # Can't determine next page start, stop pagination
                    break

                page_count += 1

            except Exception as e:
                self.logger.warning(f"Error during pagination on page {page_count + 1}: {e}")
                break

        return all_items

    def _get_ccxt_config(self) -> Dict:
        """
        Get CCXT configuration dictionary. Override in subclass if needed.

        Returns:
            Configuration dictionary for CCXT
        """
        config = {
            'apiKey': self.config.get('apiKey'),
            'secret': self.config.get('secret'),
            'enableRateLimit': True,
            'options': {
                'defaultType': 'spot',
            }
        }

        # Add password/passphrase if present (needed for KuCoin)
        if 'password' in self.config:
            config['password'] = self.config['password']

        return config

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    async def initialize(self) -> None:
        """Initialize CCXT exchange connection"""
        if self._initialized:
            self.logger.debug(f"{self.exchange_name.title()} client already initialized")
            return

        try:
            if self.mock_mode:
                self.logger.info(f"{self.exchange_name.title()} client ({self.account_name}) initialized in MOCK mode")
                self._initialized = True
                return

            # Initialize CCXT exchange
            self.exchange = self.ccxt_class(self._get_ccxt_config())

            # Test connection by fetching markets
            await self.exchange.load_markets()

            self.logger.info(f"{self.exchange_name.title()} client initialized successfully")
            self._initialized = True

        except Exception as e:
            self._handle_ccxt_error(e, "initialize")

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    async def get_balances(self) -> Dict[str, Dict[str, float]]:
        """
        Fetch current account balances for tracked assets with breakdown.

        Returns:
            Dictionary mapping asset symbols to balance details

        Raises:
            CircuitBreakerOpenError: If circuit breaker is open
        """
        if not self._initialized:
            await self.initialize()

        try:
            if self.mock_mode:
                from src.utils.mock_data import get_mock_balances
                self.logger.debug(f"Fetching {self.exchange_name.title()} balances (mock mode)")
                return get_mock_balances(self.exchange_name)

            # Wrap API call with circuit breaker
            async def fetch_balance_data():
                await self._rate_limit()
                return await self.exchange.fetch_balance()

            # Fetch balance from exchange through circuit breaker
            balance_response = await self.circuit_breaker.call(fetch_balance_data)

            # Extract tracked assets with detailed breakdown
            balances = {}
            for asset in self.tracked_assets:
                # Map to exchange-specific symbol if needed
                exchange_asset = self._map_asset_symbol(asset)

                free = float(balance_response.get('free', {}).get(exchange_asset, 0.0))
                used = float(balance_response.get('used', {}).get(exchange_asset, 0.0))
                total = float(balance_response.get('total', {}).get(exchange_asset, 0.0))

                balances[asset] = {
                    'free': free,
                    'locked': used,
                    'total': total
                }

            self.logger.info(f"{self.exchange_name.title()} balances fetched: {balances}")
            return balances

        except Exception as e:
            self._handle_ccxt_error(e, "get_balances")

    @retry_with_backoff(max_retries=3, initial_delay=2.0)
    async def get_trades(self, since: datetime) -> List[Trade]:
        """
        Fetch trade history since a specific datetime.

        Args:
            since: Fetch trades from this datetime onwards

        Returns:
            List of Trade objects sorted by timestamp
        """
        if not self._initialized:
            await self.initialize()

        try:
            if self.mock_mode:
                from src.utils.mock_data import get_cached_trades
                self.logger.debug(f"Fetching {self.exchange_name.title()} trades since {since} (mock mode)")
                return get_cached_trades(self.exchange_name, since)

            await self._rate_limit()

            all_trades = []
            since_timestamp = int(since.timestamp() * 1000)

            # Fetch trades for each tracked asset
            for asset in self.tracked_assets:
                symbols_to_try = self._get_trading_pairs(asset)

                for symbol in symbols_to_try:
                    try:
                        # Paginate through all trades
                        current_since = since_timestamp
                        page_count = 0
                        max_pages = 20

                        while page_count < max_pages:
                            await self._rate_limit()

                            trades = await self.exchange.fetch_my_trades(
                                symbol=symbol,
                                since=current_since,
                                limit=500
                            )

                            if not trades:
                                break

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

                            if len(trades) < 500:
                                break

                            last_timestamp = trades[-1]['timestamp']
                            current_since = int(last_timestamp) + 1
                            page_count += 1

                        break  # Success, no need to try other symbols

                    except Exception as e:
                        import ccxt.async_support as ccxt
                        if isinstance(e, ccxt.BadSymbol):
                            continue
                        self.logger.warning(f"Error fetching trades for {symbol}: {e}")
                        continue

            all_trades.sort(key=lambda t: t.timestamp)

            self.logger.info(f"{self.exchange_name.title()} trades fetched: {len(all_trades)} trades since {since}")
            return all_trades

        except Exception as e:
            self._handle_ccxt_error(e, "get_trades")

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    async def get_deposits(self, since: datetime) -> List[Transaction]:
        """Fetch deposit history since a specific datetime"""
        if self.mock_mode:
            return []

        try:
            await self._rate_limit()

            all_deposits = []
            since_ts = int(since.timestamp() * 1000)

            for asset in self.tracked_assets:
                exchange_asset = self._map_asset_symbol(asset)

                try:
                    deposits = await self.exchange.fetch_deposits(
                        code=exchange_asset,
                        since=since_ts,
                        limit=500
                    )

                    for deposit in deposits:
                        status = deposit.get('status', 'unknown')
                        if status in ['ok', 'complete', 'completed', 'success', 'finished']:
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
                    self.logger.debug(f"Error fetching deposits for {exchange_asset}: {e}")
                    continue

            all_deposits.sort(key=lambda t: t.timestamp)
            self.logger.info(f"{self.exchange_name.title()} deposits fetched: {len(all_deposits)} since {since}")
            return all_deposits

        except Exception as e:
            self.logger.error(f"Error fetching {self.exchange_name.title()} deposits: {e}")
            return []

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    async def get_withdrawals(self, since: datetime) -> List[Transaction]:
        """Fetch withdrawal history since a specific datetime"""
        if self.mock_mode:
            return []

        try:
            await self._rate_limit()

            all_withdrawals = []
            since_ts = int(since.timestamp() * 1000)

            for asset in self.tracked_assets:
                exchange_asset = self._map_asset_symbol(asset)

                try:
                    withdrawals = await self.exchange.fetch_withdrawals(
                        code=exchange_asset,
                        since=since_ts,
                        limit=500
                    )

                    for withdrawal in withdrawals:
                        status = withdrawal.get('status', 'unknown')
                        if status in ['ok', 'complete', 'completed', 'success', 'finished']:
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
                    self.logger.debug(f"Error fetching withdrawals for {exchange_asset}: {e}")
                    continue

            all_withdrawals.sort(key=lambda t: t.timestamp)
            self.logger.info(f"{self.exchange_name.title()} withdrawals fetched: {len(all_withdrawals)} since {since}")
            return all_withdrawals

        except Exception as e:
            self.logger.error(f"Error fetching {self.exchange_name.title()} withdrawals: {e}")
            return []

    @retry_with_backoff(max_retries=3, initial_delay=1.0)
    async def get_prices(self, symbols: List[str]) -> Dict[str, float]:
        """
        Fetch current USD prices for specified symbols.

        Args:
            symbols: List of asset symbols

        Returns:
            Dictionary mapping symbols to USD prices
        """
        if not self._initialized:
            await self.initialize()

        self._validate_symbols(symbols, self.tracked_assets)

        try:
            if self.mock_mode:
                from src.utils.mock_data import get_mock_prices
                self.logger.debug(f"Fetching {self.exchange_name.title()} prices for {symbols} (mock mode)")
                return get_mock_prices(symbols)

            await self._rate_limit()

            prices = {}

            for symbol in symbols:
                if symbol == 'USDT':
                    prices[symbol] = 1.0
                    continue

                # Check if symbol is available on this exchange
                if not self._is_symbol_available(symbol):
                    prices[symbol] = 0.0
                    continue

                pairs_to_try = self._get_price_pairs(symbol)

                price_found = False
                for pair in pairs_to_try:
                    try:
                        ticker = await self.exchange.fetch_ticker(pair)
                        prices[symbol] = float(ticker['last'])
                        price_found = True
                        break
                    except:
                        continue

                if not price_found:
                    self.logger.warning(f"Could not fetch price for {symbol} on {self.exchange_name.title()}, using 0.0")
                    prices[symbol] = 0.0

            self.logger.info(f"{self.exchange_name.title()} prices fetched: {prices}")
            return prices

        except Exception as e:
            self._handle_ccxt_error(e, "get_prices")

    async def close(self) -> None:
        """Close exchange connection and cleanup resources"""
        try:
            if self.exchange:
                await self.exchange.close()
                self.logger.info(f"{self.exchange_name.title()} client closed successfully")
        except Exception as e:
            self.logger.warning(f"Error closing {self.exchange_name.title()} client: {e}")
        finally:
            self._initialized = False
            self.exchange = None

    def get_circuit_status(self) -> Dict[str, Any]:
        """
        Get current circuit breaker status for this exchange.

        Returns:
            Dictionary with circuit breaker state and statistics
        """
        return self.circuit_breaker.get_status()

    def reset_circuit(self):
        """
        Manually reset the circuit breaker to CLOSED state.

        Use this if you know the exchange has recovered and want to
        force the circuit back to normal operation.
        """
        self.circuit_breaker.reset()
        self.logger.info(f"{self.exchange_name.title()} circuit breaker manually reset")

    # Methods to override in subclasses

    def _map_asset_symbol(self, asset: str) -> str:
        """
        Map standard asset symbol to exchange-specific symbol.
        Override in subclass if needed (e.g., Kraken uses 'USD' instead of 'USDT').

        Args:
            asset: Standard asset symbol

        Returns:
            Exchange-specific asset symbol
        """
        return asset

    def _get_trading_pairs(self, asset: str) -> List[str]:
        """
        Get list of trading pairs to try for an asset.
        Override in subclass if needed.

        Args:
            asset: Asset symbol

        Returns:
            List of trading pair strings to try
        """
        return [f"{asset}/USDT", f"{asset}/USD"]

    def _get_price_pairs(self, symbol: str) -> List[str]:
        """
        Get list of price pairs to try for a symbol.
        Override in subclass if needed.

        Args:
            symbol: Asset symbol

        Returns:
            List of price pair strings to try
        """
        return [f"{symbol}/USDT", f"{symbol}/USD"]

    def _is_symbol_available(self, symbol: str) -> bool:
        """
        Check if symbol is available on this exchange.
        Override in subclass if needed (e.g., ALKIMI not on Kraken).

        Args:
            symbol: Asset symbol

        Returns:
            True if available, False otherwise
        """
        return True
