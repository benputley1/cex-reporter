#!/usr/bin/env python3
"""
Analyze Deposits & Withdrawals Excel File
Calculate starting ALKIMI balances and stablecoin withdrawals from exchanges.
"""

import sys
import os
import pandas as pd
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

def main():
    """Analyze the deposits & withdrawals Excel file."""

    excel_file = '/Users/ben/Desktop/cex-reporter/deposits & withdrawals.xlsx'

    print("=" * 80)
    print("DEPOSITS & WITHDRAWALS ANALYSIS")
    print("=" * 80)
    print()

    # Read all sheets from the Excel file
    try:
        xl_file = pd.ExcelFile(excel_file)
        print(f"📊 Found {len(xl_file.sheet_names)} sheet(s) in the Excel file:")
        for i, sheet in enumerate(xl_file.sheet_names, 1):
            print(f"  {i}. {sheet}")
        print()

        # Read each sheet and display its structure
        for sheet_name in xl_file.sheet_names:
            print("=" * 80)
            print(f"SHEET: {sheet_name}")
            print("=" * 80)

            df = pd.read_excel(excel_file, sheet_name=sheet_name)

            print(f"\nColumns: {list(df.columns)}")
            print(f"Rows: {len(df)}")
            print("\nFirst few rows:")
            print(df.head(10).to_string())
            print("\n")

            # If the sheet contains deposit/withdrawal data, analyze it
            if 'Asset' in df.columns or 'Currency' in df.columns or 'Coin' in df.columns:
                analyze_transactions(df, sheet_name)

    except Exception as e:
        print(f"❌ Error reading Excel file: {str(e)}")
        import traceback
        traceback.print_exc()


def analyze_transactions(df, sheet_name):
    """Analyze transaction data from a sheet."""

    print(f"\n{'─' * 80}")
    print(f"ANALYSIS: {sheet_name}")
    print('─' * 80)

    # Try to identify the asset/currency column
    asset_col = None
    for col in ['Asset', 'Currency', 'Coin', 'asset', 'currency', 'coin']:
        if col in df.columns:
            asset_col = col
            break

    if not asset_col:
        print("⚠️  Could not identify asset/currency column")
        return

    # Try to identify transaction type column
    type_col = None
    for col in ['Type', 'Transaction Type', 'type', 'transaction_type']:
        if col in df.columns:
            type_col = col
            break

    # Try to identify amount column
    amount_col = None
    for col in ['Amount', 'Quantity', 'amount', 'quantity', 'Volume']:
        if col in df.columns:
            amount_col = col
            break

    print(f"\nDetected columns:")
    print(f"  Asset/Currency: {asset_col}")
    print(f"  Type: {type_col}")
    print(f"  Amount: {amount_col}")
    print()

    if not amount_col:
        print("⚠️  Could not identify amount column")
        return

    # Calculate ALKIMI deposits (starting balances)
    alkimi_deposits = df[df[asset_col].str.upper().str.contains('ALKIMI', na=False)]
    if type_col:
        alkimi_deposits = alkimi_deposits[alkimi_deposits[type_col].str.upper().str.contains('DEPOSIT', na=False)]

    if len(alkimi_deposits) > 0:
        print("💰 ALKIMI DEPOSITS (Starting Balances):")
        print("-" * 80)
        total_alkimi = 0
        for _, row in alkimi_deposits.iterrows():
            amount = row[amount_col]
            if pd.notna(amount):
                total_alkimi += float(amount)
                print(f"  {row.to_dict()}")
        print(f"\n  Total ALKIMI Deposited: {total_alkimi:,.2f} ALKIMI")
        print()

    # Calculate stablecoin withdrawals
    stablecoins = ['USDT', 'USDC', 'BUSD', 'DAI', 'USD']
    stablecoin_withdrawals = df[df[asset_col].str.upper().isin(stablecoins)]
    if type_col:
        stablecoin_withdrawals = stablecoin_withdrawals[stablecoin_withdrawals[type_col].str.upper().str.contains('WITHDRAW', na=False)]

    if len(stablecoin_withdrawals) > 0:
        print("💸 STABLECOIN WITHDRAWALS:")
        print("-" * 80)
        withdrawal_summary = {}
        for _, row in stablecoin_withdrawals.iterrows():
            asset = row[asset_col].upper()
            amount = row[amount_col]
            if pd.notna(amount):
                amount = float(amount)
                if asset not in withdrawal_summary:
                    withdrawal_summary[asset] = 0
                withdrawal_summary[asset] += amount
                print(f"  {row.to_dict()}")

        print(f"\n  Summary by stablecoin:")
        for asset, total in withdrawal_summary.items():
            print(f"    {asset}: {total:,.2f}")
        print()


if __name__ == '__main__':
    main()
