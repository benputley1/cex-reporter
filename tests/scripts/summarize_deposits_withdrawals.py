#!/usr/bin/env python3
"""
Summarize Deposits & Withdrawals
Clean summary of ALKIMI starting balances and stablecoin withdrawals.
"""

import pandas as pd
from collections import defaultdict

def main():
    excel_file = '/Users/ben/Desktop/cex-reporter/deposits & withdrawals.xlsx'

    print("=" * 80)
    print("EXCHANGE DEPOSITS & WITHDRAWALS SUMMARY")
    print("=" * 80)
    print()

    # ========================================================================
    # ALKIMI DEPOSITS (Starting Balances)
    # ========================================================================
    print("💰 ALKIMI DEPOSITS TO EXCHANGES (Starting Balances)")
    print("=" * 80)

    df_deposits = pd.read_excel(excel_file, sheet_name='Deposits od ALKIMI to exchanges')

    # Group by destination exchange
    deposits_by_exchange = defaultdict(list)
    for _, row in df_deposits.iterrows():
        destination = row['Destination']
        amount = row['Amount']
        date = row['Date']
        deposits_by_exchange[destination].append({
            'date': date,
            'amount': amount
        })

    total_alkimi_deposited = 0
    for exchange, deposits in sorted(deposits_by_exchange.items()):
        exchange_total = sum(d['amount'] for d in deposits)
        total_alkimi_deposited += exchange_total
        print(f"\n{exchange}:")
        for dep in deposits:
            print(f"  {dep['date']}: {dep['amount']:>15,.0f} ALKIMI")
        print(f"  {'─' * 40}")
        print(f"  Subtotal:       {exchange_total:>15,.0f} ALKIMI")

    print(f"\n{'═' * 80}")
    print(f"TOTAL ALKIMI DEPOSITED: {total_alkimi_deposited:>15,.0f} ALKIMI")
    print(f"{'═' * 80}")

    # ========================================================================
    # STABLECOIN WITHDRAWALS
    # ========================================================================
    print("\n\n")
    print("💸 STABLECOIN WITHDRAWALS FROM EXCHANGES")
    print("=" * 80)

    df_withdrawals = pd.read_excel(excel_file, sheet_name='Stablecoin Withdrawals from Exc')

    # Identify source exchanges from the From_Nametag or Method columns
    withdrawals_by_source = defaultdict(lambda: defaultdict(list))

    for _, row in df_withdrawals.iterrows():
        # Determine source exchange
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

        # If no nametag, check Method
        if source == 'Unknown' and pd.notna(row['Method']):
            method = str(row['Method']).lower()
            if 'kucoin' in method:
                source = 'KuCoin'

        # Get the token and amount
        token = row['Token']
        amount = row['Amount']
        date = row['DateTime (UTC)']

        withdrawals_by_source[source][token].append({
            'date': date,
            'amount': amount
        })

    total_usd_withdrawn = 0
    for source in sorted(withdrawals_by_source.keys()):
        print(f"\n{source}:")
        source_total = 0
        for token, withdrawals in sorted(withdrawals_by_source[source].items()):
            token_total = sum(w['amount'] for w in withdrawals)
            source_total += token_total
            print(f"  {token}:")
            for withdrawal in withdrawals:
                print(f"    {withdrawal['date']}: ${withdrawal['amount']:>12,.2f}")
            print(f"    {'─' * 50}")
            print(f"    Subtotal:        ${token_total:>12,.2f}")

        total_usd_withdrawn += source_total
        print(f"  {'─' * 54}")
        print(f"  {source} Total:       ${source_total:>12,.2f}")

    print(f"\n{'═' * 80}")
    print(f"TOTAL STABLECOINS WITHDRAWN: ${total_usd_withdrawn:>12,.2f}")
    print(f"{'═' * 80}")

    # ========================================================================
    # RECONCILIATION
    # ========================================================================
    print("\n\n")
    print("📊 RECONCILIATION")
    print("=" * 80)
    print(f"Starting ALKIMI deposited:     {total_alkimi_deposited:>15,.0f} ALKIMI")
    print(f"Stablecoins withdrawn:        ${total_usd_withdrawn:>15,.2f}")
    print()
    print("Note: Compare these figures with your current CEX Reporter balances")
    print("      to verify accounting accuracy.")
    print("=" * 80)


if __name__ == '__main__':
    main()
