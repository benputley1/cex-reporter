"""
Simplified Position Report Formatter for Slack

Clean, focused daily report format.
"""

from typing import Dict
from datetime import datetime


class SimpleFormatter:
    """Formats simplified position reports for Slack."""

    def format_report(self, report_data: Dict) -> Dict:
        """
        Format simplified report for Slack Block Kit.

        Args:
            report_data: Report from SimpleTracker

        Returns:
            Slack Block Kit formatted message
        """
        blocks = []

        # Header
        report_date = report_data['report_date'].strftime("%B %d, %Y")
        blocks.append({
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"📊 Alkimi Treasury Report - {report_date}"
            }
        })

        blocks.append({"type": "divider"})

        # Section 1: Current Holdings by Exchange
        holdings_text = self._format_holdings(report_data['holdings_by_exchange'], report_data['total_balances'])
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": holdings_text
            }
        })

        blocks.append({"type": "divider"})

        # Section 1.5: Cetus DeFi Positions (if available)
        if 'Cetus' in report_data['holdings_by_exchange']:
            cetus_text = self._format_cetus_positions(report_data['holdings_by_exchange']['Cetus'])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": cetus_text
                }
            })
            blocks.append({"type": "divider"})

        # Section 2: Daily Change
        daily_change = report_data.get('daily_change', {})
        if daily_change.get('available'):
            daily_text = self._format_daily_change(daily_change, report_data.get('today_activity', {}))
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": daily_text
                }
            })
        else:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": (
                        "*📅 Daily Change*\n"
                        f"_{daily_change.get('message', 'No historical data available')}_"
                    )
                }
            })

        blocks.append({"type": "divider"})

        # Section 3: Monthly Performance Windows (November first, then October)
        monthly_windows = report_data.get('monthly_windows', {})

        # Display November first (most recent month)
        if 'november' in monthly_windows:
            nov_text = self._format_monthly_window(monthly_windows['november'])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": nov_text
                }
            })
            blocks.append({"type": "divider"})

        # Display October second
        if 'october' in monthly_windows:
            oct_text = self._format_monthly_window(monthly_windows['october'])
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": oct_text
                }
            })
            blocks.append({"type": "divider"})

        # Section 4: CEX vs DEX Breakdown (if DEX data available)
        cex_dex = report_data.get('cex_dex_breakdown', {})
        if cex_dex.get('dex', {}).get('trade_count', 0) > 0:
            cex_dex_text = self._format_cex_dex_breakdown(cex_dex)
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": cex_dex_text
                }
            })
            blocks.append({"type": "divider"})

        # Section 4.5: On-Chain Analytics (if available)
        onchain = report_data.get('onchain_analytics', {})
        if onchain.get('pools') or onchain.get('holders'):
            onchain_text = self._format_onchain_analytics(onchain)
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": onchain_text
                }
            })
            blocks.append({"type": "divider"})

        # Section 5: Token Revenue Target (November only)
        token_revenue = report_data.get('token_revenue_target', {})
        if token_revenue.get('available'):
            revenue_text = self._format_token_revenue_target(token_revenue)
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": revenue_text
                }
            })

        return {"blocks": blocks}

    def _format_holdings(self, holdings_by_exchange: Dict, total_balances: Dict) -> str:
        """Format holdings by exchange section with free/locked breakdown."""
        lines = ["*💼 Current Holdings by Exchange*\n"]
        lines.append("═" * 40 + "\n")

        # Track total free and locked across all exchanges
        total_free = {'USDT': 0.0, 'ALKIMI': 0.0}
        total_locked = {'USDT': 0.0, 'ALKIMI': 0.0}

        # Sort exchanges alphabetically (skip Cetus - handled separately)
        for exchange_name in sorted(holdings_by_exchange.keys()):
            # Skip Cetus - it has its own section
            if exchange_name == 'Cetus':
                continue
            data = holdings_by_exchange[exchange_name]
            account_count = len(data['accounts'])

            # Exchange header
            account_text = f"{account_count} account" if account_count == 1 else f"{account_count} accounts"
            lines.append(f"*{exchange_name}* ({account_text}):\n")

            # Balances with free/locked breakdown
            usdt = data['USDT']
            alkimi = data['ALKIMI']

            # Track totals
            total_free['USDT'] += usdt['free']
            total_free['ALKIMI'] += alkimi['free']
            total_locked['USDT'] += usdt['locked']
            total_locked['ALKIMI'] += alkimi['locked']

            # USDT breakdown
            if usdt['total'] > 0:
                lines.append(f"  *USDT:*\n")
                lines.append(f"    • Free:      ${usdt['free']:,.2f}\n")
                if usdt['locked'] > 0:
                    lines.append(f"    • In Orders: ${usdt['locked']:,.2f}\n")
                lines.append(f"    • Total:     ${usdt['total']:,.2f}\n")

            # ALKIMI breakdown
            if alkimi['total'] > 0:
                lines.append(f"  *ALKIMI:*\n")
                lines.append(f"    • Free:      {alkimi['free']:,.0f} tokens\n")
                if alkimi['locked'] > 0:
                    lines.append(f"    • In Orders: {alkimi['locked']:,.0f} tokens\n")
                lines.append(f"    • Total:     {alkimi['total']:,.0f} tokens\n")

            if usdt['total'] == 0 and alkimi['total'] == 0:
                lines.append(f"  _No balance_\n")

            lines.append("\n")

        # Totals with free/locked breakdown
        lines.append("─" * 40 + "\n")
        lines.append("*Total Across All Exchanges:*\n")

        # USDT totals
        lines.append(f"*USDT:*\n")
        lines.append(f"  • Free:      ${total_free['USDT']:,.2f}\n")
        if total_locked['USDT'] > 0:
            lines.append(f"  • In Orders: ${total_locked['USDT']:,.2f}\n")
        lines.append(f"  • Total:     ${total_balances['USDT']:,.2f}\n")

        lines.append("\n")

        # ALKIMI totals
        lines.append(f"*ALKIMI:*\n")
        lines.append(f"  • Free:      {total_free['ALKIMI']:,.0f} tokens\n")
        if total_locked['ALKIMI'] > 0:
            lines.append(f"  • In Orders: {total_locked['ALKIMI']:,.0f} tokens\n")
        lines.append(f"  • Total:     {total_balances['ALKIMI']:,.0f} tokens\n")

        return "".join(lines)

    def _format_daily_change(self, daily_change: Dict, today_activity: Dict) -> str:
        """Format daily change section."""
        lines = ["*📅 Daily Change (vs 24h ago)*\n"]
        lines.append("═" * 40 + "\n")

        usdt = daily_change['usdt']
        alkimi = daily_change['alkimi']

        # USDT change
        usdt_emoji = "📈" if usdt['change'] >= 0 else "📉"
        lines.append(
            f"*{usdt_emoji} USDT:* ${usdt['previous']:,.2f} → ${usdt['current']:,.2f} "
            f"({usdt['change']:+,.2f} / {usdt['change_percent']:+.2f}%)\n"
        )

        # ALKIMI change
        alkimi_emoji = "🟢" if alkimi['change'] >= 0 else "🔴"
        lines.append(
            f"*{alkimi_emoji} ALKIMI:* {alkimi['previous']:,.0f} → {alkimi['current']:,.0f} "
            f"({alkimi['change']:+,.0f} / {alkimi['change_percent']:+.2f}%)\n"
        )

        # Today's activity
        lines.append("\n*Today's Activity:*\n")
        if today_activity.get('trade_count', 0) > 0:
            lines.append(
                f"  • {today_activity['trade_count']} trades "
                f"({today_activity['buys']} buys, {today_activity['sells']} sells)\n"
            )
            lines.append(f"  • Fees: ${today_activity['fees']:.2f}\n")
        else:
            lines.append("  • No trades today\n")

        return "".join(lines)

    def _format_monthly_window(self, window_data: Dict) -> str:
        """Format monthly performance window section."""
        month_name = window_data.get('month_name', 'Month')
        start = window_data['start_date'].strftime("%b %d")
        end = window_data['end_date'].strftime("%b %d")
        days = window_data.get('days', 0)

        # Determine if this is current month (MTD) or completed month
        from datetime import datetime
        is_current_month = window_data['end_date'].month == datetime.now().month

        if is_current_month:
            header = f"*📈 {month_name} Performance (MTD - {days} days)*"
        else:
            header = f"*📊 {month_name} Performance ({start} - {end})*"

        lines = [f"{header}\n"]
        lines.append("═" * 40 + "\n")

        # P&L Summary
        trades = window_data['trades']
        lines.append("*Performance Summary:*\n")
        if trades['trade_count'] > 0:
            # Position values
            lines.append(
                f"  • Starting: ${trades['starting_value']:,.2f} "
                f"({trades['starting_balance']:,.0f} @ ${trades['starting_price']:.6f})\n"
            )
            lines.append(
                f"  • Current:  ${trades['current_value']:,.2f} "
                f"({trades['current_balance']:,.0f} @ ${trades['current_price']:.6f})\n"
            )

            # Price change
            price_change_pct = ((trades['current_price'] - trades['starting_price']) / trades['starting_price'] * 100) if trades['starting_price'] > 0 else 0
            price_emoji = "📈" if price_change_pct >= 0 else "📉"
            lines.append(f"  • Price change: {price_emoji} {price_change_pct:+.2f}%\n")

            lines.append("\n")

            # Withdrawals
            if trades.get('withdrawals', 0) > 0:
                lines.append(f"*Withdrawals:* ${trades['withdrawals']:,.2f}\n\n")

            # P&L Metrics
            lines.append("*P&L Breakdown:*\n")

            # Trading P&L (realized from buys/sells)
            trading_pnl = trades.get('pnl_trading', 0)
            trading_emoji = "🟢" if trading_pnl >= 0 else "🔴"
            lines.append(f"  • {trading_emoji} Trading P&L: ${trading_pnl:+,.2f}\n")
            lines.append("    _Realized gains from buy/sell activity_\n")

            # Mark-to-market P&L (overall)
            mtm_pnl = trades.get('pnl_mark_to_market', 0)
            mtm_emoji = "🟢" if mtm_pnl >= 0 else "🔴"
            lines.append(f"  • {mtm_emoji} Mark-to-Market: ${mtm_pnl:+,.2f}\n")
            lines.append("    _Total performance incl. position value change_\n")

            lines.append("\n")

            # Trading activity
            lines.append(f"*Activity:* {trades['trade_count']} trades ")
            lines.append(f"({trades['buys']} buys, {trades['sells']} sells)\n")
            lines.append(f"*Fees:* ${trades['fees']:.2f}\n")
        else:
            lines.append("  • No trades in this period\n")

        return "".join(lines)

    def _format_rolling_25d(self, rolling_data: Dict) -> str:
        """Format rolling window section."""
        start = rolling_data['start_date'].strftime("%b %d")
        end = rolling_data['end_date'].strftime("%b %d")
        days = rolling_data.get('days', 25)  # Default to 25 for backwards compatibility

        lines = [f"*📈 Last {days} Days ({start} - {end})*\n"]
        lines.append("═" * 40 + "\n")

        # P&L Summary
        trades = rolling_data['trades']
        lines.append("*Performance Summary:*\n")
        if trades['trade_count'] > 0:
            # Position values
            lines.append(
                f"  • Starting: ${trades['starting_value']:,.2f} "
                f"({trades['starting_balance']:,.0f} @ ${trades['starting_price']:.6f})\n"
            )
            lines.append(
                f"  • Current:  ${trades['current_value']:,.2f} "
                f"({trades['current_balance']:,.0f} @ ${trades['current_price']:.6f})\n"
            )

            # Price change
            price_change_pct = ((trades['current_price'] - trades['starting_price']) / trades['starting_price'] * 100) if trades['starting_price'] > 0 else 0
            price_emoji = "📈" if price_change_pct >= 0 else "📉"
            lines.append(f"  • Price change: {price_emoji} {price_change_pct:+.2f}%\n")

            lines.append("\n")

            # Withdrawals
            if trades.get('withdrawals', 0) > 0:
                lines.append(f"*Withdrawals:* ${trades['withdrawals']:,.2f}\n\n")

            # P&L Metrics
            lines.append("*P&L Breakdown:*\n")

            # Trading P&L (realized from buys/sells)
            trading_pnl = trades.get('pnl_trading', 0)
            trading_emoji = "🟢" if trading_pnl >= 0 else "🔴"
            lines.append(f"  • {trading_emoji} Trading P&L: ${trading_pnl:+,.2f}\n")
            lines.append("    _Realized gains from buy/sell activity_\n")

            # Mark-to-market P&L (overall)
            mtm_pnl = trades.get('pnl_mark_to_market', 0)
            mtm_emoji = "🟢" if mtm_pnl >= 0 else "🔴"
            lines.append(f"  • {mtm_emoji} Mark-to-Market: ${mtm_pnl:+,.2f}\n")
            lines.append("    _Total performance incl. position value change_\n")

            lines.append("\n")

            # Trading activity
            lines.append(f"*Activity:* {trades['trade_count']} trades ")
            lines.append(f"({trades['buys']} buys, {trades['sells']} sells)\n")
            lines.append(f"*Fees:* ${trades['fees']:.2f}\n")
        else:
            lines.append("  • No trades in this period\n")

        return "".join(lines)

    def _format_token_revenue_target(self, revenue_data: Dict) -> str:
        """Format token revenue target section - compact version."""
        month = revenue_data.get('month', 'Month')
        days_elapsed = revenue_data.get('days_elapsed', 0)
        days_in_month = revenue_data.get('days_in_month', 30)

        revenue = revenue_data.get('revenue', {})
        activity = revenue_data.get('activity', {})
        holdings = revenue_data.get('holdings_by_exchange', {})

        lines = [f"*💰 TOKEN REVENUE TARGET - {month} (Day {days_elapsed}/{days_in_month})*\n\n"]

        # Revenue Progress
        trading_revenue = revenue.get('trading_revenue', 0)
        net_cash_position = revenue.get('net_cash_position', 0)
        target = revenue.get('target', 500000)
        gap = revenue.get('gap', 0)
        daily_avg = revenue.get('daily_avg', 0)
        projected = revenue.get('projected_monthly', 0)
        required_daily = revenue.get('required_daily', 0)
        days_remaining = revenue.get('days_remaining', 0)

        progress_pct = (net_cash_position / target * 100) if target > 0 else 0
        projected_pct = (projected / target * 100) if target > 0 else 0

        lines.append("*REVENUE PROGRESS*\n")
        lines.append(f"Target:          ${target:,.0f}\n")
        lines.append(f"Trading Revenue: ${trading_revenue:,.2f}\n")

        # Show RAMAN OTC if present
        raman_otc = activity.get('raman_otc')
        if raman_otc:
            otc_cost = raman_otc['cost']
            otc_alkimi = raman_otc['alkimi']
            otc_price = raman_otc['price']
            lines.append(f"RAMAN OTC:       -${otc_cost:,.2f} ({otc_alkimi/1_000_000:.0f}M ALKIMI @ ${otc_price:.6f})\n")

        lines.append(f"Net Position:    ${net_cash_position:,.2f} ({progress_pct:.1f}%)\n")
        lines.append(f"Gap:             ${gap:,.0f} remaining\n\n")

        # Daily Performance
        lines.append("*DAILY PERFORMANCE*\n")
        lines.append(f"Average:         ${daily_avg:,.2f}/day\n")
        lines.append(f"Projected:       ${projected:,.0f} ({projected_pct:.1f}% of target)\n")
        if days_remaining > 0:
            lines.append(f"Required:        ${required_daily:,.0f}/day ({days_remaining} days left)\n\n")
        else:
            lines.append("\n")

        # Exchange Balances
        lines.append("*EXCHANGE BALANCES*\n")

        # Sort exchanges alphabetically for consistency
        total_alkimi = 0
        total_usdt = 0
        for exchange_name in sorted(holdings.keys()):
            exchange_data = holdings[exchange_name]
            alkimi_balance = exchange_data.get('ALKIMI', {}).get('total', 0)
            usdt_balance = exchange_data.get('USDT', {}).get('total', 0)
            total_alkimi += alkimi_balance
            total_usdt += usdt_balance
            lines.append(f"{exchange_name}: {alkimi_balance:,.0f} ALKIMI | ${usdt_balance:,.2f} USDT\n")

        lines.append(f"Total: {total_alkimi:,.0f} ALKIMI | ${total_usdt:,.2f} USDT\n\n")

        # Activity summary
        alkimi_sold = activity.get('alkimi_sold', 0)
        lines.append(f"Volume sold: {alkimi_sold:,.0f} ALKIMI\n")

        return "".join(lines)

    def _format_cetus_positions(self, cetus_data: Dict) -> str:
        """Format Cetus DeFi positions section."""
        lines = ["*🌊 Cetus DeFi Positions (Sui Blockchain)*\n"]
        lines.append("═" * 40 + "\n")

        # Get CETUS_LP and CETUS_REWARDS balances
        cetus_lp = cetus_data.get('CETUS_LP', {}).get('total', 0)
        cetus_rewards = cetus_data.get('CETUS_REWARDS', {}).get('total', 0)

        lines.append(f"*Total Liquidity Position:* ${cetus_lp:,.2f}\n")
        lines.append(f"*Pending Rewards:* ${cetus_rewards:,.2f}\n\n")

        # Note about real-time tracking
        lines.append("_DeFi positions tracked in real-time via Sui blockchain_\n")

        return "".join(lines)

    def _format_cex_dex_breakdown(self, breakdown: Dict) -> str:
        """Format CEX vs DEX trading breakdown section."""
        lines = ["*🔄 CEX vs DEX Activity*\n"]
        lines.append("═" * 40 + "\n")

        cex = breakdown.get('cex', {})
        dex = breakdown.get('dex', {})
        total_volume = breakdown.get('total_volume', 0)
        cex_pct = breakdown.get('cex_percentage', 0)
        dex_pct = breakdown.get('dex_percentage', 0)

        # Volume summary
        lines.append("*Volume Distribution:*\n")
        lines.append(f"  • Total: ${total_volume:,.2f}\n")
        lines.append(f"  • CEX: ${cex.get('total_volume', 0):,.2f} ({cex_pct:.1f}%)\n")
        lines.append(f"  • DEX: ${dex.get('total_volume', 0):,.2f} ({dex_pct:.1f}%)\n\n")

        # CEX breakdown by exchange
        if cex.get('by_exchange'):
            lines.append("*CEX Breakdown:*\n")
            # Filter out None keys and sort by exchange name
            cex_items = [(k, v) for k, v in cex['by_exchange'].items() if k is not None]
            for exchange, data in sorted(cex_items, key=lambda x: x[0] or ''):
                lines.append(f"  • {exchange}: {data['count']} trades, ${data['volume']:,.2f}\n")
            lines.append("\n")

        # DEX breakdown by protocol
        if dex.get('by_exchange'):
            lines.append("*DEX Breakdown:*\n")
            # Filter out None keys and sort by protocol name
            dex_items = [(k, v) for k, v in dex['by_exchange'].items() if k is not None]
            for protocol, data in sorted(dex_items, key=lambda x: x[0] or ''):
                lines.append(f"  • {protocol}: {data['count']} trades, ${data['volume']:,.2f}\n")
            lines.append("\n")

        # Activity summary
        lines.append("*Trade Counts:*\n")
        lines.append(f"  • CEX: {cex.get('trade_count', 0)} trades ({cex.get('buy_count', 0)} buys, {cex.get('sell_count', 0)} sells)\n")
        lines.append(f"  • DEX: {dex.get('trade_count', 0)} trades ({dex.get('buy_count', 0)} buys, {dex.get('sell_count', 0)} sells)\n")

        return "".join(lines)

    def _format_onchain_analytics(self, analytics: Dict) -> str:
        """Format on-chain analytics section (pools, holders, whale tracking)."""
        lines = ["*⛓️ ALKIMI On-Chain Analytics (Sui)*\n"]
        lines.append("═" * 40 + "\n")

        # Liquidity Pools
        pools = analytics.get('pools', [])
        if pools:
            total_tvl = sum(p.get('tvl_usd', 0) for p in pools)
            total_volume = sum(p.get('volume_24h', 0) for p in pools)

            lines.append("*Liquidity Pools:*\n")
            lines.append(f"  • Total TVL: ${total_tvl:,.2f}\n")
            lines.append(f"  • 24h Volume: ${total_volume:,.2f}\n\n")

            # Top pools by TVL
            sorted_pools = sorted(pools, key=lambda x: x.get('tvl_usd', 0), reverse=True)
            for pool in sorted_pools[:5]:
                dex = pool.get('dex', 'Unknown')
                name = pool.get('name', 'Unknown')
                tvl = pool.get('tvl_usd', 0)
                price = pool.get('price', 0)
                fee = pool.get('fee_tier', '')
                fee_str = f" ({fee})" if fee else ""
                lines.append(f"  • {dex}{fee_str}: ${tvl:,.0f} TVL @ ${price:.6f}\n")

            lines.append("\n")

        # Top Holders
        holders = analytics.get('holders', [])
        if holders:
            lines.append("*Top Holders:*\n")

            # Calculate concentration
            top_5_pct = sum(h.get('percentage', 0) for h in holders[:5])
            top_10_pct = sum(h.get('percentage', 0) for h in holders[:10])

            for i, holder in enumerate(holders[:5], 1):
                addr = holder.get('address', 'Unknown')
                # Truncate address for display
                short_addr = f"{addr[:8]}...{addr[-6:]}" if len(addr) > 16 else addr
                balance = holder.get('balance', 0)
                pct = holder.get('percentage', 0)
                lines.append(f"  {i}. {short_addr}: {balance:,.0f} ({pct:.2f}%)\n")

            lines.append(f"\n  _Top 5 concentration: {top_5_pct:.1f}%_\n")
            if len(holders) >= 10:
                lines.append(f"  _Top 10 concentration: {top_10_pct:.1f}%_\n")

            lines.append("\n")

        # Watched Wallets
        watched = analytics.get('watched_wallets', [])
        if watched:
            lines.append("*Watched Wallets:*\n")
            for wallet in watched:
                addr = wallet.get('address', 'Unknown')
                short_addr = f"{addr[:8]}...{addr[-6:]}" if len(addr) > 16 else addr
                balance = wallet.get('balance', 0)
                tx_count = wallet.get('transaction_count', 0)
                net_change = wallet.get('net_change', 0)

                change_emoji = "📈" if net_change > 0 else "📉" if net_change < 0 else "➖"
                lines.append(f"  • {short_addr}:\n")
                lines.append(f"    Balance: {balance:,.0f} ALKIMI\n")
                lines.append(f"    Txns: {tx_count} | Net: {change_emoji} {net_change:+,.0f}\n")

            lines.append("\n")

        # Timestamp
        timestamp = analytics.get('timestamp')
        if timestamp:
            if isinstance(timestamp, str):
                lines.append(f"_Updated: {timestamp}_\n")
            else:
                lines.append(f"_Updated: {timestamp.strftime('%Y-%m-%d %H:%M UTC')}_\n")

        return "".join(lines)
