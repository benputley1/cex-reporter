"""
Position Report Formatter for Slack

Formats position tracking and trading performance data for Slack messages.
"""

from typing import Dict
from datetime import datetime


class PositionFormatter:
    """Formats position tracking data into Slack Block Kit messages."""

    def format_position_report(self, position_data: Dict) -> Dict:
        """
        Format comprehensive position report for Slack.

        Args:
            position_data: Position report from PositionTracker

        Returns:
            Slack Block Kit formatted message
        """
        usdt = position_data['usdt_position']
        alkimi = position_data['alkimi_position']
        trading = position_data['trading_performance']
        summary = position_data['summary']

        blocks = []

        # Header
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📊 Alkimi Treasury Position Report"
            }
        })

        blocks.append({"type": "divider"})

        # Daily Change (Last 24h)
        daily = position_data.get('daily_change', {})
        if daily:
            daily_usdt = daily.get('usdt', {})
            daily_alkimi = daily.get('alkimi', {})
            daily_trading = daily.get('trading', {})

            usdt_emoji = "📈" if daily_usdt.get('change', 0) >= 0 else "📉"
            alkimi_emoji = "🟢" if daily_alkimi.get('change', 0) >= 0 else "🔴"

            # Build trading text with note if no trades
            trading_text = (
                f"*Trading:* {daily_trading.get('total_trades', 0)} trades "
                f"({daily_trading.get('buy_count', 0)} buys, {daily_trading.get('sell_count', 0)} sells)\n"
            )

            if daily_trading.get('total_trades', 0) == 0:
                trading_text += f"_No trading activity in the last 24 hours_"
            else:
                trading_text += (
                    f"• Realized P&L: ${daily_trading.get('realized_pnl', 0):+,.2f}\n"
                    f"• Fees: ${daily_trading.get('fees', 0):.2f}"
                )

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*📅 Daily Change (Last 24h)*\n"
                        f"\n"
                        f"*{usdt_emoji} USDT:* ${daily_usdt.get('previous', 0):,.2f} → ${daily_usdt.get('current', 0):,.2f} "
                        f"({daily_usdt.get('change', 0):+,.2f} / {daily_usdt.get('change_percent', 0):+.2f}%)\n"
                        f"*{alkimi_emoji} ALKIMI:* {daily_alkimi.get('previous', 0):,.0f} → {daily_alkimi.get('current', 0):,.0f} "
                        f"({daily_alkimi.get('change', 0):+,.0f} / {daily_alkimi.get('change_percent', 0):+.2f}%)\n"
                        f"\n"
                        f"{trading_text}"
                    )
                }
            })

            blocks.append({"type": "divider"})

        # Monthly Breakdown
        monthly = position_data.get('monthly_breakdown', {})
        if monthly and monthly.get('months'):
            monthly_lines = ["*📈 Monthly Performance*\n"]

            for month_data in monthly['months']:
                month_name = month_data['month']
                trades = month_data['trades']
                prices = month_data.get('prices', {})
                cash_flow = month_data.get('cash_flow', {})
                volume = month_data.get('volume', {})
                inventory = month_data.get('inventory', {})

                # Add (MTD) indicator for current month
                if month_data.get('is_current'):
                    month_name = f"{month_name} (MTD)"

                # Visual separator and month header
                monthly_lines.append(f"\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n")
                monthly_lines.append(f"*{month_name}*\n")
                monthly_lines.append(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n")

                # Cash flow (most important metric first)
                if cash_flow.get('net') is not None:
                    net = cash_flow['net']
                    monthly_lines.append(f"Cash:      ${net:+,.0f} net\n")

                # P&L
                pnl = month_data['realized_pnl']
                monthly_lines.append(f"P&L:       ${pnl:+,.2f} realized\n")

                # ALKIMI inventory change
                if inventory:
                    net_change = inventory.get('net_change', 0)
                    monthly_lines.append(f"ALKIMI:    {net_change:+,.0f} tokens\n")

                # Trading activity
                if trades['total'] > 0:
                    buys = trades['buys']
                    sells = trades['sells']
                    if buys > 0 and sells > 0:
                        trade_str = f"{trades['total']} trades ({buys} buys, {sells} sells)"
                    elif buys > 0:
                        trade_str = f"{buys} buys"
                    else:
                        trade_str = f"{sells} sells"
                    monthly_lines.append(f"Trades:    {trade_str}\n")

                # Fees
                fees = month_data['fees']
                monthly_lines.append(f"Fees:      ${fees:.2f}\n")

                # Withdrawals (if any)
                withdrawals = month_data.get('withdrawals', {})
                if withdrawals and withdrawals.get('total_amount', 0) > 0:
                    total_w = withdrawals['total_amount']
                    count_w = withdrawals['count']
                    monthly_lines.append(f"Withdraw:  ${total_w:,.2f} ({count_w} txns)\n")

                # Add pricing details if both buys and sells occurred
                if prices.get('weighted_avg_buy', 0) > 0 and prices.get('weighted_avg_sell', 0) > 0:
                    monthly_lines.append(
                        f"\nPricing:   Buy ${prices['weighted_avg_buy']:.4f} | "
                        f"Sell ${prices['weighted_avg_sell']:.4f}\n"
                    )

            # Add explanatory note at the bottom
            monthly_lines.append(
                f"\n_ℹ️ P&L uses FIFO accounting and may include inventory from prior months._"
            )

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "".join(monthly_lines)
                }
            })

            blocks.append({"type": "divider"})

        # Overall Position Section Header
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*📊 Overall Position (Since Aug 15)*"
            }
        })

        # USDT Position
        usdt_emoji = "📈" if usdt['total_change'] >= 0 else "📉"
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{usdt_emoji} USDT Position*\n"
                    f"• Starting: {usdt['starting_balance']:,.2f} USDT\n"
                    f"• Current: {usdt['current_balance']:,.2f} USDT\n"
                    f"• Change: {usdt['total_change']:+,.2f} USDT ({usdt['change_percent']:+.2f}%)\n"
                    f"\n"
                    f"*From ALKIMI Trading:*\n"
                    f"• Spent: -{usdt['trading_activity']['spent_on_alkimi']:,.2f} USDT\n"
                    f"• Received: +{usdt['trading_activity']['received_from_alkimi']:,.2f} USDT\n"
                    f"• Net: {usdt['trading_activity']['net_from_trading']:+,.2f} USDT"
                )
            }
        })

        blocks.append({"type": "divider"})

        # ALKIMI Position
        alkimi_emoji = "🟢" if alkimi['quantity_change'] >= 0 else "🔴"
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{alkimi_emoji} ALKIMI Position*\n"
                    f"• Starting: {alkimi['starting_balance']:,.0f} ALKIMI\n"
                    f"• Current: {alkimi['current_balance']:,.0f} ALKIMI\n"
                    f"• Quantity Change: {alkimi['quantity_change']:+,.0f} ({alkimi['quantity_change_percent']:+.2f}%)\n"
                    f"\n"
                    f"*Value:*\n"
                    f"• Starting Value: ${alkimi['starting_value_usd']:,.2f} @ ${alkimi['starting_price']:.4f}\n"
                    f"• Current Value: ${alkimi['current_value_usd']:,.2f} @ ${alkimi['current_price']:.4f}\n"
                    f"• Value Change: ${alkimi['value_change_usd']:+,.2f} ({alkimi['value_change_percent']:+.2f}%)\n"
                    f"• Price Change: ${alkimi['price_change']:+.4f} ({alkimi['price_change_percent']:+.2f}%)"
                )
            }
        })

        blocks.append({"type": "divider"})

        # Trading Performance
        profit_emoji = "💰" if trading['realized_profit']['profit_usd'] >= 0 else "⚠️"
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{profit_emoji} ALKIMI Trading Performance*\n"
                    f"\n"
                    f"*Purchases:*\n"
                    f"• {trading['buys']['count']} trades\n"
                    f"• {trading['buys']['total_quantity']:,.0f} ALKIMI\n"
                    f"• Avg Buy Price: ${trading['buys']['average_price']:.4f}\n"
                    f"• Total Cost: ${trading['buys']['total_cost_usd']:,.2f}\n"
                    f"\n"
                    f"*Sales:*\n"
                    f"• {trading['sells']['count']} trades\n"
                    f"• {trading['sells']['total_quantity']:,.0f} ALKIMI\n"
                    f"• Avg Sale Price: ${trading['sells']['average_price']:.4f}\n"
                    f"• Total Revenue: ${trading['sells']['total_revenue_usd']:,.2f}\n"
                    f"\n"
                    f"*Realized Profit:*\n"
                    f"• ${trading['realized_profit']['profit_usd']:+,.2f} ({trading['realized_profit']['profit_percent']:+.2f}%)\n"
                    f"• Avg Spread: ${trading['realized_profit']['spread']:+.4f} ({trading['realized_profit']['spread_percent']:+.2f}%)"
                )
            }
        })

        blocks.append({"type": "divider"})

        # Fee Analysis
        fees = position_data['fee_analysis']
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*💳 Trading Fees*\n"
                    f"• Total Fees Paid: ${fees['total_fees_usd']:,.2f}\n"
                    f"• Fees as % of Volume: {fees['fee_as_percent_of_volume']:.3f}%\n"
                    f"• Avg Fee per Trade: ${fees['avg_fee_per_trade']:.2f}\n"
                    f"• Buy Fees: ${fees['buy_fees_usd']:,.2f}\n"
                    f"• Sell Fees: ${fees['sell_fees_usd']:,.2f}"
                )
            }
        })

        blocks.append({"type": "divider"})

        # Deposits & Withdrawals
        dep_with = position_data.get('deposit_withdrawal_summary', {})
        if dep_with and dep_with.get('total_transactions', 0) > 0:
            usdt_data = dep_with.get('usdt', {})
            alkimi_data = dep_with.get('alkimi', {})

            deposit_emoji = "📥"
            withdrawal_emoji = "📤"

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        f"*{deposit_emoji} Deposits & Withdrawals*\n"
                        f"\n"
                        f"*USDT:*\n"
                        f"• Deposits: +{usdt_data.get('total_deposits', 0):,.2f} USDT ({usdt_data.get('deposit_count', 0)} transactions)\n"
                        f"• Withdrawals: -{usdt_data.get('total_withdrawals', 0):,.2f} USDT ({usdt_data.get('withdrawal_count', 0)} transactions)\n"
                        f"• Net Flow: {usdt_data.get('net_flow', 0):+,.2f} USDT\n"
                        f"\n"
                        f"*ALKIMI:*\n"
                        f"• Deposits: +{alkimi_data.get('total_deposits', 0):,.0f} ALKIMI ({alkimi_data.get('deposit_count', 0)} transactions)\n"
                        f"• Withdrawals: -{alkimi_data.get('total_withdrawals', 0):,.0f} ALKIMI ({alkimi_data.get('withdrawal_count', 0)} transactions)\n"
                        f"• Net Flow: {alkimi_data.get('net_flow', 0):+,.0f} ALKIMI"
                    )
                }
            })

            blocks.append({"type": "divider"})

        # Exchange Breakdown
        exchanges = position_data['exchange_breakdown']
        if exchanges:
            exchange_lines = ["*🏦 Holdings by Exchange*"]
            for ex_name, ex_data in sorted(exchanges.items()):
                if ex_data['alkimi_balance'] > 0 or ex_data['usdt_balance'] > 0:
                    exchange_lines.append(
                        f"• *{ex_name.upper()}*: "
                        f"{ex_data['alkimi_balance']:,.0f} ALKIMI (${ex_data['alkimi_value_usd']:,.2f}) | "
                        f"{ex_data['usdt_balance']:,.2f} USDT"
                    )
                    exchange_lines.append(
                        f"  └ {ex_data['trade_count']} trades, "
                        f"${ex_data['total_volume_usd']:,.2f} volume, "
                        f"${ex_data['fees_paid_usd']:.2f} fees"
                    )

            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "\n".join(exchange_lines)
                }
            })

            blocks.append({"type": "divider"})

        # Summary
        total_value = summary['current_portfolio_value']
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*📊 Summary*\n"
                    f"• Total Portfolio Value: ${total_value:,.2f}\n"
                    f"• USDT: ${usdt['current_balance']:,.2f}\n"
                    f"• ALKIMI: ${alkimi['current_value_usd']:,.2f}\n"
                    f"\n"
                    f"• Realized Profit: ${summary['realized_profit']:+,.2f}\n"
                    f"• Total Fees: ${summary['total_fees_paid']:,.2f}\n"
                    f"• Net Profit: ${summary['net_profit_after_fees']:+,.2f}\n"
                    f"• Total Trades: {summary['total_trades']}"
                )
            }
        })

        # Timestamp
        timestamp = datetime.fromisoformat(position_data['timestamp']).strftime('%Y-%m-%d %H:%M:%S UTC')
        blocks.append({
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": f"🔔 Report generated at {timestamp}"
                }
            ]
        })

        return {"blocks": blocks}

    def format_position_summary(self, position_data: Dict) -> Dict:
        """
        Format a condensed position summary for quick updates.

        Args:
            position_data: Position report from PositionTracker

        Returns:
            Slack Block Kit formatted message (condensed)
        """
        summary = position_data['summary']
        usdt = position_data['usdt_position']
        alkimi = position_data['alkimi_position']

        blocks = []

        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": "📊 Quick Position Update"
            }
        })

        blocks.append({
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Portfolio Value*\n${summary['current_portfolio_value']:,.2f}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Realized Profit*\n${summary['realized_profit']:+,.2f}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*USDT Change*\n{usdt['total_change']:+,.2f} ({usdt['change_percent']:+.2f}%)"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*ALKIMI Change*\n{alkimi['quantity_change']:+,.0f} ({alkimi['quantity_change_percent']:+.2f}%)"
                },
            ]
        })

        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*Trading:* {summary['total_trades']} trades | "
                    f"Avg Buy: ${summary['alkimi_avg_buy_price']:.4f} | "
                    f"Avg Sell: ${summary['alkimi_avg_sell_price']:.4f}"
                )
            }
        })

        timestamp = datetime.fromisoformat(position_data['timestamp']).strftime('%H:%M:%S UTC')
        blocks.append({
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": f"Updated: {timestamp}"}
            ]
        })

        return {"blocks": blocks}
