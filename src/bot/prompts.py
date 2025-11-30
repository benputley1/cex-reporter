"""
LLM system prompts and templates for the ALKIMI Slack bot.

This module contains all prompts used with Claude API for:
1. SQL generation from natural language queries
2. Python function generation for complex analytics
3. Query answering with data context
4. Intent classification fallback
"""

import logging
from typing import Optional
import anthropic

logger = logging.getLogger(__name__)

# =============================================================================
# Database Schema for Context
# =============================================================================

TRADES_SCHEMA = """
Table: trades
Columns:
  - id: INTEGER PRIMARY KEY
  - trade_id: TEXT (unique exchange trade ID)
  - exchange: TEXT (mexc, kraken, kucoin, gateio, cetus, turbos, bluefin)
  - account_name: TEXT (MM1, MM2, MM3, TREASURY, etc.)
  - timestamp: TEXT (ISO format datetime)
  - symbol: TEXT (ALKIMI)
  - side: TEXT (buy or sell)
  - amount: REAL (quantity of ALKIMI)
  - price: REAL (USD price per ALKIMI)
  - fee: REAL (trading fee in USD)

Sample data:
| exchange | account_name | side | amount    | price   |
|----------|-------------|------|-----------|---------|
| mexc     | MM1         | sell | 50000.0   | 0.0275  |
| gateio   | MM2         | buy  | 25000.0   | 0.0268  |
| cetus    | DEX         | sell | 10000.0   | 0.0272  |

Indexes:
  - idx_timestamp: ON timestamp
  - idx_exchange: ON exchange
  - idx_account: ON account_name
  - idx_side: ON side
"""

# =============================================================================
# SQL Generation Prompt
# =============================================================================

SQL_GENERATION_PROMPT = """
You are a SQL expert for the ALKIMI trading database.

{schema}

Generate a safe SELECT query for this request: {query}

RULES:
1. Only generate SELECT statements (no INSERT, UPDATE, DELETE, DROP)
2. Always include LIMIT 100 at the end (unless user specifies a different limit)
3. No subqueries, CTEs, or UNION operations
4. No functions except: SUM, AVG, COUNT, MIN, MAX, strftime, date, datetime
5. For date filtering, use: strftime('%Y-%m-%d', timestamp) or date(timestamp)
6. For time ranges: timestamp >= datetime('now', '-N days')
7. Return ONLY the SQL query, no markdown formatting, no explanation
8. Column names are case-sensitive - use exact names from schema
9. For "today": WHERE date(timestamp) = date('now')
10. For "this week": WHERE timestamp >= datetime('now', '-7 days')
11. For "this month": WHERE timestamp >= datetime('now', 'start of month')

Example queries:
- "trades today" → SELECT * FROM trades WHERE date(timestamp) = date('now') LIMIT 100
- "total sold this week" → SELECT SUM(amount) as total FROM trades WHERE side='sell' AND timestamp >= datetime('now', '-7 days') LIMIT 100
- "volume by exchange" → SELECT exchange, SUM(amount*price) as volume FROM trades GROUP BY exchange ORDER BY volume DESC LIMIT 100
- "mexc buys last 24h" → SELECT * FROM trades WHERE exchange='mexc' AND side='buy' AND timestamp >= datetime('now', '-1 day') ORDER BY timestamp DESC LIMIT 100
- "average price per exchange" → SELECT exchange, AVG(price) as avg_price, COUNT(*) as trade_count FROM trades GROUP BY exchange LIMIT 100

Return only the SQL query, nothing else.
"""

# =============================================================================
# Python Function Generation Prompt
# =============================================================================

PYTHON_GENERATION_PROMPT = """
You are a Python expert creating analysis functions for ALKIMI trading data.

Available functions (already imported):
- load_trades() → pd.DataFrame with columns: timestamp, exchange, account_name, side, amount, price, fee
- load_balances() → Dict[str, Dict[str, float]] mapping exchange → {{asset: balance}}
- load_snapshots() → List[Dict] with daily balance snapshots

Available libraries (already imported):
- pd (pandas)
- np (numpy)
- datetime, timedelta
- math, statistics

Create a Python function for: {query}

RULES:
1. Define a function with a clear name and docstring
2. The function MUST assign its final result to a variable called `result`
3. No file I/O operations (open, read, write)
4. No network calls (requests, urllib, httpx)
5. No system calls (os.system, subprocess)
6. No exec, eval, compile, or __import__
7. Only use approved libraries listed above
8. Handle edge cases (empty dataframes, missing data)
9. Return meaningful data structures (DataFrame, dict, list, or scalar)
10. Include comments for complex logic
11. Return ONLY the function code, no markdown formatting, no explanation

Example:
Request: "Calculate rolling 7-day volume by exchange"

def rolling_7day_volume(days_back=7):
    \"\"\"Calculate rolling volume by exchange for the past N days.\"\"\"
    df = load_trades()

    # Convert timestamp to datetime
    df['timestamp'] = pd.to_datetime(df['timestamp'])

    # Filter to recent trades
    cutoff = datetime.now() - timedelta(days=days_back)
    recent = df[df['timestamp'] >= cutoff]

    if recent.empty:
        result = pd.DataFrame()
        return result

    # Calculate volume metrics by exchange
    result = recent.groupby('exchange').agg({{
        'amount': 'sum',
        'price': 'mean'
    }})
    result['volume_usd'] = result['amount'] * result['price']
    result = result.sort_values('volume_usd', ascending=False)

    return result

result = rolling_7day_volume()

Return only the Python function code, nothing else.
"""

# =============================================================================
# Query Answer Prompt
# =============================================================================

QUERY_ANSWER_PROMPT = """
You are an AI assistant for ALKIMI trading operations.

Current data context:
{context}

User question: {query}

Instructions:
1. Provide a concise, actionable answer based on the data context
2. Include specific numbers and metrics from the data
3. Format currency as $X,XXX.XX (e.g., $1,234.56)
4. Format large numbers with commas (e.g., 1,234,567)
5. If the data shows trends, mention them
6. If you cannot answer from the provided data, say so clearly
7. Keep the response under 500 words
8. Use bullet points for multiple data points
9. Be professional and focused on trading operations

Provide your answer:
"""

# =============================================================================
# Intent Classification Prompt
# =============================================================================

INTENT_CLASSIFICATION_PROMPT = """
Classify this trading query into one of these categories:

Categories:
- pnl_query: Questions about profit, loss, P&L, earnings, returns, gains
- trade_query: Questions about trades, transactions, buy/sell activity, order history
- balance_query: Questions about holdings, balances, positions, inventory
- price_query: Questions about current price, rates, market value
- analytics_query: Questions comparing venues, exchanges, best/worst performance, trends
- unknown: Cannot classify or unclear intent

Query: {query}

Respond with ONLY the category name (e.g., "pnl_query"), nothing else.
"""

# =============================================================================
# Prompt Builder Functions
# =============================================================================

def build_sql_prompt(query: str) -> str:
    """Build SQL generation prompt with schema context."""
    return SQL_GENERATION_PROMPT.format(
        schema=TRADES_SCHEMA,
        query=query
    )

def build_python_prompt(query: str) -> str:
    """Build Python function generation prompt."""
    return PYTHON_GENERATION_PROMPT.format(query=query)

def build_answer_prompt(query: str, context: str) -> str:
    """Build query answer prompt with data context."""
    return QUERY_ANSWER_PROMPT.format(
        context=context,
        query=query
    )

def build_intent_prompt(query: str) -> str:
    """Build intent classification prompt."""
    return INTENT_CLASSIFICATION_PROMPT.format(query=query)

# =============================================================================
# Claude API Client Wrapper
# =============================================================================

class ClaudeClient:
    """
    Wrapper for Claude API calls with error handling and logging.

    This client provides high-level methods for:
    - SQL query generation
    - Python function generation
    - Natural language query answering
    - Intent classification
    """

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        max_tokens: int = 4096,
        temperature: float = 0.0
    ):
        """
        Initialize Claude API client.

        Args:
            api_key: Anthropic API key
            model: Claude model to use (default: claude-sonnet-4-20250514)
            max_tokens: Maximum tokens in response (default: 4096)
            temperature: Sampling temperature 0.0-1.0 (default: 0.0 for deterministic)
        """
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        logger.info(f"Initialized ClaudeClient with model: {model}")

    async def _call_api(
        self,
        system_prompt: str,
        user_message: str,
        temperature: Optional[float] = None
    ) -> str:
        """
        Internal method to call Claude API with error handling.

        Args:
            system_prompt: System-level instructions
            user_message: User query or request
            temperature: Override default temperature if needed

        Returns:
            Claude's response text

        Raises:
            anthropic.APIError: If API call fails
        """
        try:
            temp = temperature if temperature is not None else self.temperature

            logger.debug(f"Calling Claude API with model: {self.model}")
            logger.debug(f"System prompt length: {len(system_prompt)}")
            logger.debug(f"User message: {user_message[:100]}...")

            message = self.client.messages.create(
                model=self.model,
                max_tokens=self.max_tokens,
                temperature=temp,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_message}
                ]
            )

            response_text = message.content[0].text
            logger.debug(f"Received response: {response_text[:200]}...")

            return response_text.strip()

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            raise
        except Exception as e:
            logger.error(f"Unexpected error calling Claude API: {e}")
            raise

    async def generate_sql(self, query: str) -> str:
        """
        Generate SQL query from natural language.

        Args:
            query: Natural language query (e.g., "show trades today")

        Returns:
            SQL SELECT statement

        Example:
            >>> client = ClaudeClient(api_key="...")
            >>> sql = await client.generate_sql("total volume this week")
            >>> print(sql)
            SELECT SUM(amount*price) as total_volume FROM trades
            WHERE timestamp >= datetime('now', '-7 days') LIMIT 100
        """
        logger.info(f"Generating SQL for query: {query}")

        prompt = build_sql_prompt(query)

        try:
            sql = await self._call_api(
                system_prompt="You are a SQL expert. Generate only valid SELECT queries.",
                user_message=prompt,
                temperature=0.0  # Deterministic for SQL generation
            )

            # Clean up response (remove markdown formatting if present)
            sql = sql.replace("```sql", "").replace("```", "").strip()

            # Basic validation
            sql_upper = sql.upper()
            if not sql_upper.startswith("SELECT"):
                raise ValueError(f"Generated query is not a SELECT statement: {sql}")

            # Check for dangerous keywords
            dangerous_keywords = ["DROP", "DELETE", "UPDATE", "INSERT", "ALTER", "TRUNCATE"]
            for keyword in dangerous_keywords:
                if keyword in sql_upper:
                    raise ValueError(f"Generated query contains forbidden keyword: {keyword}")

            logger.info(f"Generated SQL: {sql}")
            return sql

        except Exception as e:
            logger.error(f"Failed to generate SQL: {e}")
            raise

    async def generate_python(self, query: str) -> str:
        """
        Generate Python function from description.

        Args:
            query: Description of desired analysis

        Returns:
            Python function code as string

        Example:
            >>> client = ClaudeClient(api_key="...")
            >>> code = await client.generate_python("calculate average trade size by exchange")
            >>> print(code)
            def avg_trade_size_by_exchange():
                ...
                result = ...
        """
        logger.info(f"Generating Python for query: {query}")

        prompt = build_python_prompt(query)

        try:
            code = await self._call_api(
                system_prompt="You are a Python expert. Generate only safe, executable Python code.",
                user_message=prompt,
                temperature=0.0  # Deterministic for code generation
            )

            # Clean up response (remove markdown formatting if present)
            code = code.replace("```python", "").replace("```", "").strip()

            # Basic validation
            if "def " not in code:
                raise ValueError("Generated code does not contain a function definition")

            if "result" not in code:
                raise ValueError("Generated code does not assign to 'result' variable")

            # Check for dangerous operations
            dangerous_operations = ["open(", "exec(", "eval(", "__import__", "os.system", "subprocess"]
            for operation in dangerous_operations:
                if operation in code:
                    raise ValueError(f"Generated code contains forbidden operation: {operation}")

            logger.info(f"Generated Python function ({len(code)} chars)")
            logger.debug(f"Code preview: {code[:200]}...")
            return code

        except Exception as e:
            logger.error(f"Failed to generate Python: {e}")
            raise

    async def answer_query(self, query: str, context: str) -> str:
        """
        Answer a query given data context.

        Args:
            query: User's question
            context: Relevant data context (SQL results, data summaries, etc.)

        Returns:
            Natural language answer

        Example:
            >>> client = ClaudeClient(api_key="...")
            >>> context = "Total trades: 150\\nTotal volume: $45,000\\nTop exchange: MEXC"
            >>> answer = await client.answer_query("what's our trading volume?", context)
            >>> print(answer)
            Based on the data, your total trading volume is $45,000 across 150 trades...
        """
        logger.info(f"Answering query: {query}")
        logger.debug(f"Context length: {len(context)} chars")

        prompt = build_answer_prompt(query, context)

        try:
            answer = await self._call_api(
                system_prompt="You are a helpful AI assistant for ALKIMI trading operations.",
                user_message=prompt,
                temperature=0.3  # Slightly creative for natural answers
            )

            logger.info(f"Generated answer ({len(answer)} chars)")
            return answer

        except Exception as e:
            logger.error(f"Failed to answer query: {e}")
            raise

    async def classify_intent(self, query: str) -> str:
        """
        Classify query intent using LLM fallback.

        Args:
            query: User's query text

        Returns:
            Intent category: pnl_query, trade_query, balance_query,
                           price_query, analytics_query, or unknown

        Example:
            >>> client = ClaudeClient(api_key="...")
            >>> intent = await client.classify_intent("show me today's profit")
            >>> print(intent)
            pnl_query
        """
        logger.info(f"Classifying intent for: {query}")

        prompt = build_intent_prompt(query)

        try:
            intent = await self._call_api(
                system_prompt="You are an intent classification system. Respond with only the category name.",
                user_message=prompt,
                temperature=0.0  # Deterministic for classification
            )

            # Normalize response
            intent = intent.lower().strip()

            # Validate intent
            valid_intents = [
                "pnl_query",
                "trade_query",
                "balance_query",
                "price_query",
                "analytics_query",
                "unknown"
            ]

            if intent not in valid_intents:
                logger.warning(f"Invalid intent '{intent}', defaulting to 'unknown'")
                intent = "unknown"

            logger.info(f"Classified as: {intent}")
            return intent

        except Exception as e:
            logger.error(f"Failed to classify intent: {e}")
            return "unknown"

    def set_model(self, model: str) -> None:
        """Change the Claude model used for API calls."""
        logger.info(f"Changing model from {self.model} to {model}")
        self.model = model

    def set_temperature(self, temperature: float) -> None:
        """Change the default temperature for API calls."""
        if not 0.0 <= temperature <= 1.0:
            raise ValueError("Temperature must be between 0.0 and 1.0")
        logger.info(f"Changing temperature from {self.temperature} to {temperature}")
        self.temperature = temperature


# =============================================================================
# Convenience Functions
# =============================================================================

def create_claude_client(
    api_key: str,
    model: str = "claude-sonnet-4-20250514"
) -> ClaudeClient:
    """
    Create a configured Claude client instance.

    Args:
        api_key: Anthropic API key
        model: Claude model to use

    Returns:
        Configured ClaudeClient instance
    """
    return ClaudeClient(api_key=api_key, model=model)
