#!/usr/bin/env python3
"""
Calculate Accurate P&L Using Deposits & Withdrawals
Uses actual CEX Reporter position data combined with Excel deposits/withdrawals.
"""

import sys
import os
from datetime import datetime
from collections import defaultdict
import pandas as pd
import asyncio

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from config.settings import settings
from src.analytics.position_tracker import PositionTracker
from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient

async def initialize_exchanges():
    """Initialize all exchange clients."""
    exchanges = []

    # MEXC
    for account in settings.mexc_accounts:
        if account['account_name'] == 'MM1':
            continue
        try:
            client = MEXCClient(account['apiKey'], account['secret'])
            exchanges.append((f"MEXC_{account['account_name']}", client))
        except:
            pass

    # Kraken
    for account in settings.kraken_accounts:
        try:
            client = KrakenClient(account['apiKey'], account['secret'])
            exchanges.append((f"Kraken_{account['account_name']}", client))
        except:
            pass

    # KuCoin
    for account in settings.kucoin_accounts:
        try:
            client = KuCoinClient(account['apiKey'], account['secret'], account['password'])
            exchanges.append((f"KuCoin_{account['account_name']}", client))
        except:
            pass

    # Gate.io
    for account in settings.gateio_accounts:
        try:
            client = GateioClient(account['apiKey'], account['secret'])
            exchanges.append((f"Gateio_{account['account_name']}", client))
        except:
            pass

    return exchanges

async def main():
    """Calculate accurate P&L using deposits & withdrawals data."""

    excel_file = '/Users/ben/Desktop/cex-reporter/deposits & withdrawals.xlsx'

    print("=" * 80)
    print("ACCURATE P&L CALCULATION")
    print("Using Deposits & Withdrawals Data + CEX Reporter Position")
    print("=" * 80)
    print()

    # ========================================================================
    # Step 1: Load Deposits (Starting ALKIMI Inventory)
    # ========================================================================
    print("📥 STEP 1: Loading ALKIMI Deposits (Starting Inventory)")
    print("─" * 80)

    df_deposits = pd.read_excel(excel_file, sheet_name='Deposits od ALKIMI to exchanges')

    total_starting_alkimi = 0
    total_starting_usd_value = 0

    deposits_by_exchange = defaultdict(lambda: {'alkimi': 0, 'usd_value': 0})

    for _, row in df_deposits.iterrows():
        destination = row['Destination']
        amount = row['Amount']
        usd_value = row['USD Amount']

        deposits_by_exchange[destination]['alkimi'] += amount
        deposits_by_exchange[destination]['usd_value'] += usd_value

        total_starting_alkimi += amount
        total_starting_usd_value += usd_value

    for exchange in sorted(deposits_by_exchange.keys()):
        data = deposits_by_exchange[exchange]
        avg_price = data['usd_value'] / data['alkimi']
        print(f"{exchange:25s}: {data['alkimi']:>15,.0f} ALKIMI @ ${avg_price:.6f} = ${data['usd_value']:>12,.2f}")

    print(f"{'─' * 80}")
    print(f"{'TOTAL STARTING INVENTORY':25s}: {total_starting_alkimi:>15,.0f} ALKIMI = ${total_starting_usd_value:>12,.2f}")
    print()

    # ========================================================================
    # Step 2: Load Withdrawals
    # ========================================================================
    print("📤 STEP 2: Loading Stablecoin Withdrawals (Profits Taken)")
    print("─" * 80)

    df_withdrawals = pd.read_excel(excel_file, sheet_name='Stablecoin Withdrawals from Exc')

    withdrawals_by_month = defaultdict(float)
    total_withdrawals = 0

    for _, row in df_withdrawals.iterrows():
        date = pd.to_datetime(row['DateTime (UTC)'])
        amount = row['Amount']
        month_key = date.strftime('%Y-%m')
        withdrawals_by_month[month_key] += amount
        total_withdrawals += amount

    # Remove duplicates (amounts that appear twice)
    # Based on the earlier output, Unknown duplicates the identified exchanges
    # So we need to divide by 2
    actual_total_withdrawals = total_withdrawals / 2
    for month in withdrawals_by_month:
        withdrawals_by_month[month] /= 2

    for month_key in sorted(withdrawals_by_month.keys()):
        print(f"{month_key}: ${withdrawals_by_month[month_key]:>12,.2f}")

    print(f"{'─' * 80}")
    print(f"TOTAL WITHDRAWALS: ${actual_total_withdrawals:>12,.2f}")
    print()

    # ========================================================================
    # Step 3: Get Current Position from CEX Reporter
    # ========================================================================
    print("💰 STEP 3: Getting Current Position from CEX Reporter")
    print("─" * 80)

    exchanges = await initialize_exchanges()
    exchange_clients = [ex[1] for ex in exchanges]

    position_tracker = PositionTracker()

    try:
        report = await position_tracker.get_position_report(exchange_clients)

        current_usdt = report['usdt_position']['current_balance']
        current_alkimi = report['alkimi_position']['current_balance']
        current_alkimi_price = report['alkimi_position'].get('current_price', 0)
        current_alkimi_value = report['alkimi_position']['current_value_usd']

        print(f"USDT Balance:       ${current_usdt:>15,.2f}")
        print(f"ALKIMI Balance:     {current_alkimi:>15,.0f}")
        print(f"ALKIMI Price:       ${current_alkimi_price:>15,.6f}")
        print(f"ALKIMI Value:       ${current_alkimi_value:>15,.2f}")
        print(f"{'─' * 80}")
        print(f"Total on Exchanges: ${current_usdt + current_alkimi_value:>15,.2f}")
        print()

        # ========================================================================
        # Step 4: Trading Performance by Month
        # ========================================================================
        print("📊 STEP 4: Trading Performance by Month")
        print("─" * 80)

        if 'monthly_breakdown' in report and 'months' in report['monthly_breakdown']:
            for month_data in report['monthly_breakdown']['months']:
                month_name = month_data['month']
                trades = month_data['trades']
                prices = month_data['prices']
                cash_flow = month_data['cash_flow']
                realized_pnl = month_data['realized_pnl']

                # Get corresponding withdrawals
                month_key = month_data['month_key']
                month_withdrawal = withdrawals_by_month.get(month_key, 0)

                print(f"\n{month_name}:")
                print(f"  Trades:      {trades['total']} total ({trades['buys']} buys, {trades['sells']} sells)")
                print(f"  Cash Flow:   ${cash_flow['net']:>12,.2f} (spent ${cash_flow['spent_on_buys']:,.2f}, received ${cash_flow['received_from_sells']:,.2f})")
                print(f"  Realized P&L: ${realized_pnl:>12,.2f}")
                if month_withdrawal > 0:
                    print(f"  Withdrawn:    ${month_withdrawal:>12,.2f}")

        # ========================================================================
        # Step 5: Complete Reconciliation
        # ========================================================================
        print("\n\n")
        print("=" * 80)
        print("COMPLETE P&L RECONCILIATION")
        print("=" * 80)

        print(f"\n📥 STARTING POSITION (From Excel):")
        avg_deposit_price = total_starting_usd_value / total_starting_alkimi
        print(f"   ALKIMI deposited:        {total_starting_alkimi:>15,.0f} @ ${avg_deposit_price:.6f}")
        print(f"   Initial value:           ${total_starting_usd_value:>15,.2f}")

        print(f"\n📊 TRADING ACTIVITY (From CEX Reporter):")
        trading_perf = report['trading_performance']
        total_bought = trading_perf['buys']['total_quantity']
        total_sold = trading_perf['sells']['total_quantity']
        realized_profit = trading_perf['realized_profit']['profit_usd']
        print(f"   ALKIMI bought:           {total_bought:>15,.0f}")
        print(f"   ALKIMI sold:             {total_sold:>15,.0f}")
        print(f"   Realized P&L:            ${realized_profit:>15,.2f}")

        print(f"\n💰 CURRENT POSITION:")
        print(f"   USDT balance:            ${current_usdt:>15,.2f}")
        print(f"   ALKIMI balance:          {current_alkimi:>15,.0f} @ ${current_alkimi_price:.6f}")
        print(f"   ALKIMI value:            ${current_alkimi_value:>15,.2f}")
        print(f"   Total on exchanges:      ${current_usdt + current_alkimi_value:>15,.2f}")

        print(f"\n📤 WITHDRAWALS (From Excel):")
        print(f"   Stablecoins withdrawn:   ${actual_total_withdrawals:>15,.2f}")

        print(f"\n💵 TOTAL ASSETS:")
        total_assets = current_usdt + current_alkimi_value + actual_total_withdrawals
        print(f"   Current + Withdrawn:     ${total_assets:>15,.2f}")

        print(f"\n📈 TOTAL P&L:")
        total_pnl = total_assets - total_starting_usd_value
        pnl_percent = (total_pnl / total_starting_usd_value) * 100 if total_starting_usd_value > 0 else 0
        print(f"   Total P&L:               ${total_pnl:>15,.2f} ({pnl_percent:+.2f}%)")

        print(f"\n📊 BREAKDOWN:")
        # Unrealized = current ALKIMI value - (starting ALKIMI - sold + bought) * current price
        remaining_alkimi_from_start = total_starting_alkimi - total_sold + total_bought
        unrealized_pnl = current_alkimi_value - (remaining_alkimi_from_start * current_alkimi_price)
        print(f"   Realized P&L:            ${realized_profit:>15,.2f}")
        print(f"   Unrealized P&L (approx): ${total_pnl - realized_profit:>15,.2f}")

        print("\n" + "=" * 80)

    finally:
        # Cleanup
        for name, client in exchanges:
            try:
                await client.close()
            except:
                pass


if __name__ == '__main__':
    asyncio.run(main())
