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

        # Configure agent timeout (default 60 seconds)
        self.agent_timeout = float(os.environ.get("AGENT_TIMEOUT_SECONDS", "60"))

        # Configure thread cleanup settings
        self.thread_cleanup_interval_hours = float(os.environ.get("THREAD_CLEANUP_INTERVAL_HOURS", "6"))
        self.thread_retention_days = int(os.environ.get("THREAD_RETENTION_DAYS", "7"))

        # Configure whale alert settings
        self.whale_threshold = float(os.environ.get("WHALE_ALERT_THRESHOLD_USD", "10000"))
        self.whale_alert_channel = os.environ.get("WHALE_ALERT_CHANNEL", "#trading-alerts")
        self.whale_alert_cooldown = {}  # Prevent spam: {trade_id: timestamp}
        self.whale_cooldown_seconds = int(os.environ.get("WHALE_COOLDOWN_SECONDS", "3600"))  # 1 hour default

        # Configure price alerts
        self.price_alert_threshold = float(os.environ.get("PRICE_ALERT_THRESHOLD_PERCENT", "5.0"))
        self.price_alert_channel = os.environ.get("PRICE_ALERT_CHANNEL", "#trading-alerts")
        self.last_price_alert = {}  # Track last alert by direction to prevent spam

        # Configure failure tracking
        self.failure_alert_channel = os.environ.get("FAILURE_ALERT_CHANNEL", "#ops-alerts")
        self.failure_counts = {}  # {component_name: count}
        self.failure_threshold = int(os.environ.get("FAILURE_ALERT_THRESHOLD", "3"))
        self.last_failure_alert = {}  # {component_name: timestamp}
        self.failure_cooldown_minutes = int(os.environ.get("FAILURE_COOLDOWN_MINUTES", "30"))

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
                try:
                    response = await asyncio.wait_for(
                        self.agent.process(
                            message=text,
                            user_id=user,
                            thread_ts=thread_ts
                        ),
                        timeout=self.agent_timeout
                    )
                except asyncio.TimeoutError:
                    logger.warning(f"Agent timeout for user {user}: {text[:50]}")
                    await say(
                        text="I'm taking too long to process that. Please try a simpler question or try again.",
                        thread_ts=thread_ts
                    )
                    return

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
            # Use intelligent error classification
            await say(
                blocks=self.formatter.format_error(e),
                thread_ts=thread_ts
            )

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
            elif subcommand == "health":
                await self._handle_health_check(say)
            elif subcommand == "balance" or subcommand == "bal":
                await self._handle_quick_balance(say)
            elif subcommand == "price" or subcommand == "p":
                await self._handle_price_query(say)
            elif subcommand == "today":
                await self._handle_quick_pnl(say, period="today")
            elif subcommand == "week":
                await self._handle_quick_pnl(say, period="week")
            elif subcommand == "month":
                await self._handle_quick_pnl(say, period="month")
            else:
                # Treat as natural language query
                intent = self.router.classify(text)
                params = self.router.extract_parameters(text, intent)
                await self._route_query(intent, params, user, say)

        except Exception as e:
            logger.error(f"Error handling slash command: {e}", exc_info=True)
            # Use intelligent error classification
            await say(blocks=self.formatter.format_error(e))

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
            # Use intelligent error classification
            await say(blocks=self.formatter.format_error(e))

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
            # Use intelligent error classification
            await say(blocks=self.formatter.format_error(e))

    async def _handle_balance_query(self, say):
        """Handle balance query."""
        logger.info("Balance query")

        try:
            balances = await self.data_provider.get_balances()
            await say(blocks=self.formatter.format_balance_summary(balances))
        except Exception as e:
            logger.error(f"Error querying balances: {e}", exc_info=True)
            # Use intelligent error classification
            await say(blocks=self.formatter.format_error(e))

    async def _handle_quick_balance(self, say):
        """Quick balance summary command."""
        logger.info("Quick balance requested")
        try:
            balances = await self.data_provider.get_balances()

            # Summarize key totals
            total_alkimi = sum(b.get('alkimi', 0) for b in balances.values())
            total_usdt = sum(b.get('usdt', 0) for b in balances.values())
            price = await self.data_provider.get_current_price()
            total_value = total_alkimi * price + total_usdt

            text = f"*Quick Balance*\n"
            text += f"ALKIMI: *{total_alkimi:,.0f}* (${total_alkimi * price:,.2f})\n"
            text += f"USDT: *${total_usdt:,.2f}*\n"
            text += f"*Total:* ${total_value:,.2f}"

            await say(text=text)
        except Exception as e:
            await say(blocks=self.formatter.format_error(e))

    async def _handle_price_query(self, say):
        """Handle price query."""
        logger.info("Price query")

        try:
            price = await self.data_provider.get_current_price()
            if price:
                # Record price for alert detection
                self.data_provider.record_price(price)
            await say(f"💹 Current ALKIMI price: *${price:.6f}*")
        except Exception as e:
            logger.error(f"Error querying price: {e}", exc_info=True)
            # Use intelligent error classification
            await say(blocks=self.formatter.format_error(e))

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
            # Use intelligent error classification
            await say(blocks=self.formatter.format_error(e))

    async def _handle_quick_pnl(self, say, period: str):
        """Quick P&L for specified period."""
        logger.info(f"Quick P&L requested for {period}")
        try:
            now = datetime.now()
            if period == "today":
                since = now.replace(hour=0, minute=0, second=0, microsecond=0)
            elif period == "week":
                since = now - timedelta(days=7)
            elif period == "month":
                since = now - timedelta(days=30)
            else:
                since = None

            report = await self.pnl_calc.calculate(since=since, until=now)

            pnl_emoji = "📈" if report.total_pnl >= 0 else "📉"
            pnl_sign = "+" if report.total_pnl >= 0 else ""

            text = f"{pnl_emoji} *{period.title()} P&L*\n"
            text += f"P&L: *{pnl_sign}${report.total_pnl:,.2f}*\n"
            text += f"Trades: {report.total_trades}"

            await say(text=text)
        except Exception as e:
            await say(blocks=self.formatter.format_error(e))

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
            # Use intelligent error classification
            await say(blocks=self.formatter.format_error(e))

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
            # Use intelligent error classification
            await say(blocks=self.formatter.format_error(e))

    async def _handle_list_functions(self, say):
        """List all saved functions."""
        logger.info("Listing saved functions")

        try:
            functions = await self.functions.list_all()
            await say(blocks=self.formatter.format_function_list(functions))
        except Exception as e:
            logger.error(f"Error listing functions: {e}", exc_info=True)
            # Use intelligent error classification
            await say(blocks=self.formatter.format_error(e))

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
            # Use intelligent error classification
            await say(blocks=self.formatter.format_error(e))

    async def _handle_history(self, user: str, say):
        """Show query history."""
        logger.info(f"Query history requested by {user}")

        try:
            # Get recent history from data provider
            history = await self.data_provider.get_query_history(user_id=user, limit=10)
            await say(blocks=self.formatter.format_query_history(history))
        except Exception as e:
            logger.error(f"Error retrieving history: {e}", exc_info=True)
            # Use intelligent error classification
            await say(blocks=self.formatter.format_error(e))

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
                # Use intelligent error classification
                await say(blocks=self.formatter.format_error(e))
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
                        # Use intelligent error classification
                        await say(blocks=self.formatter.format_error(e))
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
                # Use intelligent error classification
                await say(blocks=self.formatter.format_error(e))

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
                    # Use intelligent error classification
                    await say(blocks=self.formatter.format_error(e))
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

    async def _handle_health_check(self, say):
        """Handle /alkimi health command - show system status."""
        logger.info("Health check requested")

        try:
            # Get health status from data provider
            # (Team 8 added health_check() to DataProvider)
            health = await self.data_provider.health_check()

            # Format as Slack blocks
            blocks = self._format_health_blocks(health)
            await say(blocks=blocks)

        except Exception as e:
            logger.error(f"Error getting health status: {e}", exc_info=True)
            await say(blocks=self.formatter.format_error(
                "Failed to get health status",
                str(e)
            ))

    def _format_health_blocks(self, health) -> List[Dict]:
        """Format health status as Slack blocks."""
        status_emoji = {
            "healthy": "✅",
            "degraded": "⚠️",
            "unhealthy": "❌"
        }

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "System Health Status"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"*Overall:* {status_emoji.get(health.overall_status.value, '❓')} {health.overall_status.value.upper()}"}
            },
            {"type": "divider"}
        ]

        # Add component statuses
        for component in health.components:
            emoji = status_emoji.get(component.status.value, '❓')
            latency = f"{component.latency_ms:.0f}ms" if component.latency_ms else "N/A"

            text = f"{emoji} *{component.name}*: {component.status.value}"
            if component.latency_ms:
                text += f" ({latency})"
            if component.error_message:
                text += f"\n   └ {component.error_message}"

            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": text}
            })

        return blocks

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
            # Use intelligent error classification
            await say(blocks=self.formatter.format_error(e))

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
            # Use intelligent error classification
            await say(blocks=self.formatter.format_error(e))

    def _is_in_cooldown(self, cooldown_key: str, minutes: int = 60) -> bool:
        """
        Check if an alert is in cooldown period.

        Args:
            cooldown_key: Unique key for the alert type (e.g., "price_up", "price_down")
            minutes: Cooldown period in minutes

        Returns:
            True if still in cooldown, False otherwise
        """
        if cooldown_key not in self.last_price_alert:
            return False

        last_alert_time = self.last_price_alert[cooldown_key]
        cooldown_delta = timedelta(minutes=minutes)

        return datetime.now() - last_alert_time < cooldown_delta

    def _set_cooldown(self, cooldown_key: str) -> None:
        """
        Set cooldown timestamp for an alert type.

        Args:
            cooldown_key: Unique key for the alert type
        """
        self.last_price_alert[cooldown_key] = datetime.now()

    async def _check_price_movement(self) -> None:
        """Check for significant price movements and alert if threshold exceeded."""
        try:
            change = self.data_provider.get_price_change(minutes=60)
            if change is None:
                logger.debug("No price change data available yet")
                return

            if abs(change) >= self.price_alert_threshold:
                # Cooldown: only alert once per hour per direction
                direction = "up" if change > 0 else "down"
                cooldown_key = f"price_{direction}"

                if self._is_in_cooldown(cooldown_key, minutes=60):
                    logger.debug(
                        f"Price alert in cooldown for direction '{direction}' "
                        f"(change: {change:+.2f}%)"
                    )
                    return

                await self._send_price_alert(change)
                self._set_cooldown(cooldown_key)

        except Exception as e:
            logger.error(f"Error checking price movement: {e}", exc_info=True)

    async def _send_price_alert(self, change: float) -> None:
        """
        Send price alert to configured Slack channel.

        Args:
            change: Price change percentage
        """
        try:
            direction = "UP" if change > 0 else "DOWN"
            current_price = self.data_provider.price_history[-1][1] if self.data_provider.price_history else None

            if current_price is None:
                logger.warning("Cannot send price alert: no current price available")
                return

            message = f"*PRICE ALERT*\n"
            message += f"ALKIMI is *{direction} {abs(change):.1f}%* in the last hour\n"
            message += f"*Current Price:* ${current_price:.6f}"

            await self.app.client.chat_postMessage(
                channel=self.price_alert_channel,
                text=message
            )

            logger.info(
                f"Sent price alert: {direction} {abs(change):.1f}% to {self.price_alert_channel}"
            )

        except Exception as e:
            logger.error(f"Error sending price alert: {e}", exc_info=True)

    async def check_for_whale_trades(self, since: Optional[datetime] = None):
        """
        Check for whale trades and send alerts.

        Args:
            since: Check trades since this timestamp (default: last 5 minutes)
        """
        try:
            # Default to checking last 5 minutes if not specified
            if since is None:
                since = datetime.now() - timedelta(minutes=5)

            # Get recent trades
            trades_df = await self.data_provider.get_trades_df(since=since)

            if trades_df.empty:
                logger.debug("No recent trades found for whale detection")
                return

            # Check each trade for whale threshold
            whale_count = 0
            for _, trade in trades_df.iterrows():
                value_usd = trade['amount'] * trade['price']

                if value_usd >= self.whale_threshold:
                    # Generate unique trade ID
                    trade_id = f"{trade['exchange']}_{trade.get('trade_id', trade['timestamp'])}"

                    # Check cooldown (don't alert same trade twice)
                    if trade_id in self.whale_alert_cooldown:
                        last_alert_time = self.whale_alert_cooldown[trade_id]
                        time_since_alert = (datetime.now() - last_alert_time).total_seconds()
                        if time_since_alert < self.whale_cooldown_seconds:
                            logger.debug(f"Skipping whale alert for {trade_id} (cooldown active)")
                            continue

                    # Send alert
                    await self._send_whale_alert(trade, value_usd)

                    # Update cooldown
                    self.whale_alert_cooldown[trade_id] = datetime.now()
                    whale_count += 1

                    # Log the whale detection
                    logger.info(
                        f"WHALE_DETECTED | exchange={trade['exchange']} | "
                        f"side={trade['side']} | amount={trade['amount']:,.0f} | "
                        f"price=${trade['price']:.6f} | value=${value_usd:,.2f}"
                    )

            if whale_count > 0:
                logger.info(f"Sent {whale_count} whale alert(s)")

            # Cleanup old cooldown entries (older than cooldown period)
            self._cleanup_whale_cooldown()

        except Exception as e:
            logger.error(f"Error checking for whale trades: {e}", exc_info=True)

    async def _send_whale_alert(self, trade: Dict, value_usd: float):
        """
        Send whale trade alert to configured channel.

        Args:
            trade: Trade data dictionary (from pandas Series)
            value_usd: USD value of the trade
        """
        try:
            # Format side emoji and color
            if trade['side'].lower() == 'buy':
                side_emoji = "🟢"
            else:
                side_emoji = "🔴"

            # Format timestamp
            if isinstance(trade['timestamp'], str):
                timestamp = datetime.fromisoformat(trade['timestamp'].replace('Z', '+00:00'))
            else:
                timestamp = trade['timestamp']

            # Create rich Slack message with blocks
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": f"{side_emoji} WHALE ALERT",
                        "emoji": True
                    }
                },
                {
                    "type": "section",
                    "fields": [
                        {
                            "type": "mrkdwn",
                            "text": f"*Side:*\n{side_emoji} {trade['side'].upper()}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Value:*\n${value_usd:,.2f}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Amount:*\n{trade['amount']:,.0f} ALKIMI"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Price:*\n${trade['price']:.6f}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Exchange:*\n{trade['exchange']}"
                        },
                        {
                            "type": "mrkdwn",
                            "text": f"*Time:*\n{timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}"
                        }
                    ]
                },
                {
                    "type": "context",
                    "elements": [
                        {
                            "type": "mrkdwn",
                            "text": f"Threshold: ${self.whale_threshold:,.0f} | Trade ID: {trade.get('trade_id', 'N/A')}"
                        }
                    ]
                }
            ]

            # Send message using app.client.chat_postMessage
            await self.app.client.chat_postMessage(
                channel=self.whale_alert_channel,
                text=f"{side_emoji} WHALE ALERT: {trade['side'].upper()} {trade['amount']:,.0f} ALKIMI @ ${trade['price']:.6f} (${value_usd:,.2f}) on {trade['exchange']}",
                blocks=blocks
            )

            logger.info(f"Whale alert sent to {self.whale_alert_channel}")

        except Exception as e:
            logger.error(f"Error sending whale alert: {e}", exc_info=True)

    def _cleanup_whale_cooldown(self):
        """Remove old entries from whale cooldown cache."""
        try:
            current_time = datetime.now()
            expired_ids = [
                trade_id for trade_id, alert_time in self.whale_alert_cooldown.items()
                if (current_time - alert_time).total_seconds() > self.whale_cooldown_seconds
            ]

            for trade_id in expired_ids:
                del self.whale_alert_cooldown[trade_id]

            if expired_ids:
                logger.debug(f"Cleaned up {len(expired_ids)} expired whale cooldown entries")
        except Exception as e:
            logger.error(f"Error cleaning up whale cooldown: {e}", exc_info=True)

    async def record_failure(self, component: str, error: str):
        """
        Record a component failure and alert if threshold reached.

        Args:
            component: Name of the failing component (e.g., "data_refresh", "exchange_api")
            error: Error message or description
        """
        try:
            self.failure_counts[component] = self.failure_counts.get(component, 0) + 1

            logger.warning(
                f"FAILURE_RECORDED | component={component} | "
                f"count={self.failure_counts[component]} | error={error[:100]}"
            )

            # Check if we should alert
            if self.failure_counts[component] >= self.failure_threshold:
                # Check cooldown
                last_alert = self.last_failure_alert.get(component)
                if last_alert:
                    elapsed = (datetime.now() - last_alert).total_seconds() / 60
                    if elapsed < self.failure_cooldown_minutes:
                        logger.debug(
                            f"Failure alert in cooldown for {component} "
                            f"(elapsed: {elapsed:.1f}m, cooldown: {self.failure_cooldown_minutes}m)"
                        )
                        return  # Still in cooldown

                await self._send_failure_alert(component, error, self.failure_counts[component])
                self.last_failure_alert[component] = datetime.now()

        except Exception as e:
            logger.error(f"Error recording failure for {component}: {e}", exc_info=True)

    async def record_success(self, component: str):
        """
        Record successful operation, reset failure count.

        Args:
            component: Name of the component that succeeded
        """
        try:
            if component in self.failure_counts:
                previous_count = self.failure_counts[component]

                if previous_count >= self.failure_threshold:
                    # Service recovered - send recovery alert
                    await self._send_recovery_alert(component)
                    logger.info(f"RECOVERY | component={component} | previous_failures={previous_count}")

                # Reset failure count
                self.failure_counts[component] = 0

        except Exception as e:
            logger.error(f"Error recording success for {component}: {e}", exc_info=True)

    async def _send_failure_alert(self, component: str, error: str, count: int):
        """
        Send failure alert to ops channel.

        Args:
            component: Name of the failing component
            error: Error message
            count: Number of consecutive failures
        """
        try:
            logger.warning(f"Sending failure alert for {component}: {error}")

            # Truncate error message if too long
            error_display = error[:200] + "..." if len(error) > 200 else error

            message = f"⚠️ *SYSTEM ALERT*\n"
            message += f"Component: *{component}*\n"
            message += f"Status: ❌ *FAILING*\n"
            message += f"Consecutive failures: {count}\n"
            message += f"Error: `{error_display}`\n"
            message += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"

            await self.app.client.chat_postMessage(
                channel=self.failure_alert_channel,
                text=message
            )

            logger.info(f"Failure alert sent to {self.failure_alert_channel} for {component}")

        except Exception as e:
            logger.error(f"Error sending failure alert: {e}", exc_info=True)

    async def _send_recovery_alert(self, component: str):
        """
        Send recovery alert when service comes back up.

        Args:
            component: Name of the recovered component
        """
        try:
            logger.info(f"Sending recovery alert for {component}")

            message = f"✅ *RECOVERY ALERT*\n"
            message += f"Component: *{component}*\n"
            message += f"Status: ✅ *RECOVERED*\n"
            message += f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"

            await self.app.client.chat_postMessage(
                channel=self.failure_alert_channel,
                text=message
            )

            logger.info(f"Recovery alert sent to {self.failure_alert_channel} for {component}")

        except Exception as e:
            logger.error(f"Error sending recovery alert: {e}", exc_info=True)

    async def _start_background_tasks(self):
        """Start background maintenance tasks."""
        asyncio.create_task(self._periodic_thread_cleanup())
        asyncio.create_task(self._periodic_price_monitoring())
        logger.info(
            f"Started background tasks: thread cleanup every "
            f"{self.thread_cleanup_interval_hours} hours, price monitoring every 1 minute"
        )

    async def _periodic_price_monitoring(self):
        """Periodically fetch price and check for significant movements (every 1 minute)."""
        while True:
            try:
                # Fetch current price
                price = await self.data_provider.get_current_price()
                if price:
                    # Record price for history
                    self.data_provider.record_price(price)

                    # Check for significant movements and alert if needed
                    await self._check_price_movement()

                # Sleep for 1 minute before next check
                await asyncio.sleep(60)

            except Exception as e:
                logger.error(f"Price monitoring failed: {e}", exc_info=True)
                # Wait before retrying
                await asyncio.sleep(60)

    async def _periodic_thread_cleanup(self):
        """Periodically cleanup old threads (every N hours based on config)."""
        while True:
            await asyncio.sleep(self.thread_cleanup_interval_hours * 60 * 60)
            try:
                # Remove threads older than N days from memory
                # Keep in database for history
                cleaned = await self._cleanup_stale_threads(days=self.thread_retention_days)
                if cleaned > 0:
                    logger.info(
                        f"Background cleanup: removed {cleaned} stale threads "
                        f"(older than {self.thread_retention_days} days)"
                    )
            except Exception as e:
                logger.error(f"Thread cleanup failed: {e}", exc_info=True)

    async def _cleanup_stale_threads(self, days: int) -> int:
        """
        Clean up threads older than N days from memory.

        Args:
            days: Remove threads older than this many days from active_threads set

        Returns:
            Number of threads removed from memory
        """
        try:
            # Get list of stale thread IDs from database
            stale_threads = await self.data_provider.get_stale_threads(days=days)

            if not stale_threads:
                logger.debug("No stale threads to clean up")
                return 0

            # Remove from in-memory set
            cleaned_count = 0
            for thread_ts in stale_threads:
                if thread_ts in self.active_threads:
                    self.active_threads.remove(thread_ts)
                    cleaned_count += 1

            # Optionally mark threads as inactive in database (keeping for history)
            # Note: We don't delete from database, just remove from active memory
            if cleaned_count > 0:
                logger.info(
                    f"Cleaned {cleaned_count} stale threads from memory "
                    f"(retained in database for history)"
                )

            return cleaned_count

        except Exception as e:
            logger.error(f"Error during thread cleanup: {e}", exc_info=True)
            return 0

    async def start(self):
        """Start the bot in Socket Mode."""
        try:
            # Start background maintenance tasks
            await self._start_background_tasks()

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
