"""
Slack Message Formatters using Block Kit

Formats bot responses using Slack's Block Kit for rich, interactive messages.
"""

from typing import List, Dict, Any, Optional
import pandas as pd
from datetime import datetime
from src.bot.pnl_config import PnLReport


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

    def format_table(self, df: pd.DataFrame, title: str = None, max_rows: int = 10) -> List[Dict]:
        """
        Format DataFrame as Slack table using code block for alignment.

        Args:
            df: DataFrame to format
            title: Optional table title
            max_rows: Maximum rows to display

        Returns:
            List of Slack Block Kit blocks
        """
        blocks = []

        if title:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*{title}*"
                }
            })

        if df.empty:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "_No data found_"
                }
            })
            return blocks

        # Truncate if too many rows
        display_df = df.head(max_rows)
        truncated = len(df) > max_rows

        # Format as monospaced table
        table_str = display_df.to_string(index=False, max_rows=max_rows)

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"```\n{table_str}\n```"
            }
        })

        if truncated:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"_Showing {max_rows} of {len(df)} rows_"
                    }
                ]
            })

        return blocks

    def format_trade_list(self, trades: pd.DataFrame, max_trades: int = 10) -> List[Dict]:
        """
        Format trade list with details.

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

        # Show summary stats first
        total_volume = (trades['amount'] * trades['price']).sum()
        avg_price = trades['price'].mean()

        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Total Volume:*\n${total_volume:,.2f}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Avg Price:*\n${avg_price:.6f}"
                }
            ]
        })

        blocks.append({"type": "divider"})

        # Format individual trades
        for _, trade in trades.head(max_trades).iterrows():
            side_emoji = "🟢" if trade.get('side', 'buy').lower() == 'buy' else "🔴"
            exchange = trade.get('exchange', 'Unknown')
            timestamp = trade.get('timestamp', '')
            if isinstance(timestamp, pd.Timestamp):
                timestamp = timestamp.strftime('%Y-%m-%d %H:%M')

            amount = trade.get('amount', 0)
            price = trade.get('price', 0)
            total = amount * price

            trade_text = (
                f"{side_emoji} *{exchange}* - {timestamp}\n"
                f"  {amount:,.0f} ALKIMI @ ${price:.6f} = ${total:,.2f}"
            )

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": trade_text
                }
            })

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
        Format balance summary by exchange.

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

        for exchange, assets in balances.items():
            balance_text = f"*{exchange}*\n"
            for currency, amount in sorted(assets.items()):
                if amount > 0:
                    balance_text += f"  • {currency}: {self._format_number(amount)}\n"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": balance_text
                }
            })

        return blocks

    def format_error(self, error: str, suggestion: str = None) -> List[Dict]:
        """
        Format error message with optional suggestion.

        Args:
            error: Error message
            suggestion: Optional suggestion for fixing the error

        Returns:
            List of Slack Block Kit blocks
        """
        blocks = []

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"❌ *Error*\n{error}"
            }
        })

        if suggestion:
            blocks.append({
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",
                        "text": f"💡 _{suggestion}_"
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
