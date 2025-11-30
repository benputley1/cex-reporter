# Deposit/Withdrawal Tracking Implementation

## Overview

Adding deposit/withdrawal tracking to properly account for portfolio changes that aren't due to trading activity.

## Problem Statement

Currently, the system calculates position changes as:
```
Position Change = Current Balance - Starting Balance
```

But this doesn't account for:
- Deposits (money/assets moved INTO the account)
- Withdrawals (money/assets moved OUT of the account)

## Correct Formula

```
Current Balance = Starting Balance + Deposits - Withdrawals + Trading P&L
```

Rearranged:
```
Trading P&L = Current Balance - Starting Balance - Deposits + Withdrawals
```

## Implementation Plan

### 1. Data Structure (✅ DONE)
- Added `Transaction` dataclass to `src/exchanges/base.py`
- Added abstract methods: `get_deposits()`, `get_withdrawals()`

### 2. Exchange Client Implementation (IN PROGRESS)
For each exchange (MEXC, KuCoin, Gate.io, Kraken):
- Implement `get_deposits(since)` using ccxt's `fetchDeposits()`
- Implement `get_withdrawals(since)` using ccxt's `fetchWithdrawals()`
- Parse exchange-specific transaction formats
- Filter by tracked assets (USDT, ALKIMI)
- Handle pagination for large histories

### 3. Position Tracker Updates
Update `PositionTracker` to:
- Fetch deposits/withdrawals for each account
- Calculate net deposits: `total_deposits - total_withdrawals`
- Adjust position calculations:
  ```python
  true_starting_balance = current_balance - net_deposits - trading_pnl
  ```
- Add new report sections:
  - Total deposits by asset
  - Total withdrawals by asset
  - Net flow (deposits - withdrawals)

### 4. Report Format Updates
Add to Slack report:
```
📥 Deposits & Withdrawals
  USDT:
    • Deposits: +50,000 USDT (3 transactions)
    • Withdrawals: -10,000 USDT (1 transaction)
    • Net Flow: +40,000 USDT

  ALKIMI:
    • Deposits: +500,000 ALKIMI (2 transactions)
    • Withdrawals: -1,200,000 ALKIMI (5 transactions)
    • Net Flow: -700,000 ALKIMI

📊 Adjusted Position Analysis
  Starting Balance (inferred):
    • USDT: 9,634.43 (after accounting for +40K deposits)
    • ALKIMI: 4,200,099 (after accounting for -700K withdrawals)

  Trading P&L (isolated):
    • USDT from trading: +30,000
    • ALKIMI from trading: -1,323,099 (net sales)
```

## Benefits

1. **Accurate P&L**: Separate trading performance from deposits/withdrawals
2. **True Starting Balance**: Calculate what balance was before any activity
3. **Cash Flow Tracking**: See money movement in/out of accounts
4. **Better Analysis**: Understand if position changes are due to trading or transfers

## Implementation Status

- [x] Research exchange APIs
- [x] Add Transaction dataclass
- [x] Add abstract methods to ExchangeInterface
- [ ] Implement in MEXC client
- [ ] Implement in KuCoin client
- [ ] Implement in Gate.io client
- [ ] Implement in Kraken client
- [ ] Update PositionTracker
- [ ] Update Slack formatter
- [ ] Test with real data
