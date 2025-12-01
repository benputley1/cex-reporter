"""
Conversational Agent for ALKIMI Slack Bot

LLM-first approach using Claude function calling for natural language interactions.
Replaces keyword-based routing with intelligent intent understanding.
"""

import os
import json
import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import time

import anthropic

from src.bot.data_provider import DataProvider
from src.bot.query_engine import QueryEngine
from src.bot.python_executor import SafePythonExecutor
from src.bot.function_store import FunctionStore
from src.bot.pnl_config import PnLConfig, OTCManager, PnLCalculator, CostBasisMethod
from src.utils import get_logger

logger = get_logger(__name__)

# Thread history TTL in seconds (30 minutes)
THREAD_HISTORY_TTL = 1800
MAX_HISTORY_MESSAGES = 10


# =============================================================================
# System Prompt
# =============================================================================

SYSTEM_PROMPT = """# ALKIMI Trading Analyst Bot

## Identity & Role

You are the ALKIMI Trading Analyst, a Slack bot that provides real-time market intelligence and trading analysis for the $ADS token. You serve the Alkimi team with direct, actionable insights on token performance, liquidity dynamics, and market conditions across both centralized and decentralized exchanges.

## Data Sources

You have access to the following data:

### CEX Data (Centralized Exchanges)
- ALKIMI trading pairs across listed exchanges (MEXC, Kraken, KuCoin, Gate.io)
- Trade history with timestamps, amounts, prices, and fees
- Balance snapshots across accounts
- P&L calculations with FIFO/LIFO/Average cost basis

### Sui DEX Data (Decentralized Exchanges)
- DEX trading volume across Cetus, Turbos, BlueMove, Aftermath, and other Sui DEXs
- Swap activity and trade flow analysis

### Database Schema
Table: trades - id, trade_id, exchange, account_name, timestamp, symbol, side (buy/sell), amount, price, fee
Table: otc_transactions - id, date, counterparty, alkimi_amount, usd_amount, price, side, notes

---

## Communication Style

- Direct and concise - Lead with the key insight, then provide supporting data
- Numbers first - Always include specific figures, percentages, and comparisons
- Action-oriented - When relevant, suggest potential implications or considerations
- No fluff - Skip pleasantries and unnecessary caveats in routine updates
- Do not use bold formatting (no **text**). Code blocks are OK for data tables. Bullet points are OK for lists.

---

## Response Guidelines

### When asked about current price/market status:
- Provide price from CoinGecko
- Include 24h change if available
- Flag unusual activity if present

### When asked about balances:
- Report balances across all exchanges/accounts
- Break down by asset type
- Note any significant changes from previous snapshots

### When asked about trading activity:
- Summarize volume distribution by exchange
- Identify notable trades or patterns
- Report buy/sell ratio and trade counts

### When asked for P&L:
- Present realized and unrealized P&L clearly
- Note the cost basis method being used
- Include period dates and trade counts
- Break down by exchange when relevant

### When asked for analysis:
- Present data objectively first
- Offer interpretation based on patterns
- Note any risks or considerations
- Be clear about data limitations

---

## Important Guidelines

- Always use the provided tools to fetch real data - NEVER fabricate information
- If data is unavailable, say so clearly
- Acknowledge data limitations or delays when relevant
- Do not provide financial advice or explicit trade recommendations
- Do not speculate on future price movements

---

## Tone Calibration

Match the urgency of the situation:
- **Routine queries:** Brief, factual, minimal commentary
- **Significant findings:** More detail, context, and potential implications

---

Today's date is: {current_date}

*Built for Alkimi. Reducing noise, surfacing signal.*
"""


# =============================================================================
# Tool Definitions
# =============================================================================

TOOLS = [
    # Core Data Tools
    {
        "name": "get_balances",
        "description": "Get current token balances across all exchanges and accounts. Returns the latest snapshot of holdings.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_trades",
        "description": "Query trade history with optional filters. Returns list of trades with timestamp, exchange, side, amount, price.",
        "input_schema": {
            "type": "object",
            "properties": {
                "since": {
                    "type": "string",
                    "description": "Start date/time. Accepts: 'today', 'yesterday', 'this week', 'this month', or ISO date (YYYY-MM-DD)"
                },
                "until": {
                    "type": "string",
                    "description": "End date/time. Accepts same formats as 'since'. Defaults to now."
                },
                "exchange": {
                    "type": "string",
                    "description": "Filter by exchange: mexc, kraken, kucoin, gateio"
                },
                "side": {
                    "type": "string",
                    "enum": ["buy", "sell"],
                    "description": "Filter by trade side"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of trades to return (default 20, max 100)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_trade_summary",
        "description": "Get aggregated trading statistics: total volume, trade counts, breakdown by exchange/account.",
        "input_schema": {
            "type": "object",
            "properties": {
                "since": {
                    "type": "string",
                    "description": "Start date/time for summary period"
                },
                "until": {
                    "type": "string",
                    "description": "End date/time for summary period"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_current_price",
        "description": "Get the current ALKIMI token price from CoinGecko.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_pnl_report",
        "description": "Calculate Profit & Loss report for a time period. Includes realized P&L from completed trades and unrealized P&L from current holdings.",
        "input_schema": {
            "type": "object",
            "properties": {
                "since": {
                    "type": "string",
                    "description": "Start date for P&L calculation (default: all time)"
                },
                "until": {
                    "type": "string",
                    "description": "End date for P&L calculation (default: now)"
                }
            },
            "required": []
        }
    },
    # SQL & Functions Tools
    {
        "name": "execute_sql",
        "description": "Run a read-only SQL query against the trades database. Only SELECT queries are allowed. Use for custom data analysis.",
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "SQL SELECT query to execute. Tables: trades, otc_transactions, query_history"
                }
            },
            "required": ["sql"]
        }
    },
    {
        "name": "list_saved_functions",
        "description": "List all saved Python analysis functions that users have created.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "run_saved_function",
        "description": "Execute a previously saved Python analysis function by name.",
        "input_schema": {
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Name of the saved function to run"
                }
            },
            "required": ["name"]
        }
    },
    # OTC & Config Tools
    {
        "name": "get_otc_transactions",
        "description": "List all OTC (over-the-counter) transactions.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "add_otc_transaction",
        "description": "Record a new OTC transaction. Requires date, amount, USD value, and side (buy/sell).",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "description": "Transaction date (YYYY-MM-DD)"
                },
                "alkimi_amount": {
                    "type": "number",
                    "description": "Amount of ALKIMI tokens"
                },
                "usd_amount": {
                    "type": "number",
                    "description": "USD value of the transaction"
                },
                "side": {
                    "type": "string",
                    "enum": ["buy", "sell"],
                    "description": "Whether this was a buy or sell"
                },
                "counterparty": {
                    "type": "string",
                    "description": "Name of the counterparty (optional)"
                },
                "notes": {
                    "type": "string",
                    "description": "Additional notes (optional)"
                }
            },
            "required": ["date", "alkimi_amount", "usd_amount", "side"]
        }
    },
    {
        "name": "get_pnl_config",
        "description": "Get current P&L calculation configuration including cost basis method.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "set_cost_basis_method",
        "description": "Set the cost basis calculation method for P&L reports.",
        "input_schema": {
            "type": "object",
            "properties": {
                "method": {
                    "type": "string",
                    "enum": ["fifo", "lifo", "average"],
                    "description": "Cost basis method: fifo (First In First Out), lifo (Last In First Out), or average"
                }
            },
            "required": ["method"]
        }
    },
    # Utility Tools
    {
        "name": "take_snapshot",
        "description": "Take a manual balance snapshot right now. Fetches current balances from all exchanges and saves them.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_snapshots",
        "description": "Get historical daily balance snapshots.",
        "input_schema": {
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "description": "Number of days to look back (default 7, max 30)"
                }
            },
            "required": []
        }
    },
    # DEX & On-Chain Tools
    {
        "name": "get_dex_trades",
        "description": "Get DEX trades for ALKIMI token on Sui blockchain (Cetus, Turbos, BlueMove, Aftermath). Shows swap activity across decentralized exchanges.",
        "input_schema": {
            "type": "object",
            "properties": {
                "since": {
                    "type": "string",
                    "description": "Start date (YYYY-MM-DD or 'today', 'this week'). Default: 7 days ago"
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum trades to return (default 50, max 100)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_alkimi_pools",
        "description": "Get liquidity pool data for ALKIMI across Sui DEXs. Shows TVL, 24h volume, price, and liquidity depth.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_onchain_analytics",
        "description": "Get on-chain analytics for ALKIMI token: holder count, top holders, supply distribution, wallet activity.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_treasury_value",
        "description": "Get the total treasury value including USDT and ALKIMI holdings across all wallets.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_top_holders",
        "description": "Get list of top ALKIMI token holders on Sui blockchain with their balances and percentages.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of top holders to return (default 10, max 50)"
                }
            },
            "required": []
        }
    },
    {
        "name": "get_wallet_activity",
        "description": "Get recent activity for a specific wallet address including transactions, swaps, and balance changes.",
        "input_schema": {
            "type": "object",
            "properties": {
                "address": {
                    "type": "string",
                    "description": "Sui wallet address to track"
                }
            },
            "required": ["address"]
        }
    },
    {
        "name": "get_market_data",
        "description": "Get comprehensive market data for ALKIMI from CoinGecko: price, 24h change, volume, market cap.",
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_query_history",
        "description": "Get history of recent queries made to the bot by a user.",
        "input_schema": {
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "description": "Number of queries to return (default 10, max 50)"
                }
            },
            "required": []
        }
    }
]


# =============================================================================
# Conversational Agent Class
# =============================================================================

class ConversationalAgent:
    """
    LLM-first conversational agent using Claude function calling.

    Handles natural language queries by using Claude to determine intent
    and execute appropriate tools, then formulating helpful responses.
    """

    def __init__(
        self,
        anthropic_api_key: str = None,
        data_provider: DataProvider = None,
        model: str = "claude-sonnet-4-20250514"
    ):
        """
        Initialize the conversational agent.

        Args:
            anthropic_api_key: Anthropic API key (defaults to ANTHROPIC_API_KEY env var)
            data_provider: DataProvider instance for data access
            model: Claude model to use
        """
        self.client = anthropic.Anthropic(
            api_key=anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.model = model
        self.data_provider = data_provider or DataProvider()

        # Initialize components
        self.query_engine = QueryEngine()
        self.executor = SafePythonExecutor(self.data_provider)
        self.functions = FunctionStore()
        self.pnl_config = PnLConfig()
        self.otc = OTCManager()
        self.pnl_calc = PnLCalculator(
            data_provider=self.data_provider,
            pnl_config=self.pnl_config,
            otc_manager=self.otc
        )

        # Thread-based conversation memory
        # {thread_ts: {'messages': [...], 'last_access': timestamp}}
        self.thread_history: Dict[str, Dict] = defaultdict(lambda: {'messages': [], 'last_access': 0})

        logger.info(f"ConversationalAgent initialized with model: {model}")

    def _cleanup_old_threads(self):
        """Remove thread histories that haven't been accessed recently."""
        current_time = time.time()
        expired_threads = [
            ts for ts, data in self.thread_history.items()
            if current_time - data['last_access'] > THREAD_HISTORY_TTL
        ]
        for ts in expired_threads:
            del self.thread_history[ts]
        if expired_threads:
            logger.debug(f"Cleaned up {len(expired_threads)} expired thread histories")

    def _add_to_history(self, thread_ts: str, role: str, content: str):
        """Add a message to thread history."""
        if not thread_ts:
            return

        self.thread_history[thread_ts]['messages'].append({
            'role': role,
            'content': content
        })
        self.thread_history[thread_ts]['last_access'] = time.time()

        # Trim to max messages
        if len(self.thread_history[thread_ts]['messages']) > MAX_HISTORY_MESSAGES:
            self.thread_history[thread_ts]['messages'] = \
                self.thread_history[thread_ts]['messages'][-MAX_HISTORY_MESSAGES:]

    def _get_history(self, thread_ts: str) -> List[Dict]:
        """Get conversation history for a thread."""
        if not thread_ts or thread_ts not in self.thread_history:
            return []
        self.thread_history[thread_ts]['last_access'] = time.time()
        return self.thread_history[thread_ts]['messages']

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse flexible date strings into datetime objects."""
        if not date_str:
            return None

        date_str = date_str.lower().strip()
        now = datetime.now()

        # Handle relative dates
        if date_str == 'today':
            return datetime.combine(now.date(), datetime.min.time())
        elif date_str == 'yesterday':
            return datetime.combine(now.date() - timedelta(days=1), datetime.min.time())
        elif date_str in ('this week', 'week'):
            return now - timedelta(days=now.weekday())
        elif date_str in ('this month', 'month'):
            return datetime(now.year, now.month, 1)
        elif date_str in ('last week',):
            start_of_this_week = now - timedelta(days=now.weekday())
            return start_of_this_week - timedelta(days=7)
        elif date_str in ('last month',):
            first_of_this_month = datetime(now.year, now.month, 1)
            last_month = first_of_this_month - timedelta(days=1)
            return datetime(last_month.year, last_month.month, 1)

        # Try ISO date format
        try:
            return datetime.fromisoformat(date_str)
        except ValueError:
            pass

        # Try other common formats
        for fmt in ['%Y-%m-%d', '%d/%m/%Y', '%m/%d/%Y']:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue

        logger.warning(f"Could not parse date: {date_str}")
        return None

    async def _execute_tool(self, tool_name: str, tool_input: Dict, user_id: str) -> str:
        """
        Execute a tool and return the result as a string.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
            user_id: ID of the user making the request

        Returns:
            String representation of the tool result
        """
        try:
            logger.info(f"Executing tool: {tool_name} with input: {tool_input}")

            if tool_name == "get_balances":
                balances = await self.data_provider.get_balances()
                if not balances:
                    return "No balance data available. A snapshot may need to be taken."
                return json.dumps(balances, indent=2)

            elif tool_name == "get_trades":
                since = self._parse_date(tool_input.get('since'))
                until = self._parse_date(tool_input.get('until'))
                exchange = tool_input.get('exchange')
                limit = min(tool_input.get('limit', 20), 100)

                df = await self.data_provider.get_trades_df(
                    since=since,
                    until=until,
                    exchange=exchange
                )

                # Filter by side if specified
                if tool_input.get('side'):
                    df = df[df['side'] == tool_input['side']]

                if df.empty:
                    return "No trades found for the specified criteria."

                # Limit results
                df = df.head(limit)

                # Format for display
                trades_list = []
                for _, row in df.iterrows():
                    trades_list.append({
                        'timestamp': row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else str(row['timestamp']),
                        'exchange': row['exchange'],
                        'side': row['side'],
                        'amount': float(row['amount']),
                        'price': float(row['price']),
                        'value_usd': float(row['amount'] * row['price'])
                    })

                return json.dumps({
                    'count': len(trades_list),
                    'trades': trades_list
                }, indent=2)

            elif tool_name == "get_trade_summary":
                since = self._parse_date(tool_input.get('since'))
                until = self._parse_date(tool_input.get('until'))

                summary = await self.data_provider.get_trade_summary(since=since, until=until)
                return json.dumps(summary, indent=2, default=str)

            elif tool_name == "get_current_price":
                price = await self.data_provider.get_current_price()
                if price is None:
                    return "Unable to fetch current price. CoinGecko may be unavailable."
                return json.dumps({'price_usd': price, 'formatted': f"${price:.6f}"})

            elif tool_name == "get_pnl_report":
                since = self._parse_date(tool_input.get('since'))
                until = self._parse_date(tool_input.get('until'))

                report = await self.pnl_calc.calculate(since=since, until=until)
                return json.dumps({
                    'period': f"{report.period_start.date()} to {report.period_end.date()}",
                    'realized_pnl': report.realized_pnl,
                    'unrealized_pnl': report.unrealized_pnl,
                    'net_pnl': report.net_pnl,
                    'total_sells': report.total_sells,
                    'cost_basis': report.total_cost_basis,
                    'current_holdings': report.current_holdings,
                    'avg_cost_per_token': report.avg_cost_per_token,
                    'current_price': report.current_price,
                    'trade_count': report.trade_count,
                    'by_exchange': report.by_exchange
                }, indent=2)

            elif tool_name == "execute_sql":
                sql = tool_input.get('sql', '')
                result = self.query_engine.execute_sql(sql)

                if result.error:
                    return f"SQL Error: {result.error}"

                if result.data is None or result.data.empty:
                    return "Query returned no results."

                # Convert DataFrame to list of dicts
                records = result.data.to_dict('records')
                return json.dumps({
                    'row_count': len(records),
                    'columns': list(result.data.columns),
                    'data': records[:50]  # Limit to 50 rows
                }, indent=2, default=str)

            elif tool_name == "list_saved_functions":
                functions = await self.functions.list_all()
                if not functions:
                    return "No saved functions found."

                func_list = []
                for f in functions:
                    func_list.append({
                        'name': f.name,
                        'description': f.description,
                        'created_by': f.created_by,
                        'use_count': f.use_count
                    })
                return json.dumps(func_list, indent=2)

            elif tool_name == "run_saved_function":
                name = tool_input.get('name', '')
                func = await self.functions.get(name)

                if not func:
                    return f"Function '{name}' not found."

                result = await self.executor.execute(func.code)
                await self.functions.increment_usage(name)

                if result.error:
                    return f"Execution error: {result.error}"

                return json.dumps({
                    'function': name,
                    'result': result.result,
                    'stdout': result.stdout
                }, indent=2, default=str)

            elif tool_name == "get_otc_transactions":
                transactions = await self.otc.list_all()
                if not transactions:
                    return "No OTC transactions recorded."

                otc_list = []
                for t in transactions:
                    otc_list.append({
                        'id': t.id,
                        'date': t.date.isoformat(),
                        'side': t.side,
                        'alkimi_amount': t.alkimi_amount,
                        'usd_amount': t.usd_amount,
                        'price': t.price,
                        'counterparty': t.counterparty
                    })
                return json.dumps(otc_list, indent=2)

            elif tool_name == "add_otc_transaction":
                otc_date = datetime.fromisoformat(tool_input['date'])
                otc_id = await self.otc.add(
                    date=otc_date,
                    alkimi_amount=tool_input['alkimi_amount'],
                    usd_amount=tool_input['usd_amount'],
                    side=tool_input['side'],
                    counterparty=tool_input.get('counterparty'),
                    notes=tool_input.get('notes'),
                    created_by=user_id
                )
                return json.dumps({
                    'success': True,
                    'otc_id': otc_id,
                    'message': f"OTC transaction #{otc_id} recorded successfully."
                })

            elif tool_name == "get_pnl_config":
                config = await self.pnl_config.get_config()
                method = await self.pnl_config.get_cost_basis_method()
                return json.dumps({
                    'cost_basis_method': method.value,
                    'config': config
                }, indent=2)

            elif tool_name == "set_cost_basis_method":
                method_str = tool_input.get('method', 'fifo').lower()
                method_map = {
                    'fifo': CostBasisMethod.FIFO,
                    'lifo': CostBasisMethod.LIFO,
                    'average': CostBasisMethod.AVERAGE,
                    'avg': CostBasisMethod.AVERAGE
                }
                method = method_map.get(method_str, CostBasisMethod.FIFO)
                await self.pnl_config.set_cost_basis_method(method, user_id)
                return json.dumps({
                    'success': True,
                    'method': method.value,
                    'message': f"Cost basis method set to {method.value.upper()}."
                })

            elif tool_name == "take_snapshot":
                # This requires fetching live balances - for now return a helpful message
                # Full implementation would call exchange APIs
                balances = await self.data_provider.get_balances()
                if balances:
                    self.data_provider.snapshot_manager.save_snapshot(balances)
                    return json.dumps({
                        'success': True,
                        'message': 'Snapshot saved successfully.',
                        'date': date.today().isoformat()
                    })
                else:
                    return json.dumps({
                        'success': False,
                        'message': 'No balance data available to snapshot. Run a refresh cycle first.'
                    })

            elif tool_name == "get_snapshots":
                days = min(tool_input.get('days', 7), 30)
                snapshots = await self.data_provider.get_snapshots(days=days)

                if not snapshots:
                    return "No snapshots found for the specified period."

                return json.dumps({
                    'count': len(snapshots),
                    'snapshots': snapshots
                }, indent=2)

            elif tool_name == "get_dex_trades":
                since = self._parse_date(tool_input.get('since'))
                if since is None:
                    since = datetime.now() - timedelta(days=7)
                limit = min(tool_input.get('limit', 50), 100)

                df = await self.data_provider.get_dex_trades(since=since)

                if df.empty:
                    return "No DEX trades found. Sui DEX monitor may not be configured or no recent swaps occurred."

                # Format trades
                trades_list = []
                for _, row in df.head(limit).iterrows():
                    trades_list.append({
                        'timestamp': row['timestamp'].isoformat() if hasattr(row['timestamp'], 'isoformat') else str(row['timestamp']),
                        'exchange': row.get('exchange', 'sui_dex'),
                        'side': row.get('side', 'unknown'),
                        'amount': float(row['amount']) if 'amount' in row else 0,
                        'price': float(row['price']) if 'price' in row else 0,
                        'value_usd': float(row['amount'] * row['price']) if 'amount' in row and 'price' in row else 0
                    })

                return json.dumps({
                    'count': len(trades_list),
                    'dex': 'Sui (Cetus, Turbos, BlueMove, Aftermath)',
                    'trades': trades_list
                }, indent=2)

            elif tool_name == "get_alkimi_pools":
                if not self.data_provider.sui_monitor:
                    return "Sui DEX monitor not configured. Set ALKIMI_TOKEN_CONTRACT environment variable."

                try:
                    pools = await self.data_provider.sui_monitor.get_alkimi_pools()
                    if not pools:
                        return "No liquidity pools found for ALKIMI on Sui DEXs."
                    return json.dumps(pools, indent=2, default=str)
                except Exception as e:
                    logger.error(f"Error fetching pools: {e}")
                    return f"Error fetching pool data: {str(e)}"

            elif tool_name == "get_onchain_analytics":
                if not self.data_provider.sui_monitor:
                    return "Sui DEX monitor not configured. Set ALKIMI_TOKEN_CONTRACT environment variable."

                try:
                    analytics = await self.data_provider.sui_monitor.get_onchain_analytics()
                    if not analytics:
                        return "Unable to fetch on-chain analytics."
                    return json.dumps(analytics, indent=2, default=str)
                except Exception as e:
                    logger.error(f"Error fetching analytics: {e}")
                    return f"Error fetching on-chain analytics: {str(e)}"

            elif tool_name == "get_treasury_value":
                if not self.data_provider.sui_monitor:
                    return "Sui DEX monitor not configured. Set ALKIMI_TOKEN_CONTRACT environment variable."

                try:
                    treasury = await self.data_provider.sui_monitor.get_treasury_value()
                    if not treasury:
                        return "Unable to fetch treasury value."
                    return json.dumps({
                        'total_value_usd': treasury.total_value_usd,
                        'usdt_balance': treasury.usdt_balance,
                        'alkimi_balance': treasury.alkimi_balance,
                        'alkimi_value_usd': treasury.alkimi_value_usd,
                        'alkimi_price': treasury.alkimi_price,
                        'timestamp': treasury.timestamp.isoformat() if hasattr(treasury.timestamp, 'isoformat') else str(treasury.timestamp)
                    }, indent=2)
                except Exception as e:
                    logger.error(f"Error fetching treasury value: {e}")
                    return f"Error fetching treasury value: {str(e)}"

            elif tool_name == "get_top_holders":
                if not self.data_provider.sui_monitor:
                    return "Sui DEX monitor not configured. Set ALKIMI_TOKEN_CONTRACT environment variable."

                limit = min(tool_input.get('limit', 10), 50)
                try:
                    holders = await self.data_provider.sui_monitor.get_top_holders(limit=limit)
                    if not holders:
                        return "Unable to fetch top holders."

                    holders_list = []
                    for h in holders:
                        holders_list.append({
                            'address': h.address,
                            'balance': h.balance,
                            'percentage': h.percentage,
                            'label': h.label if hasattr(h, 'label') else None
                        })
                    return json.dumps({
                        'count': len(holders_list),
                        'holders': holders_list
                    }, indent=2)
                except Exception as e:
                    logger.error(f"Error fetching top holders: {e}")
                    return f"Error fetching top holders: {str(e)}"

            elif tool_name == "get_wallet_activity":
                if not self.data_provider.sui_monitor:
                    return "Sui DEX monitor not configured. Set ALKIMI_TOKEN_CONTRACT environment variable."

                address = tool_input.get('address', '')
                if not address:
                    return "Wallet address is required."

                try:
                    activity = await self.data_provider.sui_monitor.get_wallet_activity(address)
                    if not activity:
                        return f"No activity found for wallet {address}."
                    return json.dumps(activity, indent=2, default=str)
                except Exception as e:
                    logger.error(f"Error fetching wallet activity: {e}")
                    return f"Error fetching wallet activity: {str(e)}"

            elif tool_name == "get_market_data":
                try:
                    market_data = await self.data_provider.get_market_data()
                    if not market_data:
                        return "Unable to fetch market data from CoinGecko."
                    return json.dumps(market_data, indent=2, default=str)
                except Exception as e:
                    logger.error(f"Error fetching market data: {e}")
                    return f"Error fetching market data: {str(e)}"

            elif tool_name == "get_query_history":
                limit = min(tool_input.get('limit', 10), 50)
                try:
                    history = await self.data_provider.get_query_history(user_id=user_id, limit=limit)
                    if not history:
                        return "No query history found."
                    return json.dumps({
                        'count': len(history),
                        'queries': history
                    }, indent=2, default=str)
                except Exception as e:
                    logger.error(f"Error fetching query history: {e}")
                    return f"Error fetching query history: {str(e)}"

            else:
                return f"Unknown tool: {tool_name}"

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}", exc_info=True)
            return f"Error executing {tool_name}: {str(e)}"

    async def process(
        self,
        message: str,
        user_id: str,
        thread_ts: str = None
    ) -> Dict[str, Any]:
        """
        Process a natural language message using Claude with tools.

        Args:
            message: User's message text
            user_id: Slack user ID
            thread_ts: Slack thread timestamp for conversation continuity

        Returns:
            Dict with 'text' and/or 'blocks' for Slack response
        """
        self._cleanup_old_threads()

        # Track processing time
        start_time = time.time()

        # Log incoming query for system prompt improvement analysis
        logger.info(f"USER_QUERY | user={user_id} | thread={thread_ts or 'none'} | query={message[:200]}")

        # Build system prompt with current date
        system = SYSTEM_PROMPT.format(current_date=date.today().isoformat())

        # Build messages array with history
        messages = []
        history = self._get_history(thread_ts)

        for msg in history:
            messages.append(msg)

        # Add current message
        messages.append({"role": "user", "content": message})

        # Add to history
        self._add_to_history(thread_ts, "user", message)

        try:
            # Initial API call with tools
            response = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                system=system,
                tools=TOOLS,
                messages=messages
            )

            # Process tool calls in a loop
            tools_used = []
            while response.stop_reason == "tool_use":
                # Extract tool use blocks
                tool_use_blocks = [
                    block for block in response.content
                    if block.type == "tool_use"
                ]

                # Execute each tool
                tool_results = []
                for tool_use in tool_use_blocks:
                    tool_name = tool_use.name
                    tool_input = tool_use.input
                    tools_used.append(tool_name)

                    result = await self._execute_tool(tool_name, tool_input, user_id)

                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": result
                    })

                # Continue conversation with tool results
                messages.append({"role": "assistant", "content": response.content})
                messages.append({"role": "user", "content": tool_results})

                # Get next response
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=4096,
                    system=system,
                    tools=TOOLS,
                    messages=messages
                )

            # Extract final text response
            text_blocks = [
                block.text for block in response.content
                if hasattr(block, 'text')
            ]
            final_text = "\n".join(text_blocks) if text_blocks else "I processed your request but have no additional information to share."

            # Add assistant response to history
            self._add_to_history(thread_ts, "assistant", final_text)

            # Calculate processing time
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Log response for system prompt improvement analysis
            tools_str = ','.join(tools_used) if tools_used else 'none'
            response_preview = final_text[:100].replace('\n', ' ') if final_text else 'empty'
            logger.info(f"BOT_RESPONSE | user={user_id} | tools={tools_str} | time_ms={processing_time_ms} | response_len={len(final_text)} | preview={response_preview}")

            # Save conversation for fine-tuning
            try:
                self.data_provider.save_conversation_log(
                    thread_ts=thread_ts,
                    user_id=user_id,
                    user_message=message,
                    assistant_response=final_text,
                    tools_used=tools_used,
                    model=self.model,
                    processing_time_ms=processing_time_ms
                )
            except Exception as log_error:
                logger.warning(f"Failed to save conversation log: {log_error}")

            return {
                "text": final_text,
                "tools_used": tools_used
            }

        except anthropic.APIError as e:
            logger.error(f"Claude API error: {e}")
            return {
                "text": f"I encountered an error processing your request: {str(e)}",
                "error": True
            }
        except Exception as e:
            logger.error(f"Error in ConversationalAgent.process: {e}", exc_info=True)
            return {
                "text": f"An unexpected error occurred: {str(e)}",
                "error": True
            }
