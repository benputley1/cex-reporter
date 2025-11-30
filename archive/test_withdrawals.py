#!/usr/bin/env python3
import sys
sys.path.insert(0, '.')
from src.data.deposits_loader import DepositsLoader

loader = DepositsLoader()
withdrawals = loader.load_withdrawals()
total = loader.get_total_withdrawals()

print(f'Total withdrawals: ${total:,.2f}')
for asset, data in withdrawals.items():
    print(f'{asset}: {len(data["withdrawals"])} transactions, ${data["total_amount"]:,.2f}')
