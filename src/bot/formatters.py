"""
Slack Message Formatters using Block Kit

Formats bot responses using Slack's Block Kit for rich, interactive messages.
"""

from typing import List, Dict, Any, Optional, Union
import pandas as pd
from datetime import datetime
from src.bot.pnl_config import PnLReport
from src.bot.error_classifier import format_error_response, ErrorType
from src.utils import get_logger

logger = get_logger(__name__)


class SlackFormatter:
    """Format responses for Slack Block Kit."""

    def format_pnl_report(self, report: PnLReport) -> List[Dict]:
        """
        Format P&L report as Slack blocks.

        Creates a comprehensive P&L report with:
        - Header with date range
        - Realized P&L breakdown by exchange
        - Unrealized P&L with holdings
        - Net P&L summary

        Args:
            report: PnLReport instance

        Returns:
            List of Slack Block Kit blocks
        """
        blocks = []

        # Header
        period_str = f"{report.period_start.strftime('%b %d')} - {report.period_end.strftime('%b %d, %Y')}"
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📊 P&L REPORT ({period_str})",
                "emoji": True
            }
        })

        blocks.append({"type": "divider"})

        # Realized P&L Section
        realized_emoji = "📈" if report.realized_pnl >= 0 else "📉"
        realized_text = (
            f"{realized_emoji} *REALIZED P&L*\n"
            f"Total: *{self._format_currency(report.realized_pnl)}*\n"
        )

        # Add exchange breakdown
        if report.by_exchange:
            for exchange, pnl in sorted(report.by_exchange.items(), key=lambda x: x[1], reverse=True):
                realized_text += f"  ├─ {exchange}: {self._format_currency(pnl)}\n"
            realized_text += f"\n_Based on {report.trade_count} trades_"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": realized_text
            }
        })

        # Unrealized P&L Section
        unrealized_emoji = "📈" if report.unrealized_pnl >= 0 else "📉"
        unrealized_text = (
            f"{unrealized_emoji} *UNREALIZED P&L*\n"
            f"Holdings: *{self._format_number(report.current_holdings)} ALKIMI*\n"
            f"Avg Cost: ${report.avg_cost_per_token:.6f}\n"
            f"Current: ${report.current_price:.6f}\n"
            f"Unrealized: *{self._format_currency(report.unrealized_pnl)}*"
        )

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": unrealized_text
            }
        })

        blocks.append({"type": "divider"})

        # Net P&L Summary
        net_emoji = "🎯" if report.net_pnl >= 0 else "⚠️"
        net_color = "good" if report.net_pnl >= 0 else "danger"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{net_emoji} *NET P&L: {self._format_currency(report.net_pnl)}*"
            }
        })

        return blocks

    def format_table(self, data: Union[pd.DataFrame, List], title: str = None, max_rows: int = 10) -> List[Dict]:
        """
        Format data as Slack table with improved styling.

        Args:
            data: DataFrame or list to format
            title: Optional table title
            max_rows: Maximum rows to display

        Returns:
            List of Slack Block Kit blocks
        """
        blocks = []

        if title:
            blocks.append({
                "type": "header",
                "text": {"type": "plain_text", "text": title}
            })

        # Convert DataFrame or list to formatted text
        if isinstance(data, pd.DataFrame):
            df = data

            if df.empty:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "_No data found_"
                    }
                })
                return blocks

            # Format as monospace text for alignment
            table_text = "```\n"

            # Limit columns to first 5 for readability
            display_cols = df.columns[:5]
            display_df = df[display_cols].head(max_rows)

            # Header row
            header = " | ".join(f"{col:>12}"[:12] for col in display_cols)
            table_text += header + "\n"
            table_text += "-" * len(header) + "\n"

            # Data rows
            for idx, row in display_df.iterrows():
                row_text = " | ".join(f"{str(val):>12}"[:12] for val in row.values)
                table_text += row_text + "\n"

            table_text += "```"

            blocks.append({
                "type": "section",
                "text": {"type": "mrkdwn", "text": table_text}
            })

            # Truncation warning
            if len(df) > max_rows or len(df.columns) > 5:
                warning_parts = []
                if len(df) > max_rows:
                    warning_parts.append(f"Showing {max_rows} of {len(df)} rows")
                if len(df.columns) > 5:
                    warning_parts.append(f"Showing 5 of {len(df.columns)} columns")

                blocks.append({
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": f"_{' • '.join(warning_parts)}_"
                    }]
                })

        return blocks

    def format_trade_list(self, trades: pd.DataFrame, max_trades: int = 10) -> List[Dict]:
        """
        Format trade list with enhanced visual details.

        Args:
            trades: DataFrame of trades
            max_trades: Maximum trades to display

        Returns:
            List of Slack Block Kit blocks
        """
        blocks = []

        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"💱 Recent Trades ({len(trades)} total)",
                "emoji": True
            }
        })

        if trades.empty:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No trades found_"
                }
            })
            return blocks

        blocks.append({"type": "divider"})

        # Show summary stats first
        total_volume = (trades['amount'] * trades['price']).sum()
        avg_price = trades['price'].mean()

        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Total Volume:*\n`${total_volume:,.2f}`"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Avg Price:*\n`${avg_price:.6f}`"
                }
            ]
        })

        blocks.append({"type": "divider"})

        # Format individual trades
        for idx, trade in enumerate(trades.head(max_trades).iterrows()):
            _, trade = trade  # Unpack tuple from iterrows()
            side_emoji = "🟢" if trade.get('side', 'buy').lower() == 'buy' else "🔴"
            side_text = "BUY" if trade.get('side', 'buy').lower() == 'buy' else "SELL"
            exchange = trade.get('exchange', 'Unknown')
            timestamp = trade.get('timestamp', '')
            if isinstance(timestamp, pd.Timestamp):
                timestamp = timestamp.strftime('%b %d, %H:%M')

            amount = trade.get('amount', 0)
            price = trade.get('price', 0)
            total = amount * price

            trade_text = (
                f"{side_emoji} *{side_text}* on {exchange.upper()}\n"
                f"`{amount:,.0f}` ALKIMI @ `${price:.6f}` = `${total:,.2f}`\n"
                f"_{timestamp}_"
            )

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": trade_text
                }
            })

            # Add divider between trades (except after last one)
            if idx < min(max_trades, len(trades)) - 1:
                blocks.append({"type": "divider"})

        if len(trades) > max_trades:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_Showing {max_trades} of {len(trades)} trades_"
                    }
                ]
            })

        return blocks

    def format_balance_summary(self, balances: Dict) -> List[Dict]:
        """
        Format balance summary by exchange with improved card layout.

        Args:
            balances: Dict of exchange -> {currency -> amount}

        Returns:
            List of Slack Block Kit blocks
        """
        blocks = []

        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "💰 Current Balances",
                "emoji": True
            }
        })

        if not balances:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No balances found_"
                }
            })
            return blocks

        # Add divider for visual separation
        blocks.append({"type": "divider"})

        # Use format_balance_card for each exchange
        for i, (exchange, assets) in enumerate(balances.items()):
            # Try to use the card format if it has standard currencies
            if 'alkimi' in assets or 'usdt' in assets:
                blocks.append(self.format_balance_card(exchange, assets))
            else:
                # Fallback to original format for non-standard currencies
                balance_text = f"*{exchange.upper()}*\n"
                for currency, amount in sorted(assets.items()):
                    if amount > 0:
                        balance_text += f"  • {currency.upper()}: `{self._format_number(amount)}`\n"

                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": balance_text
                    }
                })

            # Add divider between exchanges (except after last one)
            if i < len(balances) - 1:
                blocks.append({"type": "divider"})

        return blocks

    def format_error(
        self,
        error: Union[str, Exception],
        suggestion: str = None,
        preserve_details: bool = False
    ) -> List[Dict]:
        """
        Format error message with actionable guidance.

        This method now supports intelligent error classification when
        an Exception is passed. It categorizes errors and provides
        user-friendly messages with recovery suggestions.

        Args:
            error: Error message (str) or Exception to classify
            suggestion: Optional custom suggestion (overrides auto-suggestion)
            preserve_details: If True and error is Exception, include technical details

        Returns:
            List of Slack Block Kit blocks

        Example:
            >>> try:
            ...     # some code that raises an exception
            ... except Exception as e:
            ...     blocks = formatter.format_error(e)
            ...     # Returns user-friendly message with recovery steps
        """
        blocks = []

        # If error is an Exception, use the classifier
        if isinstance(error, Exception):
            logger.info(
                f"Classifying error: {type(error).__name__}: {str(error)}",
                exc_info=preserve_details
            )

            # Get user-friendly message and suggestion
            user_message, auto_suggestion = format_error_response(
                error,
                preserve_details=preserve_details
            )

            # Use custom suggestion if provided, otherwise use auto-generated
            final_suggestion = suggestion or auto_suggestion

            error_text = user_message
        else:
            # Backwards compatibility: treat as string
            error_text = str(error)
            final_suggestion = suggestion

        # Create error block
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"❌ *Error*\n{error_text}"
            }
        })

        # Add suggestion if available
        if final_suggestion:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"💡 _{final_suggestion}_"
                    }
                ]
            })

        return blocks

    def format_success(self, message: str, details: str = None) -> List[Dict]:
        """
        Format success message.

        Args:
            message: Success message
            details: Optional details

        Returns:
            List of Slack Block Kit blocks
        """
        blocks = []

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"✅ {message}"
            }
        })

        if details:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": details
                    }
                ]
            })

        return blocks

    def format_code(self, code: str, language: str = "python") -> List[Dict]:
        """
        Format code block.

        Args:
            code: Code to format
            language: Programming language

        Returns:
            List of Slack Block Kit blocks
        """
        return [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{language}\n{code}\n```"
                }
            }
        ]

    def format_function_list(self, functions: List) -> List[Dict]:
        """
        Format list of saved functions.

        Args:
            functions: List of function records

        Returns:
            List of Slack Block Kit blocks
        """
        blocks = []

        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📚 Saved Functions",
                "emoji": True
            }
        })

        if not functions:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No saved functions yet_\n\nCreate one with `/alkimi create <description>`"
                }
            })
            return blocks

        for func in functions:
            func_name = func.get('name', 'unknown')
            description = func.get('description', 'No description')
            usage_count = func.get('usage_count', 0)
            created_at = func.get('created_at', '')

            func_text = (
                f"*`{func_name}`*\n"
                f"{description}\n"
                f"_Used {usage_count} times • Created {created_at}_"
            )

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": func_text
                }
            })

        return blocks

    def format_query_history(self, history: List) -> List[Dict]:
        """
        Format query history list.

        Args:
            history: List of query records

        Returns:
            List of Slack Block Kit blocks
        """
        blocks = []

        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📜 Query History",
                "emoji": True
            }
        })

        if not history:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No query history yet_"
                }
            })
            return blocks

        for query in history[:10]:  # Show last 10
            query_text = query.get('query_text', '')
            query_type = query.get('query_type', 'unknown')
            timestamp = query.get('timestamp', '')
            success = query.get('success', False)

            emoji = "✅" if success else "❌"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"{emoji} *{query_type}* - {timestamp}\n`{query_text[:100]}`"
                }
            })

        return blocks

    def format_help(self) -> List[Dict]:
        """
        Format help message with available commands.

        Returns:
            List of Slack Block Kit blocks
        """
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "🤖 ALKIMI Bot Help",
                    "emoji": True
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Natural Language Queries*\nJust ask me about your trades in plain English!"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "• _\"What's our P&L this month?\"_\n"
                        "• _\"Show trades over $5K\"_\n"
                        "• _\"Current ALKIMI balance\"_\n"
                        "• _\"Best performing exchange yesterday\"_"
                    )
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Quick Commands*\nFast access to common queries:"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "`balance` or `bal` - Quick balance summary\n"
                        "`price` or `p` - Current ALKIMI price\n"
                        "`today` - Today's P&L\n"
                        "`week` - Last 7 days P&L\n"
                        "`month` - Last 30 days P&L"
                    )
                }
            },
            {"type": "divider"},
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*Slash Commands*\nUse `/alkimi` followed by:"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "`pnl` - P&L report\n"
                        "`sql <query>` - Run SQL query\n"
                        "`run <name>` - Run saved function\n"
                        "`functions` - List saved functions\n"
                        "`create <description>` - Create new function\n"
                        "`history` - Query history\n"
                        "`config` - P&L configuration\n"
                        "`otc` - OTC transaction management\n"
                        "`health` - System health status\n"
                        "`help` - Show this help"
                    )
                }
            },
            {"type": "divider"},
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": "💡 Tip: Mention me with @alkimi-bot or DM me directly!"
                    }
                ]
            }
        ]

    def format_config(self, config: Dict) -> List[Dict]:
        """
        Format P&L configuration display.

        Args:
            config: Configuration dictionary

        Returns:
            List of Slack Block Kit blocks
        """
        blocks = []

        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "⚙️ P&L Configuration",
                "emoji": True
            }
        })

        cost_basis = config.get('cost_basis_method', 'FIFO')
        updated_by = config.get('updated_by', 'system')
        updated_at = config.get('updated_at', 'unknown')

        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Cost Basis Method:*\n{cost_basis}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Updated By:*\n{updated_by}"
                }
            ]
        })

        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"Last updated: {updated_at}"
                }
            ]
        })

        blocks.append({"type": "divider"})

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    "*Available Methods:*\n"
                    "• `FIFO` - First In, First Out\n"
                    "• `LIFO` - Last In, First Out\n"
                    "• `AVG` - Average Cost\n\n"
                    "Change with: `/alkimi config cost-basis <method>`"
                )
            }
        })

        return blocks

    def format_value(self, value: float, prefix: str = "$") -> str:
        """
        Format value with color coding (positive/negative).

        Args:
            value: Value to format
            prefix: Prefix symbol (default: $)

        Returns:
            Formatted value string with color indicator
        """
        if value >= 0:
            return f"🟢 +{prefix}{value:,.2f}"
        else:
            return f"🔴 {prefix}{value:,.2f}"

    def format_pnl_summary(self, pnl: float, trades: int, period: str) -> List[Dict]:
        """
        Format P&L summary with visual indicators.

        Args:
            pnl: P&L amount
            trades: Number of trades
            period: Time period description

        Returns:
            List of Slack Block Kit blocks
        """
        emoji = "📈" if pnl >= 0 else "📉"
        color = "good" if pnl >= 0 else "danger"

        return [{
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji} *{period} P&L*\n{self.format_value(pnl)}\n{trades} trades"
            }
        }]

    def format_sparkline(self, values: List[float]) -> str:
        """
        Generate simple ASCII sparkline for trends.

        Args:
            values: List of numeric values

        Returns:
            ASCII sparkline string
        """
        if not values:
            return ""

        min_val, max_val = min(values), max(values)
        if min_val == max_val:
            return "─" * len(values)

        chars = "▁▂▃▄▅▆▇█"
        normalized = [(v - min_val) / (max_val - min_val) for v in values]
        return "".join(chars[int(n * 7)] for n in normalized)

    def format_balance_card(self, exchange: str, balances: Dict) -> Dict:
        """
        Format single exchange balance as a card.

        Args:
            exchange: Exchange name
            balances: Dict of currency -> amount

        Returns:
            Slack Block Kit section block
        """
        alkimi = balances.get('alkimi', 0)
        usdt = balances.get('usdt', 0)

        return {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{exchange.upper()}*\nALKIMI: `{alkimi:,.0f}`\nUSDT: `${usdt:,.2f}`"
            }
        }

    def _format_currency(self, amount: float) -> str:
        """
        Format as currency with +/- sign.

        Args:
            amount: Amount to format

        Returns:
            Formatted currency string
        """
        sign = "+" if amount >= 0 else ""
        return f"{sign}${amount:,.2f}"

    def _format_number(self, num: float) -> str:
        """
        Format large numbers with commas.

        Args:
            num: Number to format

        Returns:
            Formatted number string
        """
        return f"{num:,.2f}"
