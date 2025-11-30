"""
Slack Message Formatter Module

Provides SlackFormatter class for formatting various types of messages
in Slack Block Kit format, including portfolio updates, alerts, and error notifications.
"""

from typing import Dict, Any, List, Optional
from datetime import datetime


class SlackFormatter:
    """
    Formats messages for Slack using Block Kit format.

    Provides methods to format different types of messages including
    portfolio updates, alerts, daily summaries, and error notifications.
    """

    @staticmethod
    def format_portfolio_update(portfolio_data: Dict, pnl_data: Dict) -> Dict:
        """
        Format portfolio update message using Slack Block Kit.

        Args:
            portfolio_data: Dictionary containing portfolio information
                {
                    'total_value_usd': float,
                    'assets': [{'symbol': str, 'amount': float, 'usd_value': float}],
                    'exchanges': [{'name': str, 'total_usd': float, 'assets': [...]}]
                }
            pnl_data: Dictionary containing P&L information
                {
                    '24h': {'value': float, 'percentage': float},
                    '7d': {'value': float, 'percentage': float},
                    'total': {'value': float, 'percentage': float}
                }

        Returns:
            Dictionary containing Slack Block Kit formatted message
        """
        blocks = []

        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📊 Alkimi Treasury Report",
                "emoji": True
            }
        })

        # Timestamp
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_Generated at {timestamp}_"
                }
            ]
        })

        blocks.append({"type": "divider"})

        # Total Portfolio Value
        total_value = portfolio_data.get('total_value_usd', 0)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"💰 *Total Portfolio Value*\n`${total_value:,.2f} USD`"
            }
        })

        blocks.append({"type": "divider"})

        # Per-Asset Breakdown
        assets = portfolio_data.get('assets', {})
        if assets:
            asset_lines = ["*📈 Asset Breakdown*"]
            for symbol, asset_data in assets.items():
                amount = asset_data.get('total_amount', 0)
                usd_value = asset_data.get('usd_value', 0)
                price = asset_data.get('price', 0)
                percentage = asset_data.get('percentage', 0)
                asset_lines.append(
                    f"• *{symbol}*: {amount:,.4f} @ ${price:.4f} = ${usd_value:,.2f} ({percentage:.1f}%)"
                )

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(asset_lines)
                }
            })

            blocks.append({"type": "divider"})

        # Per-Exchange Distribution
        exchanges = portfolio_data.get('exchanges', [])
        if exchanges:
            exchange_lines = ["*🏦 Exchange Distribution*"]
            for exchange in exchanges:
                name = exchange.get('name', 'Unknown').upper()
                total_usd = exchange.get('total_usd', 0)
                percentage = (total_usd / total_value * 100) if total_value > 0 else 0
                exchange_lines.append(
                    f"• *{name}*: ${total_usd:,.2f} ({percentage:.1f}%)"
                )

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(exchange_lines)
                }
            })

            blocks.append({"type": "divider"})

        # P&L Summary
        pnl_lines = ["*📊 Profit & Loss Summary*"]

        # 24h P&L
        pnl_24h = pnl_data.get('24h', {})
        value_24h = pnl_24h.get('value', 0)
        pct_24h = pnl_24h.get('percentage', 0)
        emoji_24h = "🟢" if value_24h >= 0 else "🔴"
        sign_24h = "+" if value_24h >= 0 else ""
        pnl_lines.append(
            f"{emoji_24h} *24h*: {sign_24h}${value_24h:,.2f} ({sign_24h}{pct_24h:.2f}%)"
        )

        # 7d P&L
        pnl_7d = pnl_data.get('7d', {})
        value_7d = pnl_7d.get('value', 0)
        pct_7d = pnl_7d.get('percentage', 0)
        emoji_7d = "🟢" if value_7d >= 0 else "🔴"
        sign_7d = "+" if value_7d >= 0 else ""
        pnl_lines.append(
            f"{emoji_7d} *7d*: {sign_7d}${value_7d:,.2f} ({sign_7d}{pct_7d:.2f}%)"
        )

        # Total P&L
        pnl_total = pnl_data.get('total', {})
        value_total = pnl_total.get('value', 0)
        pct_total = pnl_total.get('percentage', 0)
        emoji_total = "🟢" if value_total >= 0 else "🔴"
        sign_total = "+" if value_total >= 0 else ""
        pnl_lines.append(
            f"{emoji_total} *Total*: {sign_total}${value_total:,.2f} ({sign_total}{pct_total:.2f}%)"
        )

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "\n".join(pnl_lines)
            }
        })

        return {"blocks": blocks}

    @staticmethod
    def format_alert(alert_type: str, message: str, data: Dict) -> Dict:
        """
        Format alert message using Slack Block Kit.

        Args:
            alert_type: Type of alert (price_change, error, significant_movement)
            message: Alert message text
            data: Additional data relevant to the alert

        Returns:
            Dictionary containing Slack Block Kit formatted message
        """
        blocks = []

        # Alert header with emoji based on type
        alert_emoji = {
            'price_change': '📉',
            'error': '⚠️',
            'significant_movement': '🚨'
        }.get(alert_type, '🔔')

        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{alert_emoji} Alert: {alert_type.replace('_', ' ').title()}",
                "emoji": True
            }
        })

        # Timestamp
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_Triggered at {timestamp}_"
                }
            ]
        })

        blocks.append({"type": "divider"})

        # Main message
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🚨 *{message}*"
            }
        })

        # Additional data if provided
        if data:
            data_lines = ["*Details:*"]
            for key, value in data.items():
                # Format key to be more readable
                readable_key = key.replace('_', ' ').title()
                # Format value based on type
                if isinstance(value, float):
                    if abs(value) >= 1000:
                        formatted_value = f"${value:,.2f}" if 'usd' in key.lower() or 'value' in key.lower() else f"{value:,.2f}"
                    else:
                        formatted_value = f"{value:.4f}"
                elif isinstance(value, (int, bool)):
                    formatted_value = str(value)
                else:
                    formatted_value = str(value)

                data_lines.append(f"• *{readable_key}*: {formatted_value}")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(data_lines)
                }
            })

        return {"blocks": blocks}

    @staticmethod
    def format_daily_summary(
        portfolio_data: Dict,
        pnl_data: Dict,
        stats: Dict
    ) -> Dict:
        """
        Format comprehensive daily summary message.

        Args:
            portfolio_data: Dictionary containing portfolio information
            pnl_data: Dictionary containing P&L information
            stats: Dictionary containing additional statistics
                {
                    'trading_volume': float,
                    'top_movers': [{'symbol': str, 'change_pct': float}],
                    'total_trades': int
                }

        Returns:
            Dictionary containing Slack Block Kit formatted message
        """
        blocks = []

        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📊 Daily Treasury Summary",
                "emoji": True
            }
        })

        # Date
        date_str = datetime.utcnow().strftime("%Y-%m-%d")
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_Report Date: {date_str}_"
                }
            ]
        })

        blocks.append({"type": "divider"})

        # Portfolio Overview
        total_value = portfolio_data.get('total_value_usd', 0)
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"💰 *Total Portfolio Value*\n`${total_value:,.2f} USD`"
            }
        })

        blocks.append({"type": "divider"})

        # P&L Summary
        pnl_24h = pnl_data.get('24h', {})
        value_24h = pnl_24h.get('value', 0)
        pct_24h = pnl_24h.get('percentage', 0)
        emoji_24h = "📈" if value_24h >= 0 else "📉"
        sign_24h = "+" if value_24h >= 0 else ""

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{emoji_24h} *24h Performance*\n{sign_24h}${value_24h:,.2f} ({sign_24h}{pct_24h:.2f}%)"
            }
        })

        # Trading Statistics
        trading_volume = stats.get('trading_volume', 0)
        total_trades = stats.get('total_trades', 0)

        if trading_volume > 0 or total_trades > 0:
            blocks.append({"type": "divider"})
            stats_lines = ["*📊 Trading Activity*"]
            if total_trades > 0:
                stats_lines.append(f"• Total Trades: {total_trades}")
            if trading_volume > 0:
                stats_lines.append(f"• Trading Volume: ${trading_volume:,.2f}")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(stats_lines)
                }
            })

        # Top Movers
        top_movers = stats.get('top_movers', [])
        if top_movers:
            blocks.append({"type": "divider"})
            movers_lines = ["*🔥 Top Movers (24h)*"]
            for mover in top_movers[:5]:  # Limit to top 5
                symbol = mover.get('symbol', 'UNKNOWN')
                change_pct = mover.get('change_pct', 0)
                emoji = "🟢" if change_pct >= 0 else "🔴"
                sign = "+" if change_pct >= 0 else ""
                movers_lines.append(f"{emoji} *{symbol}*: {sign}{change_pct:.2f}%")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(movers_lines)
                }
            })

        return {"blocks": blocks}

    @staticmethod
    def format_error_notification(error: Exception, context: Dict) -> Dict:
        """
        Format error notification message.

        Args:
            error: Exception object
            context: Dictionary containing error context
                {
                    'component': str,
                    'operation': str,
                    'timestamp': str,
                    'additional_info': dict
                }

        Returns:
            Dictionary containing Slack Block Kit formatted message
        """
        blocks = []

        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "⚠️ Error Notification",
                "emoji": True
            }
        })

        # Timestamp
        timestamp = context.get('timestamp') or datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"_Occurred at {timestamp}_"
                }
            ]
        })

        blocks.append({"type": "divider"})

        # Error details
        component = context.get('component', 'Unknown')
        operation = context.get('operation', 'Unknown')

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"🚨 *Error in {component}*\nOperation: `{operation}`"
            }
        })

        # Error message
        error_type = type(error).__name__
        error_message = str(error)

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Error Type:* `{error_type}`\n*Message:* {error_message}"
            }
        })

        # Stack trace in code block
        import traceback
        stack_trace = ''.join(traceback.format_exception(type(error), error, error.__traceback__))

        # Truncate stack trace if too long (Slack has message limits)
        if len(stack_trace) > 2000:
            stack_trace = stack_trace[:2000] + "\n... (truncated)"

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Stack Trace:*\n```{stack_trace}```"
            }
        })

        # Additional context
        additional_info = context.get('additional_info', {})
        if additional_info:
            blocks.append({"type": "divider"})
            info_lines = ["*Additional Context:*"]
            for key, value in additional_info.items():
                readable_key = key.replace('_', ' ').title()
                info_lines.append(f"• *{readable_key}*: {value}")

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(info_lines)
                }
            })

        return {"blocks": blocks}
