#!/usr/bin/env python3
"""
Example: Position Tracker Report

Demonstrates the new position-focused reporting that tracks:
- USDT position changes
- ALKIMI quantity and value changes
- Average buy/sell prices
- Realized profit from trading
"""

import asyncio
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.analytics.position_tracker import PositionTracker
from src.reporting.position_formatter import PositionFormatter
from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient


async def main():
    print("=" * 70)
    print("POSITION TRACKER EXAMPLE (Mock Mode)")
    print("=" * 70)
    print()

    # Initialize exchanges in mock mode
    exchanges = [
        MEXCClient(mock_mode=True),
        KrakenClient(mock_mode=True),
        KuCoinClient(mock_mode=True),
        GateioClient(mock_mode=True),
    ]

    # Initialize all exchanges
    for exchange in exchanges:
        await exchange.initialize()

    # Create position tracker
    tracker = PositionTracker()

    print("Generating position report...")
    print()

    # Generate position report
    report = await tracker.get_position_report(exchanges)

    # Display the report
    print_position_report(report)

    print()
    print("=" * 70)
    print("SLACK MESSAGE PREVIEW")
    print("=" * 70)
    print()

    # Format for Slack
    formatter = PositionFormatter()
    slack_message = formatter.format_position_report(report)

    # Print Slack blocks as text
    print_slack_message(slack_message)

    # Cleanup
    for exchange in exchanges:
        await exchange.close()


def print_position_report(report: dict):
    """Print position report in readable format."""

    usdt = report['usdt_position']
    alkimi = report['alkimi_position']
    trading = report['trading_performance']
    summary = report['summary']

    print("📊 USDT POSITION")
    print("-" * 70)
    print(f"  Starting Balance:     {usdt['starting_balance']:>15,.2f} USDT")
    print(f"  Current Balance:      {usdt['current_balance']:>15,.2f} USDT")
    print(f"  Total Change:         {usdt['total_change']:>+15,.2f} USDT ({usdt['change_percent']:+.2f}%)")
    print()
    print("  From ALKIMI Trading:")
    print(f"    Spent on purchases: -{usdt['trading_activity']['spent_on_alkimi']:>14,.2f} USDT")
    print(f"    Received from sales:+{usdt['trading_activity']['received_from_alkimi']:>14,.2f} USDT")
    print(f"    Net from trading:    {usdt['trading_activity']['net_from_trading']:>+14,.2f} USDT")
    print()

    print("🟢 ALKIMI POSITION")
    print("-" * 70)
    print(f"  Starting Balance:     {alkimi['starting_balance']:>15,.0f} ALKIMI")
    print(f"  Current Balance:      {alkimi['current_balance']:>15,.0f} ALKIMI")
    print(f"  Quantity Change:      {alkimi['quantity_change']:>+15,.0f} ALKIMI ({alkimi['quantity_change_percent']:+.2f}%)")
    print()
    print("  Value:")
    print(f"    Starting:           ${alkimi['starting_value_usd']:>14,.2f} @ ${alkimi['starting_price']:.4f}")
    print(f"    Current:            ${alkimi['current_value_usd']:>14,.2f} @ ${alkimi['current_price']:.4f}")
    print(f"    Value Change:       ${alkimi['value_change_usd']:>+14,.2f} ({alkimi['value_change_percent']:+.2f}%)")
    print(f"    Price Change:       ${alkimi['price_change']:>+14,.4f} ({alkimi['price_change_percent']:+.2f}%)")
    print()

    print("💰 ALKIMI TRADING PERFORMANCE")
    print("-" * 70)
    print(f"  Purchases:")
    print(f"    Trades:             {trading['buys']['count']:>15} buys")
    print(f"    Quantity:           {trading['buys']['total_quantity']:>15,.0f} ALKIMI")
    print(f"    Average Price:      ${trading['buys']['average_price']:>14.4f}")
    print(f"    Total Cost:         ${trading['buys']['total_cost_usd']:>14,.2f}")
    print()
    print(f"  Sales:")
    print(f"    Trades:             {trading['sells']['count']:>15} sells")
    print(f"    Quantity:           {trading['sells']['total_quantity']:>15,.0f} ALKIMI")
    print(f"    Average Sale Price: ${trading['sells']['average_price']:>14.4f}")
    print(f"    Total Revenue:      ${trading['sells']['total_revenue_usd']:>14,.2f}")
    print()
    print(f"  Realized Profit:")
    print(f"    Profit (USD):       ${trading['realized_profit']['profit_usd']:>+14,.2f}")
    print(f"    Profit (%):         {trading['realized_profit']['profit_percent']:>+15.2f}%")
    print(f"    Avg Spread:         ${trading['realized_profit']['spread']:>+14.4f} ({trading['realized_profit']['spread_percent']:+.2f}%)")
    print()

    print("📊 SUMMARY")
    print("-" * 70)
    print(f"  Total Portfolio Value: ${summary['current_portfolio_value']:,.2f}")
    print(f"    - USDT:              ${usdt['current_balance']:,.2f}")
    print(f"    - ALKIMI:            ${alkimi['current_value_usd']:,.2f}")
    print()
    print(f"  Realized Profit:       ${summary['realized_profit']:+,.2f}")
    print(f"  Total Trades:          {summary['total_trades']}")
    print(f"  Avg Buy Price:         ${summary['alkimi_avg_buy_price']:.4f}")
    print(f"  Avg Sell Price:        ${summary['alkimi_avg_sell_price']:.4f}")
    print()


def print_slack_message(message: dict):
    """Print Slack message blocks as readable text."""

    for block in message['blocks']:
        if block['type'] == 'header':
            print(block['text']['text'])
            print("=" * 70)
        elif block['type'] == 'section':
            if 'text' in block:
                text = block['text']['text'].replace('*', '').replace('_', '')
                print(text)
            if 'fields' in block:
                for field in block['fields']:
                    text = field['text'].replace('*', '').replace('_', '')
                    print(text)
        elif block['type'] == 'divider':
            print("-" * 70)
        elif block['type'] == 'context':
            text = block['elements'][0]['text']
            print(f"\n{text}")
        print()


if __name__ == '__main__':
    asyncio.run(main())
