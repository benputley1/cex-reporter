"""
Query Router Module for ALKIMI Slack Bot

This module classifies user queries into different intents and extracts relevant parameters
for routing to appropriate handlers.
"""

from enum import Enum
from typing import Dict, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
import re
import logging

logger = logging.getLogger(__name__)


class QueryIntent(Enum):
    """Enumeration of possible query intents."""
    PNL_QUERY = "pnl_query"           # "What's our P&L this month?"
    TRADE_QUERY = "trade_query"       # "Show trades over $5K"
    BALANCE_QUERY = "balance_query"   # "Current holdings?"
    PRICE_QUERY = "price_query"       # "ALKIMI price on Cetus?"
    ANALYTICS_QUERY = "analytics"     # "Best performing venue?"
    SQL_QUERY = "sql_query"           # "SELECT ... FROM trades"
    PYTHON_FUNCTION = "python"        # "Create a function..."
    RUN_FUNCTION = "run_function"     # "/alkimi run whale_detector"
    HISTORY = "history"               # "/alkimi history"
    HELP = "help"                     # "/alkimi help"
    CONFIG = "config"                 # "/alkimi pnl-config"
    OTC = "otc"                       # "/alkimi otc add/list/remove"
    UNKNOWN = "unknown"


@dataclass
class QueryParams:
    """Extracted parameters from user query."""
    intent: QueryIntent
    raw_query: str
    time_range: Optional[Tuple[datetime, datetime]] = None
    exchange: Optional[str] = None
    account: Optional[str] = None
    amount_threshold: Optional[float] = None
    function_name: Optional[str] = None
    function_args: Optional[Dict] = None
    sql: Optional[str] = None
    config_key: Optional[str] = None
    config_value: Optional[str] = None


class QueryRouter:
    """Route user queries to appropriate handlers based on intent classification."""

    def __init__(self):
        """Initialize the query router with keyword patterns."""
        # Define keyword patterns for each intent (ordered by priority)
        self.intent_patterns = {
            QueryIntent.SQL_QUERY: [
                r'^\s*SELECT\s+',  # Starts with SELECT
            ],
            QueryIntent.HELP: [
                r'\bhelp\b',
                r'\bcommands?\b',
                r'what can you do',
                r'how do i',
                r'show me commands',
            ],
            QueryIntent.HISTORY: [
                r'\bhistory\b',
                r'recent queries',
                r'past queries',
                r'previous queries',
                r'query history',
            ],
            QueryIntent.CONFIG: [
                r'\bconfig\b',
                r'\bsettings?\b',
                r'cost basis',
                r'\bfifo\b',
                r'\blifo\b',
                r'pnl-config',
                r'configure',
            ],
            QueryIntent.OTC: [
                r'\botc\b',
                r'over.?the.?counter',
            ],
            QueryIntent.PYTHON_FUNCTION: [
                r'create\s+(?:a\s+)?function',
                r'make\s+(?:a\s+)?function',
                r'new\s+function',
                r'define\s+(?:a\s+)?function',
                r'write\s+(?:a\s+)?function',
            ],
            QueryIntent.RUN_FUNCTION: [
                r'^\s*run\s+\w+',  # Starts with "run" followed by function name
                r'execute\s+\w+',
            ],
            QueryIntent.PNL_QUERY: [
                r'\bp\s*&\s*l\b',
                r'\bpnl\b',
                r'\bprofit\b',
                r'\bloss(?:es)?\b',
                r'\bearnings?\b',
                r'\brevenue\b',
                r'\bgains?\b',
                r'how much (?:did we|have we) (?:made|lost|earned)',
            ],
            QueryIntent.BALANCE_QUERY: [
                r'\bbalances?\b',
                r'\bholdings?\b',
                r'\bpositions?\b',
                r'what do we have',
                r'current (?:balance|holdings?|position)',
                r'show me (?:our )?(?:balance|holdings?|position)',
            ],
            QueryIntent.PRICE_QUERY: [
                r'\bprices?\b',
                r'\brates?\b',
                r'\bworth\b',
                r'how much is',
                r'what.*(?:trading|selling|buying)\s+(?:at|for)',
                r'current price',
            ],
            QueryIntent.ANALYTICS_QUERY: [
                r'\bbest\b',
                r'\bworst\b',
                r'\bcompare\b',
                r'\bperformance\b',
                r'\bvenues?\b',
                r'top performing',
                r'most profitable',
                r'least profitable',
                r'which (?:exchange|venue)',
            ],
            QueryIntent.TRADE_QUERY: [
                r'\btrades?\b',
                r'\btransactions?\b',
                r'show me',
                r'\blist\b',
                r'recent trades',
                r'trade history',
                r'over \$?\d+',
                r'above \$?\d+',
            ],
        }

        # Exchange name patterns
        self.exchange_patterns = [
            r'\b(binance|kraken|coinbase|kucoin|cetus|raydium|orca|meteora)\b',
        ]

        # Amount threshold patterns
        self.amount_patterns = [
            r'over\s+\$?(\d+(?:,\d{3})*(?:\.\d+)?)\s*k?',
            r'above\s+\$?(\d+(?:,\d{3})*(?:\.\d+)?)\s*k?',
            r'greater\s+than\s+\$?(\d+(?:,\d{3})*(?:\.\d+)?)\s*k?',
            r'>\s*\$?(\d+(?:,\d{3})*(?:\.\d+)?)\s*k?',
        ]

    def classify(self, query: str) -> QueryIntent:
        """
        Classify query intent using keyword matching.

        Args:
            query: The user's query string

        Returns:
            The classified QueryIntent
        """
        query_lower = query.lower().strip()

        # Check patterns in priority order
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query_lower, re.IGNORECASE):
                    logger.info(f"Classified query as {intent.value} using pattern: {pattern}")
                    return intent

        # Default to UNKNOWN if no match
        logger.warning(f"Could not classify query: {query[:50]}...")
        return QueryIntent.UNKNOWN

    def extract_parameters(self, query: str, intent: QueryIntent) -> QueryParams:
        """
        Extract relevant parameters based on intent.

        Args:
            query: The user's query string
            intent: The classified intent

        Returns:
            QueryParams object with extracted parameters
        """
        params = QueryParams(intent=intent, raw_query=query)

        try:
            # Extract common parameters
            params.time_range = self.parse_time_range(query)
            params.exchange = self._extract_exchange(query)
            params.amount_threshold = self._extract_amount_threshold(query)

            # Intent-specific extraction
            if intent == QueryIntent.SQL_QUERY:
                params.sql = self._extract_sql(query)

            elif intent == QueryIntent.RUN_FUNCTION:
                is_func, func_name, func_args = self.is_function_call(query)
                if is_func:
                    params.function_name = func_name
                    params.function_args = func_args

            elif intent == QueryIntent.CONFIG:
                params.config_key, params.config_value = self._extract_config(query)

            elif intent == QueryIntent.TRADE_QUERY:
                # Already extracted exchange and amount_threshold above
                params.account = self._extract_account(query)

        except Exception as e:
            logger.error(f"Error extracting parameters: {e}", exc_info=True)

        return params

    def parse_time_range(self, query: str) -> Optional[Tuple[datetime, datetime]]:
        """
        Parse time expressions from the query.

        Supports:
        - "today" -> (start of today, now)
        - "yesterday" -> (start of yesterday, end of yesterday)
        - "this week" -> (start of week, now)
        - "this month" -> (start of month, now)
        - "last 7 days" -> (7 days ago, now)
        - "2025-11-01 to 2025-11-30" -> (date1, date2)

        Args:
            query: The user's query string

        Returns:
            Tuple of (start_datetime, end_datetime) or None
        """
        query_lower = query.lower()
        now = datetime.now()

        # Today
        if re.search(r'\btoday\b', query_lower):
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            return (start, now)

        # Yesterday
        if re.search(r'\byesterday\b', query_lower):
            yesterday = now - timedelta(days=1)
            start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
            return (start, end)

        # This week
        if re.search(r'\bthis\s+week\b', query_lower):
            # Start of week (Monday)
            days_since_monday = now.weekday()
            start = (now - timedelta(days=days_since_monday)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return (start, now)

        # Last week
        if re.search(r'\blast\s+week\b', query_lower):
            days_since_monday = now.weekday()
            this_monday = now - timedelta(days=days_since_monday)
            start = (this_monday - timedelta(days=7)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            end = (this_monday - timedelta(seconds=1))
            return (start, end)

        # This month
        if re.search(r'\bthis\s+month\b', query_lower):
            start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return (start, now)

        # Last month
        if re.search(r'\blast\s+month\b', query_lower):
            first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            end = first_of_this_month - timedelta(seconds=1)
            start = end.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            return (start, end)

        # Last N days
        match = re.search(r'\blast\s+(\d+)\s+days?\b', query_lower)
        if match:
            days = int(match.group(1))
            start = (now - timedelta(days=days)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            return (start, now)

        # Specific date range (YYYY-MM-DD to YYYY-MM-DD)
        match = re.search(
            r'(\d{4}-\d{2}-\d{2})\s+to\s+(\d{4}-\d{2}-\d{2})',
            query_lower
        )
        if match:
            try:
                start = datetime.strptime(match.group(1), '%Y-%m-%d')
                end = datetime.strptime(match.group(2), '%Y-%m-%d').replace(
                    hour=23, minute=59, second=59, microsecond=999999
                )
                return (start, end)
            except ValueError as e:
                logger.error(f"Error parsing date range: {e}")

        # Specific date range (MM/DD/YYYY to MM/DD/YYYY)
        match = re.search(
            r'(\d{1,2}/\d{1,2}/\d{4})\s+to\s+(\d{1,2}/\d{1,2}/\d{4})',
            query_lower
        )
        if match:
            try:
                start = datetime.strptime(match.group(1), '%m/%d/%Y')
                end = datetime.strptime(match.group(2), '%m/%d/%Y').replace(
                    hour=23, minute=59, second=59, microsecond=999999
                )
                return (start, end)
            except ValueError as e:
                logger.error(f"Error parsing date range: {e}")

        # Single date (YYYY-MM-DD)
        match = re.search(r'\b(\d{4}-\d{2}-\d{2})\b', query_lower)
        if match:
            try:
                date = datetime.strptime(match.group(1), '%Y-%m-%d')
                start = date.replace(hour=0, minute=0, second=0, microsecond=0)
                end = date.replace(hour=23, minute=59, second=59, microsecond=999999)
                return (start, end)
            except ValueError as e:
                logger.error(f"Error parsing date: {e}")

        return None

    def is_sql_query(self, query: str) -> bool:
        """
        Check if query starts with SELECT (case insensitive).

        Args:
            query: The user's query string

        Returns:
            True if query is a SQL SELECT statement
        """
        return bool(re.match(r'^\s*SELECT\s+', query, re.IGNORECASE))

    def is_function_call(self, query: str) -> Tuple[bool, Optional[str], Optional[Dict]]:
        """
        Check if query is a function call like:
        - "run whale_detector threshold=50000"
        - "execute profit_analyzer period=monthly"

        Args:
            query: The user's query string

        Returns:
            Tuple of (is_function, function_name, args_dict)
        """
        # Match "run function_name" or "execute function_name"
        match = re.match(
            r'^\s*(?:run|execute)\s+(\w+)(?:\s+(.+))?',
            query.strip(),
            re.IGNORECASE
        )

        if not match:
            return (False, None, None)

        function_name = match.group(1)
        args_string = match.group(2)

        # Parse arguments if present
        args_dict = {}
        if args_string:
            # Parse key=value pairs
            arg_matches = re.findall(r'(\w+)=([^\s]+)', args_string)
            for key, value in arg_matches:
                # Try to convert to appropriate type
                args_dict[key] = self._parse_value(value)

        return (True, function_name, args_dict)

    def _extract_exchange(self, query: str) -> Optional[str]:
        """Extract exchange name from query."""
        query_lower = query.lower()
        for pattern in self.exchange_patterns:
            match = re.search(pattern, query_lower)
            if match:
                return match.group(1).upper()
        return None

    def _extract_amount_threshold(self, query: str) -> Optional[float]:
        """Extract amount threshold from query."""
        for pattern in self.amount_patterns:
            match = re.search(pattern, query, re.IGNORECASE)
            if match:
                amount_str = match.group(1).replace(',', '')
                try:
                    amount = float(amount_str)
                    # Check if 'k' suffix (thousands)
                    if 'k' in query[match.end():match.end()+1].lower():
                        amount *= 1000
                    return amount
                except ValueError:
                    logger.error(f"Could not parse amount: {amount_str}")
        return None

    def _extract_account(self, query: str) -> Optional[str]:
        """Extract account/wallet address from query."""
        # Look for common account patterns
        patterns = [
            r'\baccount\s+(\w+)',
            r'\bwallet\s+(\w+)',
            r'\baddress\s+(\w+)',
        ]

        query_lower = query.lower()
        for pattern in patterns:
            match = re.search(pattern, query_lower)
            if match:
                return match.group(1)
        return None

    def _extract_sql(self, query: str) -> Optional[str]:
        """Extract SQL statement from query."""
        # SQL query is typically the entire query
        # Remove any leading/trailing whitespace
        sql = query.strip()
        return sql if sql else None

    def _extract_config(self, query: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Extract configuration key and value from query.

        Examples:
        - "set cost basis to fifo"
        - "config method=lifo"
        - "pnl-config fifo"

        Returns:
            Tuple of (config_key, config_value)
        """
        query_lower = query.lower()

        # Pattern: "set X to Y" or "set X = Y"
        match = re.search(r'set\s+(\w+(?:\s+\w+)?)\s+(?:to|=)\s+(\w+)', query_lower)
        if match:
            return (match.group(1).replace(' ', '_'), match.group(2))

        # Pattern: "config key=value"
        match = re.search(r'config\s+(\w+)\s*=\s*(\w+)', query_lower)
        if match:
            return (match.group(1), match.group(2))

        # Pattern: "pnl-config method"
        match = re.search(r'pnl-config\s+(\w+)', query_lower)
        if match:
            return ('cost_basis_method', match.group(1))

        # Pattern: "fifo" or "lifo" alone
        if re.search(r'\b(fifo|lifo)\b', query_lower):
            match = re.search(r'\b(fifo|lifo)\b', query_lower)
            return ('cost_basis_method', match.group(1).upper())

        return (None, None)

    def _parse_value(self, value_str: str):
        """
        Parse a string value to its appropriate type.

        Args:
            value_str: String representation of a value

        Returns:
            Parsed value (int, float, bool, or str)
        """
        # Boolean
        if value_str.lower() in ('true', 'yes', 'on'):
            return True
        if value_str.lower() in ('false', 'no', 'off'):
            return False

        # Integer
        try:
            return int(value_str)
        except ValueError:
            pass

        # Float
        try:
            return float(value_str)
        except ValueError:
            pass

        # String (default)
        return value_str


def main():
    """Test the query router with sample queries."""
    router = QueryRouter()

    test_queries = [
        "What's our P&L this month?",
        "Show me trades over $5000 on Binance",
        "Current ALKIMI holdings?",
        "What's the price of ALKIMI on Cetus?",
        "SELECT * FROM trades WHERE amount > 10000",
        "run whale_detector threshold=50000",
        "Create a function to analyze profits",
        "/alkimi history",
        "/alkimi help",
        "Set cost basis to FIFO",
        "Best performing venue this week",
        "Show trades yesterday on Kraken",
        "P&L for last 7 days",
    ]

    print("Testing Query Router\n" + "="*50)

    for query in test_queries:
        print(f"\nQuery: {query}")
        intent = router.classify(query)
        params = router.extract_parameters(query, intent)

        print(f"Intent: {intent.value}")
        if params.time_range:
            print(f"Time Range: {params.time_range[0]} to {params.time_range[1]}")
        if params.exchange:
            print(f"Exchange: {params.exchange}")
        if params.amount_threshold:
            print(f"Amount Threshold: ${params.amount_threshold:,.2f}")
        if params.function_name:
            print(f"Function: {params.function_name}")
            if params.function_args:
                print(f"Arguments: {params.function_args}")
        if params.config_key:
            print(f"Config: {params.config_key} = {params.config_value}")
        print("-" * 50)


if __name__ == "__main__":
    main()
