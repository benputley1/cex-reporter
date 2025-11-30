# Dashboard Requirements Mapping

**Source:** Alkimi_CEX_Dashboards_with_Exchange_Filter.xlsx
**Date:** 2025-11-04

---

## Overview

Your Excel file defines **44 dashboard metrics/visuals**. Below is a mapping of what's feasible with the current CEX Reporter system and what needs to be added.

---

## Current Capabilities ✅

### What We Can Already Provide (with minor adjustments):

| # | Metric | Status | Notes |
|---|--------|--------|-------|
| **2** | Total Assets Under Management (AUM) | ✅ **Ready** | Current portfolio aggregation |
| **4** | Total Trading Volume | ✅ **Ready** | Sum of all trades |
| **6** | Trading Volume by Asset Pair | ✅ **Ready** | From trade history (ALKIMI/USDT focus) |
| **8** | Number of Trades | ✅ **Ready** | Count from trade history |
| **9** | Total Buy Volume | ✅ **Ready** | Sum of buy trades |
| **10** | Total Sell Volume | ✅ **Ready** | Sum of sell trades |
| **11** | Buy/Sell Volume Ratio | ✅ **Ready** | Calculate from buy/sell totals |
| **17** | Current Holdings by Asset | ✅ **Ready** | Current balances (USDT, ALKIMI) |
| **18** | Holdings Value by Asset | ✅ **Ready** | Current values in USD |
| **29** | Recent Trades | ✅ **Ready** | Last N trades from history |
| **30** | Trade History Search | ✅ **Ready** | All trades since Aug 19 |
| **35** | ALKIMI Holdings | ✅ **Ready** | Total ALKIMI across exchanges |
| **36** | ALKIMI Trading Volume | ✅ **Ready** | ALKIMI-specific trade volume |
| **37** | ALKIMI Buy Volume | ✅ **Ready** | Total ALKIMI purchased |
| **38** | ALKIMI Sell Volume | ✅ **Ready** | Total ALKIMI sold |
| **39** | ALKIMI Trade History | ✅ **Ready** | ALKIMI trades only |

---

## Needs Implementation 🔧

### High Priority (Core Trading Metrics)

| # | Metric | Complexity | Notes |
|---|--------|------------|-------|
| **7** | Buy vs Sell Volume Over Time | Medium | Need time-series aggregation |
| **12** | Buy Orders by Account | Low | Group by exchange |
| **13** | Sell Orders by Account | Low | Group by exchange |
| **21** | Total Trading Fees Paid | **LOW** | Sum fees from trades |
| **22** | Fees by Account | **LOW** | Group fees by exchange |
| **31** | Largest Trades | **LOW** | Sort trades by value |
| **32** | Most Traded Pairs | Low | Count trades by pair |
| **40** | ALKIMI Holdings by Account | **LOW** | ALKIMI per exchange |

### Medium Priority (Account Details)

| # | Metric | Complexity | Notes |
|---|--------|------------|-------|
| **1** | Account Hierarchy | Medium | Main + sub-accounts (if applicable) |
| **3** | Assets by Account Type | Low | Main vs sub-account split |
| **5** | Trading Volume by Account | Low | Volume per exchange |
| **33** | Most Active Account | Low | Rank by volume/trades |
| **34** | Account Trading Summary | Low | Per-exchange summary cards |
| **41** | Account Overview Dashboard | Low | Summary view per exchange |
| **42** | Daily Activity Summary | Low | Today's metrics |

### Lower Priority (Advanced Features)

| # | Metric | Complexity | Notes |
|---|--------|------------|-------|
| **14** | Order Types Distribution | N/A | Would need order book API access |
| **15** | Order Status Summary | N/A | Would need real-time order status |
| **16** | Current Open Orders | N/A | Would need order book access |
| **19** | Largest Holdings | Low | Top N assets by value |
| **20** | Available vs Locked Balance | Medium | Need locked balance API |
| **23** | Fees by Asset Pair | Low | Group fees by trading pair |
| **24** | Fee Tier Status | Medium | Exchange-specific implementation |
| **43** | Asset Distribution Treemap | Low | Visual representation |

### Not Applicable / Out of Scope

| # | Metric | Reason |
|---|--------|--------|
| **25** | Deposits to Exchange | Not available via ccxt API (depends on exchange) |
| **26** | Withdrawals from Exchange | Not available via ccxt API |
| **27** | Net Cash Flow | Requires deposit/withdrawal data |
| **28** | Internal Transfers | May not be trackable via API |
| **44** | Audit Trail | Requires comprehensive logging system |

---

## Recommended Implementation Priority

Based on your stated needs (tracking USD/ALKIMI changes, average prices, realized profit):

### Phase 1: Core Position Tracking ✅ (DONE)
What we've already built:
- USDT position tracking (starting → current)
- ALKIMI position tracking (quantity & value)
- Average buy/sell prices
- Realized profit from trades
- Trading performance metrics

### Phase 2: Exchange-Level Breakdown 🔧 (RECOMMENDED NEXT)

Add to position report:

```python
'by_exchange': {
    'mexc': {
        'usdt_balance': 50000.00,
        'alkimi_balance': 1500000.00,
        'alkimi_value_usd': 300000.00,
        'trade_count': 15,
        'buy_volume': 85000.00,
        'sell_volume': 42000.00,
        'fees_paid': 127.50
    },
    'kraken': {...},
    'kucoin': {...},
    'gateio': {...}
}
```

**Impact:** Shows which exchanges have most activity and holdings

### Phase 3: Fee Tracking 🔧 (HIGH VALUE, LOW EFFORT)

Add fee metrics to trading performance:

```python
'fees': {
    'total_fees_usd': 425.00,
    'fees_as_percent_of_volume': 0.05,
    'by_exchange': {
        'mexc': 127.50,
        'kraken': 85.00,
        'kucoin': 142.50,
        'gateio': 70.00
    }
}
```

**Impact:** Track trading costs

### Phase 4: Time-Series Analysis 🔧 (MEDIUM EFFORT)

Add daily/weekly breakdowns:

```python
'time_series': {
    '2025-11-04': {
        'volume': 25000.00,
        'trades': 4,
        'buy_volume': 15000.00,
        'sell_volume': 10000.00,
        'fees': 12.50
    },
    '2025-11-03': {...}
}
```

**Impact:** See trends over time

### Phase 5: Top Trades & Rankings 🔧 (LOW EFFORT, GOOD INSIGHTS)

Add:
- Top 10 largest trades
- Most active trading days
- Best/worst performing days

---

## What You're Getting Now (Position Tracker)

The `PositionTracker` I just built provides:

### 1. USDT Position
```
Starting Balance: 200,000 USDT
Current Balance: 215,500 USDT
Total Change: +15,500 USDT (+7.75%)

From ALKIMI Trading:
  Spent on purchases: -185,000 USDT
  Received from sales: +200,500 USDT
  Net from trading: +15,500 USDT
```

### 2. ALKIMI Position
```
Starting Balance: 3,000,000 ALKIMI
Current Balance: 3,500,000 ALKIMI
Quantity Change: +500,000 ALKIMI (+16.67%)

Value:
  Starting: $510,000 @ $0.17
  Current: $700,000 @ $0.20
  Value Change: +$190,000 (+37.25%)
  Price Change: +$0.03 (+17.65%)
```

### 3. Trading Performance
```
Purchases:
  22 trades
  4,000,000 ALKIMI
  Avg Buy Price: $0.1725
  Total Cost: $690,000

Sales:
  18 trades
  500,000 ALKIMI
  Avg Sale Price: $0.2010
  Total Revenue: $100,500

Realized Profit:
  $14,250 (+16.5%)
  Avg Spread: $0.0285 (+16.5%)
```

### 4. Summary
```
Total Portfolio Value: $915,500
  - USDT: $215,500
  - ALKIMI: $700,000

Realized Profit: $14,250
Total Trades: 40
```

---

## Immediate Additions Needed

Based on your Excel requirements, here are the **quick wins** we should add:

### 1. Exchange Breakdown (30 minutes)
Show holdings and activity per exchange

### 2. Fee Tracking (20 minutes)
Total fees paid and fee analysis

### 3. Largest Trades (15 minutes)
Top 10 trades by value

### 4. Daily Summary (30 minutes)
Today's trading activity

---

## Questions for You

1. **Sub-Accounts:** Do you use sub-accounts on any exchanges?
   - If yes, we need to track them separately
   - If no, we can simplify to just "exchange level"

2. **Priority Focus:** Which of these are most important?
   - ✅ Position tracking (USDT, ALKIMI) - DONE
   - 🔧 Exchange-level breakdown
   - 🔧 Fee tracking and analysis
   - 🔧 Time-series trends
   - 🔧 Top trades/rankings

3. **Reporting Frequency:** How often do you need updates?
   - Current: Every 4 hours
   - Would you want: Hourly? Daily summary? Real-time alerts?

4. **Deposit/Withdrawal Tracking:**
   - Do you deposit/withdraw USDT frequently?
   - Should we track this manually or ignore?

5. **Historical Data:**
   - Is Aug 19, 2025 the correct start date?
   - Do you need data before this date?

---

## Recommended Next Steps

1. **Review the Position Tracker output** (I can show you a test run)
2. **Confirm it matches your needs** for USDT/ALKIMI tracking
3. **Add quick wins:**
   - Exchange breakdown
   - Fee tracking
   - Largest trades
4. **Test with real API data**
5. **Iterate based on what you see**

Would you like me to:
- **A)** Show you the Position Tracker output with mock data?
- **B)** Add the exchange breakdown and fee tracking now?
- **C)** Update the main.py to use Position Tracker instead of old P&L?
- **D)** Something else?

Let me know what's most important and we'll build it! 📊
