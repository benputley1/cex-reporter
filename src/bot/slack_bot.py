"""
Slack Bot Module - Enhanced with LLM-Powered Query Router

Conversational AI interface for HFT traders to query ALKIMI trading data
using natural language, SQL, Python, and saved functions.

Integrates:
- DataProvider for unified data access
- QueryRouter for intent classification
- QueryEngine for SQL execution
- SafePythonExecutor for sandboxed Python
- FunctionStore for saved functions
- PnLCalculator for P&L reports
- ClaudeClient for LLM queries
- SlackFormatter for rich messages
"""

import os
import re
import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Optional, Any, List, Set
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler

# Thinking messages to show while processing
THINKING_MESSAGES = [
    "Pulling the data...",
    "Checking the numbers...",
    "On it...",
    "Looking into that...",
    "One sec...",
    "Crunching the numbers...",
    "Querying the database...",
]

from config.settings import settings
from src.bot.data_provider import DataProvider
from src.bot.query_router import QueryRouter, QueryIntent
from src.bot.query_engine import QueryEngine
from src.bot.python_executor import SafePythonExecutor
from src.bot.function_store import FunctionStore
from src.bot.pnl_config import PnLConfig, OTCManager, PnLCalculator, CostBasisMethod
from src.bot.prompts import ClaudeClient
from src.bot.formatters import SlackFormatter
from src.bot.conversational_agent import ConversationalAgent
from src.utils import get_logger

logger = get_logger(__name__)

# Feature flag for conversational agent (set to false to use legacy keyword routing)
USE_CONVERSATIONAL_AGENT = os.environ.get("USE_CONVERSATIONAL_AGENT", "true").lower() == "true"


class AlkimiBot:
    """ALKIMI Trading Bot with LLM-powered queries."""

    def __init__(
        self,
        bot_token: str = None,
        app_token: str = None,
        signing_secret: str = None,
        anthropic_api_key: str = None
    ):
        """
        Initialize Alkimi Slack Bot.

        Args:
            bot_token: Slack bot token (SLACK_BOT_TOKEN)
            app_token: Slack app token (SLACK_APP_TOKEN)
            signing_secret: Slack signing secret
            anthropic_api_key: Anthropic API key for Claude
        """
        # Initialize Slack app
        self.app = AsyncApp(
            token=bot_token or os.environ.get("SLACK_BOT_TOKEN"),
            signing_secret=signing_secret or os.environ.get("SLACK_SIGNING_SECRET")
        )
        self.app_token = app_token or os.environ.get("SLACK_APP_TOKEN")

        # Initialize components
        self.data_provider = DataProvider(
            db_path=settings.trade_cache_db,
            sui_config=settings.sui_config
        )
        self.router = QueryRouter()
        self.claude = ClaudeClient(
            api_key=anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        )
        self.query_engine = QueryEngine(claude_client=self.claude)
        self.executor = SafePythonExecutor(self.data_provider)
        self.functions = FunctionStore()
        self.pnl_config = PnLConfig()
        self.otc = OTCManager()
        self.pnl_calc = PnLCalculator(
            data_provider=self.data_provider,
            pnl_config=self.pnl_config,
            otc_manager=self.otc
        )
        self.formatter = SlackFormatter()

        # Initialize conversational agent if enabled
        if USE_CONVERSATIONAL_AGENT:
            self.agent = ConversationalAgent(
                anthropic_api_key=anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY"),
                data_provider=self.data_provider
            )
            logger.info("ConversationalAgent enabled for natural language queries")
        else:
            self.agent = None
            logger.info("Using legacy keyword-based routing")

        # Track threads the bot has participated in (for auto-responding)
        # Load from database so threads survive restarts/deploys
        self.active_threads: Set[str] = self.data_provider.load_active_threads()
        logger.info(f"Loaded {len(self.active_threads)} active threads from database")

        # Cleanup old threads (30+ days) to prevent unbounded growth
        cleaned = self.data_provider.cleanup_old_threads(days=30)
        if cleaned > 0:
            logger.info(f"Cleaned up {cleaned} old threads")

        # Register handlers
        self._register_handlers()

        logger.info("AlkimiBot initialized successfully")

    def _register_handlers(self):
        """Register all Slack event handlers."""

        # App mention handler (when bot is @mentioned)
        @self.app.event("app_mention")
        async def handle_mention(event, say):
            # Track this thread as active (both in memory and database)
            thread_ts = event.get("ts")
            channel_id = event.get("channel")
            if thread_ts:
                self.active_threads.add(thread_ts)
                # Persist to database so thread survives restarts
                self.data_provider.add_active_thread(thread_ts, channel_id)
            await self._handle_query(event, say, is_mention=True)

        # Direct message and thread reply handler
        @self.app.event("message")
        async def handle_message(event, say):
            # Skip bot's own messages
            if event.get("bot_id"):
                return

            # Handle DMs
            if event.get("channel_type") == "im":
                await self._handle_query(event, say, is_mention=False)
                return

            # Handle thread replies (no @mention needed if bot is in thread)
            thread_ts = event.get("thread_ts")
            if thread_ts:
                is_active = thread_ts in self.active_threads
                logger.info(
                    f"Thread reply detected: thread_ts={thread_ts}, "
                    f"is_active={is_active}, active_count={len(self.active_threads)}"
                )
                if is_active:
                    await self._handle_query(event, say, is_mention=False)
                else:
                    logger.debug(f"Ignoring thread reply - thread {thread_ts} not in active_threads")

        # Slash command: /alkimi
        @self.app.command("/alkimi")
        async def handle_alkimi_command(ack, command, say):
            await ack()
            await self._handle_slash_command(command, say)

    async def _handle_query(self, event: Dict, say, is_mention: bool = False):
        """Handle natural language query from mention or DM."""
        text = event.get("text", "")
        user = event.get("user", "unknown")

        # For @mentions, always start a new thread using the message ts
        # For thread replies, use the existing thread_ts
        if is_mention:
            thread_ts = event.get("ts")  # Start new thread from the mention
        else:
            thread_ts = event.get("thread_ts") or event.get("ts")

        # Remove bot mention from text
        text = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

        if not text:
            await say(blocks=self.formatter.format_help(), thread_ts=thread_ts)
            return

        logger.info(f"Query from {user}: {text}")

        # Send immediate thinking message
        thinking_msg = random.choice(THINKING_MESSAGES)
        await say(text=thinking_msg, thread_ts=thread_ts)

        try:
            # Use conversational agent if enabled
            if self.agent:
                response = await self.agent.process(
                    message=text,
                    user_id=user,
                    thread_ts=thread_ts
                )

                # Send response
                response_text = response.get("text", "I couldn't process that request.")

                # Add context about tools used (optional, can be removed for cleaner output)
                if response.get("tools_used"):
                    tools_str = ", ".join(response["tools_used"])
                    logger.debug(f"Tools used: {tools_str}")

                await say(text=response_text, thread_ts=thread_ts)
                return

            # Legacy: keyword-based routing
            intent = self.router.classify(text)
            params = self.router.extract_parameters(text, intent)

            # Route to appropriate handler
            await self._route_query(intent, params, user, say)

        except Exception as e:
            logger.error(f"Error handling query: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                str(e),
                "Try rephrasing your question or use `/alkimi help` for examples"
            ))

    async def _handle_slash_command(self, command: Dict, say):
        """Handle /alkimi slash command."""
        text = command.get("text", "").strip()
        user = command.get("user_id", "unknown")

        logger.info(f"Slash command from {user}: /alkimi {text}")

        # Parse subcommands
        parts = text.split(maxsplit=1)
        subcommand = parts[0].lower() if parts else "help"
        args = parts[1] if len(parts) > 1 else ""

        try:
            if subcommand == "help":
                await say(blocks=self.formatter.format_help())
            elif subcommand == "pnl":
                await self._handle_pnl(args, user, say)
            elif subcommand == "sql":
                await self._handle_sql(args, user, say)
            elif subcommand == "run":
                await self._handle_run_function(args, user, say)
            elif subcommand == "functions":
                await self._handle_list_functions(say)
            elif subcommand == "create":
                await self._handle_create_function(args, user, say)
            elif subcommand == "history":
                await self._handle_history(user, say)
            elif subcommand == "config":
                await self._handle_config(args, user, say)
            elif subcommand == "otc":
                await self._handle_otc(args, user, say)
            else:
                # Treat as natural language query
                intent = self.router.classify(text)
                params = self.router.extract_parameters(text, intent)
                await self._route_query(intent, params, user, say)

        except Exception as e:
            logger.error(f"Error handling slash command: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                str(e),
                "Check `/alkimi help` for command syntax"
            ))

    async def _route_query(self, intent: QueryIntent, params, user: str, say):
        """Route query to appropriate handler based on intent."""

        if intent == QueryIntent.PNL_QUERY:
            await self._handle_pnl_query(params, user, say)
        elif intent == QueryIntent.TRADE_QUERY:
            await self._handle_trade_query(params, user, say)
        elif intent == QueryIntent.BALANCE_QUERY:
            await self._handle_balance_query(say)
        elif intent == QueryIntent.PRICE_QUERY:
            await self._handle_price_query(say)
        elif intent == QueryIntent.SQL_QUERY:
            await self._handle_sql(params.sql, user, say)
        elif intent == QueryIntent.ANALYTICS_QUERY:
            await self._handle_analytics_query(params, user, say)
        elif intent == QueryIntent.PYTHON_FUNCTION:
            await self._handle_create_function(params.raw_query, user, say)
        elif intent == QueryIntent.RUN_FUNCTION:
            await self._handle_run_function(params.function_name or "", user, say)
        elif intent == QueryIntent.HELP:
            await say(blocks=self.formatter.format_help())
        else:
            # Try natural language with Claude
            await self._handle_natural_language(params.raw_query, user, say)

    async def _handle_pnl_query(self, params, user: str, say):
        """Handle P&L query."""
        since, until = params.time_range or (None, None)

        logger.info(f"P&L query from {user}: since={since}, until={until}")

        try:
            report = await self.pnl_calc.calculate(since=since, until=until)
            await say(blocks=self.formatter.format_pnl_report(report))
        except Exception as e:
            logger.error(f"Error calculating P&L: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                f"Failed to calculate P&L: {str(e)}"
            ))

    async def _handle_trade_query(self, params, user: str, say):
        """Handle trade query with filters."""
        since, until = params.time_range or (None, None)

        logger.info(f"Trade query from {user}: exchange={params.exchange}, threshold={params.amount_threshold}")

        try:
            trades = await self.data_provider.get_trades_df(
                since=since,
                until=until,
                exchange=params.exchange
            )

            if params.amount_threshold:
                trades = trades[trades['amount'] * trades['price'] >= params.amount_threshold]

            await say(blocks=self.formatter.format_trade_list(trades))

        except Exception as e:
            logger.error(f"Error querying trades: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                f"Failed to query trades: {str(e)}"
            ))

    async def _handle_balance_query(self, say):
        """Handle balance query."""
        logger.info("Balance query")

        try:
            balances = await self.data_provider.get_balances()
            await say(blocks=self.formatter.format_balance_summary(balances))
        except Exception as e:
            logger.error(f"Error querying balances: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                f"Failed to query balances: {str(e)}"
            ))

    async def _handle_price_query(self, say):
        """Handle price query."""
        logger.info("Price query")

        try:
            price = await self.data_provider.get_current_price()
            await say(f"💹 Current ALKIMI price: *${price:.6f}*")
        except Exception as e:
            logger.error(f"Error querying price: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                f"Failed to query price: {str(e)}"
            ))

    async def _handle_pnl(self, args: str, user: str, say):
        """Handle explicit P&L command."""
        # Parse date range from args if provided
        # For now, default to current month
        logger.info(f"Explicit P&L command from {user}: {args}")

        try:
            report = await self.pnl_calc.calculate()
            await say(blocks=self.formatter.format_pnl_report(report))
        except Exception as e:
            logger.error(f"Error calculating P&L: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                f"Failed to calculate P&L: {str(e)}"
            ))

    async def _handle_sql(self, sql: str, user: str, say):
        """Handle SQL query execution."""
        if not sql:
            await say(blocks=self.formatter.format_error(
                "No SQL query provided",
                "Usage: `/alkimi sql SELECT * FROM trades LIMIT 10`"
            ))
            return

        logger.info(f"SQL query from {user}: {sql[:100]}")

        try:
            result = await self.query_engine.execute_sql(sql)

            if result.success:
                await say(blocks=self.formatter.format_table(
                    result.data,
                    title="Query Results"
                ))

                # Log to history
                await self.data_provider.save_query_history(
                    user_id=user,
                    query_text=sql,
                    query_type="sql",
                    generated_code=sql,
                    execution_time_ms=result.execution_time_ms,
                    success=True
                )
            else:
                await say(blocks=self.formatter.format_error(
                    result.error,
                    "Check your SQL syntax and try again"
                ))

        except Exception as e:
            logger.error(f"Error executing SQL: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                f"SQL execution failed: {str(e)}"
            ))

    async def _handle_run_function(self, args: str, user: str, say):
        """Handle running a saved function."""
        parts = args.split()
        func_name = parts[0] if parts else ""

        if not func_name:
            await say(blocks=self.formatter.format_error(
                "No function name provided",
                "Usage: `/alkimi run <function_name>`"
            ))
            return

        logger.info(f"Running function '{func_name}' for {user}")

        try:
            func = await self.functions.get(func_name)
            if not func:
                await say(blocks=self.formatter.format_error(
                    f"Function '{func_name}' not found",
                    "Use `/alkimi functions` to see available functions"
                ))
                return

            result = await self.executor.execute(func.code)
            await self.functions.update_usage(func_name)

            if result.success:
                # Format result appropriately
                import pandas as pd
                if isinstance(result.result, pd.DataFrame):
                    await say(blocks=self.formatter.format_table(
                        result.result,
                        title=func_name
                    ))
                else:
                    await say(f"```\n{result.result}\n```")

                # Log to history
                await self.data_provider.save_query_history(
                    user_id=user,
                    query_text=f"run {func_name}",
                    query_type="function",
                    generated_code=func.code,
                    execution_time_ms=result.execution_time_ms,
                    success=True
                )
            else:
                await say(blocks=self.formatter.format_error(
                    result.error,
                    f"Function '{func_name}' failed to execute"
                ))

        except Exception as e:
            logger.error(f"Error running function: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                f"Failed to run function: {str(e)}"
            ))

    async def _handle_list_functions(self, say):
        """List all saved functions."""
        logger.info("Listing saved functions")

        try:
            functions = await self.functions.list_all()
            await say(blocks=self.formatter.format_function_list(functions))
        except Exception as e:
            logger.error(f"Error listing functions: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                f"Failed to list functions: {str(e)}"
            ))

    async def _handle_create_function(self, args: str, user: str, say):
        """Create a new saved function using Claude."""
        if not args:
            await say(blocks=self.formatter.format_error(
                "No description provided",
                "Usage: `/alkimi create <description of what the function should do>`"
            ))
            return

        logger.info(f"Creating function from description: {args}")

        try:
            # Generate Python code from description
            code = await self.claude.generate_python(args)

            # Extract function name
            func_name = self.executor.validator.extract_function_name(code)
            if not func_name:
                func_name = f"func_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

            # Save function
            await self.functions.save(
                name=func_name,
                code=code,
                description=args,
                created_by=user
            )

            await say(blocks=[
                *self.formatter.format_success(
                    f"Created function `{func_name}`",
                    f"Run with: `/alkimi run {func_name}`"
                ),
                *self.formatter.format_code(code)
            ])

        except Exception as e:
            logger.error(f"Error creating function: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                f"Failed to create function: {str(e)}"
            ))

    async def _handle_history(self, user: str, say):
        """Show query history."""
        logger.info(f"Query history requested by {user}")

        try:
            # Get recent history from data provider
            history = await self.data_provider.get_query_history(user_id=user, limit=10)
            await say(blocks=self.formatter.format_query_history(history))
        except Exception as e:
            logger.error(f"Error retrieving history: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                f"Failed to retrieve history: {str(e)}"
            ))

    async def _handle_config(self, args: str, user: str, say):
        """Handle P&L config commands."""
        if not args:
            # Show current config
            logger.info("Displaying P&L configuration")
            try:
                config = await self.pnl_config.get_config()
                await say(blocks=self.formatter.format_config(config))
            except Exception as e:
                logger.error(f"Error getting config: {e}", exc_info=True)
                await say(blocks=self.formatter.format_error(
                    f"Failed to get configuration: {str(e)}"
                ))
        else:
            # Parse config command (e.g., "cost-basis fifo")
            parts = args.split()
            if len(parts) >= 2 and parts[0] == "cost-basis":
                method = parts[1].upper()
                if method in ["FIFO", "LIFO", "AVG"]:
                    try:
                        await self.pnl_config.set_cost_basis_method(
                            CostBasisMethod[method], user
                        )
                        await say(blocks=self.formatter.format_success(
                            f"Cost basis method set to {method}"
                        ))
                    except Exception as e:
                        logger.error(f"Error setting config: {e}", exc_info=True)
                        await say(blocks=self.formatter.format_error(
                            f"Failed to update configuration: {str(e)}"
                        ))
                else:
                    await say(blocks=self.formatter.format_error(
                        f"Unknown method: {method}",
                        "Valid methods: FIFO, LIFO, AVG"
                    ))
            else:
                await say(blocks=self.formatter.format_error(
                    "Invalid config command",
                    "Usage: `/alkimi config cost-basis <FIFO|LIFO|AVG>`"
                ))

    async def _handle_otc(self, args: str, user: str, say):
        """Handle OTC commands (list, add, remove)."""
        parts = args.split()
        subcommand = parts[0].lower() if parts else "list"

        if subcommand == "list":
            logger.info("Listing OTC transactions")
            try:
                otcs = await self.otc.list_all()
                if not otcs:
                    await say("No OTC transactions recorded")
                else:
                    # Format OTC list
                    otc_text = f"*OTC Transactions ({len(otcs)} total)*\n\n"
                    for otc in otcs:
                        otc_text += (
                            f"• ID {otc.id}: {otc.amount:,.0f} ALKIMI @ ${otc.price:.6f}\n"
                            f"  {otc.counterparty} - {otc.date.strftime('%Y-%m-%d')}\n"
                        )
                    await say(otc_text)
            except Exception as e:
                logger.error(f"Error listing OTC: {e}", exc_info=True)
                await say(blocks=self.formatter.format_error(
                    f"Failed to list OTC transactions: {str(e)}"
                ))

        elif subcommand == "add":
            # Parse: add 3000000 ALKIMI @ 0.0273 counterparty "date"
            await say(blocks=self.formatter.format_error(
                "OTC add not yet implemented",
                "Coming soon!"
            ))

        elif subcommand == "remove":
            if len(parts) >= 2:
                try:
                    otc_id = int(parts[1])
                    await self.otc.remove(otc_id)
                    await say(blocks=self.formatter.format_success(
                        f"Removed OTC transaction {otc_id}"
                    ))
                except ValueError:
                    await say(blocks=self.formatter.format_error(
                        "Invalid OTC ID",
                        "Usage: `/alkimi otc remove <id>`"
                    ))
                except Exception as e:
                    logger.error(f"Error removing OTC: {e}", exc_info=True)
                    await say(blocks=self.formatter.format_error(
                        f"Failed to remove OTC transaction: {str(e)}"
                    ))
            else:
                await say(blocks=self.formatter.format_error(
                    "No OTC ID provided",
                    "Usage: `/alkimi otc remove <id>`"
                ))
        else:
            await say(blocks=self.formatter.format_error(
                f"Unknown OTC subcommand: {subcommand}",
                "Available: list, add, remove"
            ))

    async def _handle_analytics_query(self, params, user: str, say):
        """Handle analytics query using Claude."""
        logger.info(f"Analytics query from {user}: {params.raw_query}")

        try:
            # Get context from data provider
            summary = await self.data_provider.get_trade_summary()
            context = {
                'trade_summary': summary,
                'query': params.raw_query
            }

            # Ask Claude
            answer = await self.claude.answer_query(params.raw_query, str(context))
            await say(answer)

        except Exception as e:
            logger.error(f"Error handling analytics query: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                f"Analytics query failed: {str(e)}"
            ))

    async def _handle_natural_language(self, query: str, user: str, say):
        """Handle natural language query with Claude."""
        logger.info(f"Natural language query from {user}: {query}")

        try:
            # Get context from data provider
            summary = await self.data_provider.get_trade_summary()
            context = f"Trade summary: {summary}"

            # Ask Claude
            answer = await self.claude.answer_query(query, context)
            await say(answer)

            # Log to history
            await self.data_provider.save_query_history(
                user_id=user,
                query_text=query,
                query_type="natural_language",
                generated_code=None,
                execution_time_ms=None,
                success=True
            )

        except Exception as e:
            logger.error(f"Error handling natural language query: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                f"Query failed: {str(e)}",
                "Try rephrasing your question"
            ))

    async def start(self):
        """Start the bot in Socket Mode."""
        try:
            handler = AsyncSocketModeHandler(self.app, self.app_token)
            logger.info("Starting AlkimiBot in Socket Mode...")
            await handler.start_async()
        except Exception as e:
            logger.error(f"Error starting bot: {e}", exc_info=True)
            raise

    async def close(self):
        """Cleanup resources."""
        logger.info("Shutting down AlkimiBot...")
        # Add any cleanup needed
        logger.info("AlkimiBot closed")


def create_bot(
    bot_token: str = None,
    app_token: str = None,
    signing_secret: str = None,
    anthropic_api_key: str = None
) -> AlkimiBot:
    """
    Factory function to create bot instance.

    Args:
        bot_token: Slack bot token (defaults to env SLACK_BOT_TOKEN)
        app_token: Slack app token (defaults to env SLACK_APP_TOKEN)
        signing_secret: Slack signing secret (defaults to env SLACK_SIGNING_SECRET)
        anthropic_api_key: Anthropic API key (defaults to env ANTHROPIC_API_KEY)

    Returns:
        Configured AlkimiBot instance
    """
    return AlkimiBot(
        bot_token=bot_token,
        app_token=app_token,
        signing_secret=signing_secret,
        anthropic_api_key=anthropic_api_key
    )


# Example queries the trader can ask
EXAMPLE_QUERIES = [
    "What's the current spread between MEXC and Cetus?",
    "Show me all trades over $5K in the last hour",
    "Why did volume spike on Bluefin at 2pm?",
    "Compare my execution quality this week vs last week",
    "What arbitrage opportunities exist right now?",
    "Summarize overnight activity",
    "Which wallet has the most exposure?",
    "What's our total unrealized P&L?",
    "What was our best performing venue yesterday?",
    "How much ALKIMI did we sell this week?",
    "Create a function to detect whale trades over $10K",
    "Show my query history",
]
