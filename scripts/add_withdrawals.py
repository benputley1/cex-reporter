#!/usr/bin/env python3
"""
Script to add new USDT withdrawals to the tracking spreadsheet
"""

import pandas as pd
from datetime import datetime
import os

# Path to the Excel file
excel_path = os.path.join(os.path.dirname(__file__), '..', 'deposits & withdrawals.xlsx')

# New withdrawals from Nov 8, 2025
new_withdrawals = [
    {
        'DateTime (UTC)': '2025-11-08 00:00:00',
        'Token': 'Tether USD(USDT)',
        'Value (USD)': '$20,292.81',
        'From_Nametag': 'KuCoin',
        'From': 'KuCoin',
        'Transaction Hash': 'manual_entry_20251108_kucoin'
    },
    {
        'DateTime (UTC)': '2025-11-08 00:00:00',
        'Token': 'Tether USD(USDT)',
        'Value (USD)': '$36,027.70',
        'From_Nametag': 'Gate.io',
        'From': 'Gate.io',
        'Transaction Hash': 'manual_entry_20251108_gateio'
    },
    {
        'DateTime (UTC)': '2025-11-08 00:00:00',
        'Token': 'Tether USD(USDT)',
        'Value (USD)': '$19,603.59',
        'From_Nametag': 'MEXC',
        'From': 'MEXC',
        'Transaction Hash': 'manual_entry_20251108_mexc'
    },
    {
        'DateTime (UTC)': '2025-11-08 00:00:00',
        'Token': 'Tether USD(USDT)',
        'Value (USD)': '$12,238.68',
        'From_Nametag': 'Kraken',
        'From': 'Kraken',
        'Transaction Hash': 'manual_entry_20251108_kraken'
    }
]

def add_withdrawals():
    """Add new withdrawals to the Excel file"""

    print(f"Reading Excel file: {excel_path}")

    # Read the existing Excel file
    excel_file = pd.ExcelFile(excel_path)

    # Load the withdrawals sheet
    df_withdrawals = pd.read_excel(excel_file, sheet_name='Stablecoin Withdrawals from Exc')

    print(f"\nCurrent withdrawals: {len(df_withdrawals)} rows")
    print(f"Current total (unique): ${df_withdrawals[pd.notna(df_withdrawals['From_Nametag'])]['Value (USD)'].apply(lambda x: float(str(x).replace('$', '').replace(',', '')) if pd.notna(x) else 0).sum():,.2f}")

    # Create DataFrame from new withdrawals
    df_new = pd.DataFrame(new_withdrawals)

    # Append new withdrawals
    df_updated = pd.concat([df_withdrawals, df_new], ignore_index=True)

    print(f"\nAdding {len(new_withdrawals)} new withdrawals:")
    for w in new_withdrawals:
        print(f"  - {w['From_Nametag']}: {w['Value (USD)']}")

    total_new = sum(float(w['Value (USD)'].replace('$', '').replace(',', '')) for w in new_withdrawals)
    print(f"\nTotal new withdrawals: ${total_new:,.2f}")

    # Save back to Excel (preserve all sheets)
    with pd.ExcelWriter(excel_path, engine='openpyxl', mode='a', if_sheet_exists='replace') as writer:
        df_updated.to_excel(writer, sheet_name='Stablecoin Withdrawals from Exc', index=False)

    print(f"\n✓ Updated Excel file with {len(df_updated)} total rows")

    # Verify
    df_verify = pd.read_excel(excel_path, sheet_name='Stablecoin Withdrawals from Exc')
    unique_total = df_verify[pd.notna(df_verify['From_Nametag'])]['Value (USD)'].apply(
        lambda x: float(str(x).replace('$', '').replace(',', '')) if pd.notna(x) else 0
    ).sum()
    print(f"New total (unique): ${unique_total:,.2f}")

if __name__ == '__main__':
    add_withdrawals()
