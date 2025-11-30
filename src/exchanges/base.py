"""
Exchange Base Interface Module

Defines the abstract base class for all exchange implementations,
including data models for trades and error handling utilities.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional
from enum import Enum


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
