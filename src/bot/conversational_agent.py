"""
Conversational Agent for ALKIMI Slack Bot

LLM-first approach using Claude function calling for natural language interactions.
Replaces keyword-based routing with intelligent intent understanding.

Now uses MCP (Model Context Protocol) for standardized tool responses.
All tools return MCPResponse with consistent format:
- success: bool
- data: Any (tool-specific response data)
- error: Optional[str] (error message if success=False)
- metadata: Dict (timestamps, counts, etc.)
"""

import os
import json
import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, List, Optional, Any, Tuple
from collections import defaultdict
import time

import anthropic

from config.settings import settings
from src.bot.data_provider import DataProvider
from src.mcp.server import call_tool
from src.utils import get_logger

logger = get_logger(__name__)

# Thread history TTL in seconds (30 minutes)
THREAD_HISTORY_TTL = 1800
# Max messages configurable via env var (default 20)
# This allows users to adjust context window based on their needs
MAX_HISTORY_MESSAGES = int(os.environ.get("MAX_CONTEXT_MESSAGES", "20"))


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

    Uses MCP (Model Context Protocol) for all tool execution, providing
    standardized MCPResponse format across all data sources.
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
            data_provider: DataProvider instance for data access (optional, MCP tools manage their own)
            model: Claude model to use
        """
        self.client = anthropic.Anthropic(
            api_key=anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.model = model

        # DataProvider kept for conversation logging (MCP tools have their own)
        self.data_provider = data_provider or DataProvider(sui_config=settings.sui_config)

        # Conversation context settings
        self.max_context_messages = MAX_HISTORY_MESSAGES

        # Thread-based conversation memory
        # {thread_ts: {'messages': [...], 'last_access': timestamp}}
        self.thread_history: Dict[str, Dict] = defaultdict(lambda: {'messages': [], 'last_access': 0})

        logger.info(f"ConversationalAgent initialized with model: {model} (MCP-enabled)")
        logger.info(f"Max context messages per thread: {self.max_context_messages}")

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
        """
        Add a message to thread history with timestamp.

        Args:
            thread_ts: Thread timestamp identifier
            role: Message role ('user' or 'assistant')
            content: Message content
        """
        if not thread_ts:
            return

        self.thread_history[thread_ts]['messages'].append({
            'role': role,
            'content': content,
            'timestamp': datetime.now().isoformat()
        })
        self.thread_history[thread_ts]['last_access'] = time.time()

        # Trim to max messages (keep most recent)
        if len(self.thread_history[thread_ts]['messages']) > MAX_HISTORY_MESSAGES:
            self.thread_history[thread_ts]['messages'] = \
                self.thread_history[thread_ts]['messages'][-MAX_HISTORY_MESSAGES:]

            logger.debug(f"Trimmed thread {thread_ts} history to {MAX_HISTORY_MESSAGES} messages")

    def _get_history(self, thread_ts: str) -> List[Dict]:
        """
        Get conversation history for a thread.

        Args:
            thread_ts: Thread timestamp identifier

        Returns:
            List of message dictionaries with role, content, and timestamp
        """
        if not thread_ts or thread_ts not in self.thread_history:
            return []
        self.thread_history[thread_ts]['last_access'] = time.time()
        return self.thread_history[thread_ts]['messages']

    def _summarize_long_conversation(self, messages: List[Dict]) -> Optional[str]:
        """
        Generate a summary for long conversations to provide context efficiently.

        This helps maintain context awareness when conversations exceed typical limits
        by summarizing older messages while preserving recent exchanges.

        Args:
            messages: List of conversation messages

        Returns:
            Summary string if conversation is long enough, None otherwise
        """
        if len(messages) <= 5:
            return None  # No need to summarize short conversations

        # Create a brief summary of the conversation flow
        summary_parts = []
        summary_parts.append("Previous conversation context:")

        # Include first message to show conversation start
        first_msg = messages[0]
        if first_msg['role'] == 'user':
            preview = first_msg['content'][:80]
            summary_parts.append(f"- Initial query: {preview}...")

        # Count middle messages
        middle_count = len(messages) - 5
        if middle_count > 0:
            summary_parts.append(f"- {middle_count} messages exchanged")

        # Note: The actual recent messages are still passed to the LLM
        # This summary can be prepended if needed for very long conversations
        return "\n".join(summary_parts)

    def get_conversation_metadata(self, thread_ts: str) -> Dict[str, Any]:
        """
        Get metadata about a conversation thread.

        Args:
            thread_ts: Thread timestamp identifier

        Returns:
            Dict with conversation statistics and metadata
        """
        if not thread_ts or thread_ts not in self.thread_history:
            return {
                "exists": False,
                "message_count": 0
            }

        thread_data = self.thread_history[thread_ts]
        messages = thread_data['messages']

        return {
            "exists": True,
            "message_count": len(messages),
            "last_access": datetime.fromtimestamp(thread_data['last_access']).isoformat(),
            "first_message_time": messages[0]['timestamp'] if messages else None,
            "last_message_time": messages[-1]['timestamp'] if messages else None,
            "max_messages": MAX_HISTORY_MESSAGES
        }

    def clear_context(self, thread_ts: Optional[str] = None) -> Dict[str, Any]:
        """
        Clear conversation context for one or all threads.

        Useful for resetting conversation state or managing memory usage.

        Args:
            thread_ts: Thread timestamp to clear. If None, clears all threads.

        Returns:
            Dict with information about what was cleared
        """
        if thread_ts:
            if thread_ts in self.thread_history:
                message_count = len(self.thread_history[thread_ts]['messages'])
                del self.thread_history[thread_ts]
                logger.info(f"Cleared context for thread {thread_ts} ({message_count} messages)")
                return {
                    "success": True,
                    "cleared": "single_thread",
                    "thread_ts": thread_ts,
                    "messages_cleared": message_count
                }
            else:
                return {
                    "success": False,
                    "error": "Thread not found",
                    "thread_ts": thread_ts
                }
        else:
            # Clear all threads
            thread_count = len(self.thread_history)
            total_messages = sum(
                len(data['messages'])
                for data in self.thread_history.values()
            )
            self.thread_history.clear()
            logger.info(f"Cleared all conversation contexts ({thread_count} threads, {total_messages} messages)")
            return {
                "success": True,
                "cleared": "all_threads",
                "threads_cleared": thread_count,
                "messages_cleared": total_messages
            }

    async def _execute_tool(self, tool_name: str, tool_input: Dict, user_id: str) -> str:
        """
        Execute a tool via MCP and return the result as a string.

        All tools now use the MCP call_tool function which provides
        standardized MCPResponse format with consistent error handling.

        Args:
            tool_name: Name of the tool to execute
            tool_input: Input parameters for the tool
            user_id: ID of the user making the request

        Returns:
            String representation of the tool result (JSON-formatted)
        """
        logger.info(f"Executing MCP tool: {tool_name} with input: {tool_input}")

        # Add user_id to tool_input for tools that need it
        if tool_name in ("add_otc_transaction", "set_cost_basis_method"):
            tool_input["user_id"] = user_id

        # Call the MCP tool
        response = await call_tool(tool_name, **tool_input)

        # Format MCPResponse for Claude
        if response.success:
            # Return data as JSON string for successful calls
            if response.data is None:
                return json.dumps({"success": True, "message": "Operation completed"}, indent=2)
            return json.dumps(response.data, indent=2, default=str)
        else:
            # Return error message for failed calls
            error_msg = response.error or "Unknown error occurred"
            logger.error(f"MCP tool {tool_name} failed: {error_msg}")
            return json.dumps({
                "success": False,
                "error": error_msg,
                "metadata": response.metadata
            }, indent=2, default=str)

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

        # Get conversation history
        history = self._get_history(thread_ts)
        history_count = len(history)

        # Log incoming query for system prompt improvement analysis
        logger.info(f"USER_QUERY | user={user_id} | thread={thread_ts or 'none'} | history_msgs={history_count} | query={message[:200]}")

        # Build system prompt with current date
        system = SYSTEM_PROMPT.format(current_date=date.today().isoformat())

        # Build messages array with history
        messages = []

        # Add conversation history (already includes role, content, timestamp)
        # We only send role and content to Claude API (timestamp is for our records)
        for msg in history:
            messages.append({
                "role": msg["role"],
                "content": msg["content"]
            })

        # Optional: Generate summary for very long conversations
        # Currently we just pass all messages, but summary could be prepended if needed
        summary = self._summarize_long_conversation(history)
        if summary:
            logger.debug(f"Generated summary for thread {thread_ts}: {summary}")

        # Add current message
        messages.append({"role": "user", "content": message})

        # Add to history with timestamp
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
