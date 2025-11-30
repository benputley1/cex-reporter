#!/usr/bin/env python3
"""
Calculate Accurate P&L Using Deposits & Withdrawals
Uses the Excel file data to properly account for starting balances and withdrawals.
"""

import sys
import os
from datetime import datetime
from collections import defaultdict
import pandas as pd

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from config.settings import settings
from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient

async def main():
    """Calculate accurate P&L using deposits & withdrawals data."""

    excel_file = '/Users/ben/Desktop/cex-reporter/deposits & withdrawals.xlsx'
    historical_start_date = datetime.fromisoformat(settings.historical_start_date)

    print("=" * 80)
    print("ACCURATE P&L CALCULATION")
    print("Using Deposits & Withdrawals Data")
    print("=" * 80)
    print()

    # ========================================================================
    # Step 1: Load Deposits (Starting ALKIMI Inventory)
    # ========================================================================
    print("📥 STEP 1: Loading ALKIMI Deposits (Starting Inventory)")
    print("─" * 80)

    df_deposits = pd.read_excel(excel_file, sheet_name='Deposits od ALKIMI to exchanges')

    starting_alkimi_by_exchange = {}
    total_starting_alkimi = 0
    total_starting_usd_value = 0

    for _, row in df_deposits.iterrows():
        destination = row['Destination']
        amount = row['Amount']
        usd_value = row['USD Amount']
        date = pd.to_datetime(row['Date'])

        if destination not in starting_alkimi_by_exchange:
            starting_alkimi_by_exchange[destination] = {
                'alkimi': 0,
                'usd_value': 0,
                'deposits': []
            }

        starting_alkimi_by_exchange[destination]['alkimi'] += amount
        starting_alkimi_by_exchange[destination]['usd_value'] += usd_value
        starting_alkimi_by_exchange[destination]['deposits'].append({
            'date': date,
            'amount': amount,
            'usd_value': usd_value,
            'price': usd_value / amount
        })

        total_starting_alkimi += amount
        total_starting_usd_value += usd_value

    for exchange, data in sorted(starting_alkimi_by_exchange.items()):
        avg_price = data['usd_value'] / data['alkimi']
        print(f"{exchange:25s}: {data['alkimi']:>15,.0f} ALKIMI @ ${avg_price:.6f} = ${data['usd_value']:>12,.2f}")

    print(f"{'─' * 80}")
    print(f"{'TOTAL STARTING INVENTORY':25s}: {total_starting_alkimi:>15,.0f} ALKIMI = ${total_starting_usd_value:>12,.2f}")
    print()

    # ========================================================================
    # Step 2: Load Withdrawals (Realized Profits Taken Out)
    # ========================================================================
    print("📤 STEP 2: Loading Stablecoin Withdrawals (Profits Taken)")
    print("─" * 80)

    df_withdrawals = pd.read_excel(excel_file, sheet_name='Stablecoin Withdrawals from Exc')

    withdrawals_by_month = defaultdict(lambda: defaultdict(float))
    total_withdrawals = 0

    for _, row in df_withdrawals.iterrows():
        date = pd.to_datetime(row['DateTime (UTC)'])
        amount = row['Amount']
        month_key = date.strftime('%Y-%m')

        # Try to identify source
        source = 'Unknown'
        if pd.notna(row['From_Nametag']):
            nametag = str(row['From_Nametag']).lower()
            if 'kucoin' in nametag:
                source = 'KuCoin'
            elif 'gate' in nametag:
                source = 'Gate.io'
            elif 'kraken' in nametag:
                source = 'Kraken'
            elif 'mexc' in nametag:
                source = 'MEXC'

        withdrawals_by_month[month_key][source] += amount
        total_withdrawals += amount

    for month_key in sorted(withdrawals_by_month.keys()):
        month_total = sum(withdrawals_by_month[month_key].values())
        print(f"{month_key}: ${month_total:>12,.2f}")
        for source, amount in sorted(withdrawals_by_month[month_key].items()):
            if source != 'Unknown':
                print(f"  {source:20s}: ${amount:>12,.2f}")

    print(f"{'─' * 80}")
    print(f"TOTAL WITHDRAWALS: ${total_withdrawals:>12,.2f}")
    print()

    # ========================================================================
    # Step 3: Fetch Current Balances
    # ========================================================================
    print("💰 STEP 3: Fetching Current Exchange Balances")
    print("─" * 80)

    current_balances = {}
    all_exchanges = []

    # MEXC
    for account in settings.mexc_accounts:
        if account['account_name'] == 'MM1':
            continue  # Skip MM1 due to auth issue
        try:
            client = MEXCClient(account['apiKey'], account['secret'])
            balances = await client.get_balances()
            current_balances[f"MEXC_{account['account_name']}"] = balances
            all_exchanges.append(client)
            print(f"✓ MEXC {account['account_name']:4s}: {balances.get('USDT', 0):>12,.2f} USDT, {balances.get('ALKIMI', 0):>15,.2f} ALKIMI")
        except Exception as e:
            print(f"✗ MEXC {account['account_name']}: {str(e)}")

    # Kraken
    for account in settings.kraken_accounts:
        try:
            client = KrakenClient(account['apiKey'], account['secret'])
            balances = await client.get_balances()
            current_balances[f"Kraken_{account['account_name']}"] = balances
            all_exchanges.append(client)
            print(f"✓ Kraken {account['account_name']:4s}: {balances.get('USDT', 0):>12,.2f} USDT, {balances.get('ALKIMI', 0):>15,.2f} ALKIMI")
        except Exception as e:
            print(f"✗ Kraken {account['account_name']}: {str(e)}")

    # KuCoin
    for account in settings.kucoin_accounts:
        try:
            client = KuCoinClient(account['apiKey'], account['secret'], account['password'])
            balances = await client.get_balances()
            current_balances[f"KuCoin_{account['account_name']}"] = balances
            all_exchanges.append(client)
            print(f"✓ KuCoin {account['account_name']:4s}: {balances.get('USDT', 0):>12,.2f} USDT, {balances.get('ALKIMI', 0):>15,.2f} ALKIMI")
        except Exception as e:
            print(f"✗ KuCoin {account['account_name']}: {str(e)}")

    # Gate.io
    for account in settings.gateio_accounts:
        try:
            client = GateioClient(account['apiKey'], account['secret'])
            balances = await client.get_balances()
            current_balances[f"Gateio_{account['account_name']}"] = balances
            all_exchanges.append(client)
            print(f"✓ Gate.io {account['account_name']:4s}: {balances.get('USDT', 0):>12,.2f} USDT, {balances.get('ALKIMI', 0):>15,.2f} ALKIMI")
        except Exception as e:
            print(f"✗ Gate.io {account['account_name']}: {str(e)}")

    # Calculate totals
    total_current_usdt = sum(b.get('USDT', 0) for b in current_balances.values())
    total_current_alkimi = sum(b.get('ALKIMI', 0) for b in current_balances.values())

    print(f"{'─' * 80}")
    print(f"TOTAL CURRENT: {total_current_usdt:>12,.2f} USDT, {total_current_alkimi:>15,.2f} ALKIMI")
    print()

    # ========================================================================
    # Step 4: Fetch All Trades and Calculate Monthly P&L
    # ========================================================================
    print("📊 STEP 4: Fetching Trades and Calculating Monthly P&L")
    print("─" * 80)

    all_trades = []
    for exchange in all_exchanges:
        try:
            trades = await exchange.get_trades(since=historical_start_date)
            all_trades.extend(trades)
            await exchange.close()
        except Exception as e:
            print(f"Error fetching trades: {str(e)}")

    print(f"Fetched {len(all_trades)} total trades\n")

    # Group trades by month
    monthly_trades = defaultdict(list)
    for trade in all_trades:
        month_key = trade.timestamp.strftime('%Y-%m')
        monthly_trades[month_key].append(trade)

    # Calculate P&L by month
    print("MONTHLY P&L BREAKDOWN")
    print("=" * 80)

    sorted_months = sorted(monthly_trades.keys())

    # Track running position
    running_alkimi_bought = 0
    running_alkimi_sold = 0
    running_usdt_spent = 0
    running_usdt_received = 0

    for month_key in sorted_months:
        trades = monthly_trades[month_key]

        # Calculate for this month
        month_buys = [t for t in trades if t.side.value == 'buy']
        month_sells = [t for t in trades if t.side.value == 'sell']

        alkimi_bought = sum(t.amount for t in month_buys)
        alkimi_sold = sum(t.amount for t in month_sells)
        usdt_spent = sum(t.amount * t.price + t.fee for t in month_buys)
        usdt_received = sum(t.amount * t.price - t.fee for t in month_sells)

        # Update running totals
        running_alkimi_bought += alkimi_bought
        running_alkimi_sold += alkimi_sold
        running_usdt_spent += usdt_spent
        running_usdt_received += usdt_received

        # Calculate monthly P&L
        month_pnl = usdt_received - usdt_spent

        # Get withdrawals for this month
        month_withdrawals = sum(withdrawals_by_month[month_key].values())

        print(f"\n{month_key}:")
        print(f"  Trades: {len(month_buys)} buys, {len(month_sells)} sells")
        print(f"  Bought:   {alkimi_bought:>15,.0f} ALKIMI for ${usdt_spent:>12,.2f}")
        print(f"  Sold:     {alkimi_sold:>15,.0f} ALKIMI for ${usdt_received:>12,.2f}")
        print(f"  Net P&L:  ${month_pnl:>12,.2f}")
        if month_withdrawals > 0:
            print(f"  Withdrawn: ${month_withdrawals:>12,.2f}")

    # ========================================================================
    # Step 5: Complete Reconciliation
    # ========================================================================
    print("\n\n")
    print("=" * 80)
    print("COMPLETE P&L RECONCILIATION")
    print("=" * 80)

    # Calculate latest ALKIMI price from recent trades
    recent_trades = sorted(all_trades, key=lambda t: t.timestamp, reverse=True)[:10]
    current_alkimi_price = sum(t.price for t in recent_trades) / len(recent_trades) if recent_trades else 0

    current_alkimi_value = total_current_alkimi * current_alkimi_price

    print(f"\n📥 STARTING POSITION:")
    print(f"   ALKIMI deposited:        {total_starting_alkimi:>15,.0f} @ avg ${total_starting_usd_value/total_starting_alkimi:.6f}")
    print(f"   Initial value:           ${total_starting_usd_value:>15,.2f}")

    print(f"\n📊 TRADING ACTIVITY:")
    print(f"   ALKIMI bought:           {running_alkimi_bought:>15,.0f} for ${running_usdt_spent:>12,.2f}")
    print(f"   ALKIMI sold:             {running_alkimi_sold:>15,.0f} for ${running_usdt_received:>12,.2f}")
    print(f"   Gross trading P&L:       ${running_usdt_received - running_usdt_spent:>15,.2f}")

    print(f"\n💰 CURRENT POSITION:")
    print(f"   USDT balance:            ${total_current_usdt:>15,.2f}")
    print(f"   ALKIMI balance:          {total_current_alkimi:>15,.0f} @ ${current_alkimi_price:.6f}")
    print(f"   ALKIMI value:            ${current_alkimi_value:>15,.2f}")
    print(f"   Total on exchanges:      ${total_current_usdt + current_alkimi_value:>15,.2f}")

    print(f"\n📤 WITHDRAWALS:")
    print(f"   Stablecoins withdrawn:   ${total_withdrawals:>15,.2f}")

    print(f"\n💵 TOTAL ASSETS:")
    total_assets = total_current_usdt + current_alkimi_value + total_withdrawals
    print(f"   Current + Withdrawn:     ${total_assets:>15,.2f}")

    print(f"\n📈 REALIZED + UNREALIZED P&L:")
    total_pnl = total_assets - total_starting_usd_value
    pnl_percent = (total_pnl / total_starting_usd_value) * 100 if total_starting_usd_value > 0 else 0
    print(f"   Total P&L:               ${total_pnl:>15,.2f} ({pnl_percent:+.2f}%)")

    print(f"\n📊 BREAKDOWN:")
    realized_pnl = running_usdt_received - running_usdt_spent
    unrealized_pnl = current_alkimi_value - (total_starting_alkimi - running_alkimi_sold + running_alkimi_bought) * current_alkimi_price
    print(f"   Realized P&L:            ${realized_pnl:>15,.2f}")
    print(f"   Unrealized P&L:          ${unrealized_pnl:>15,.2f}")

    print("\n" + "=" * 80)


if __name__ == '__main__':
    import asyncio
    asyncio.run(main())
