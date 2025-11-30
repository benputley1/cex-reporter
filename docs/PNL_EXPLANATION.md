# P&L Calculations - Detailed Explanation

## What You're Currently Getting

### 1. **Realized P&L** (Closed Positions)

**Definition:** Profit/loss from trades you've completed (bought and sold).

**How it's calculated:**
- Uses **FIFO (First-In-First-Out)** accounting
- When you sell, it matches against your earliest purchases
- Includes trading fees in the cost basis

**Example:**
```
Buys:
  Aug 20: Buy 100,000 ALKIMI @ $0.18 = $18,000
  Aug 25: Buy 50,000 ALKIMI @ $0.20 = $10,000

Sells:
  Sep 5: Sell 80,000 ALKIMI @ $0.22 = $17,600

FIFO Calculation:
  - Sold 80,000 from the first buy (Aug 20)
  - Cost basis: 80,000 × $0.18 = $14,400
  - Revenue: 80,000 × $0.22 = $17,600
  - Realized P&L: $17,600 - $14,400 = +$3,200

Remaining:
  - 20,000 ALKIMI from Aug 20 purchase @ $0.18
  - 50,000 ALKIMI from Aug 25 purchase @ $0.20
```

### 2. **Unrealized P&L** (Open Positions)

**Definition:** Profit/loss from assets you currently hold (not yet sold).

**How it's calculated:**
- Takes your current balance
- Calculates average entry price using FIFO
- Compares to current market price

**Example:**
```
Current Holdings: 200,000 USDT

Purchase History (FIFO):
  Aug 19: Buy 100,000 USDT @ $0.998 = $99,800
  Sep 15: Buy 100,000 USDT @ $1.002 = $100,200

Average Entry: ($99,800 + $100,200) / 200,000 = $1.000
Current Price: $1.00
Unrealized P&L: 200,000 × ($1.00 - $1.00) = $0

(USDT stays close to $1.00, so unrealized is typically minimal)
```

### 3. **Timeframe P&L** (Period-based)

**Calculates P&L for specific time periods:**

#### **24h P&L**
- All trades in the last 24 hours
- Shows daily gains/losses

#### **7d P&L**
- All trades in the last 7 days
- Shows weekly performance

#### **30d P&L**
- All trades in the last 30 days
- Shows monthly performance

#### **Total P&L (since Aug 19, 2025)**
- All trades since your historical start date
- Shows overall performance

**Example:**
```
7-day timeframe (Nov 04 - Oct 28):
  Trades: 8 trades (4 buys, 4 sells)
  Net P&L: +$2,500
  Percentage: +1.2%
```

---

## What You See in Slack Reports

### Portfolio Update Message

```
📊 Alkimi Treasury Report
━━━━━━━━━━━━━━━━━━━━━━
💰 Total Portfolio Value
$900,000.00

📈 Asset Breakdown
• USDT: 200,000.0000 @ $1.0000 = $200,000.00 (22.2%)
• ALKIMI: 3,500,000.0000 @ $0.2000 = $700,000.00 (77.8%)

━━━━━━━━━━━━━━━━━━━━━━
📊 P&L Summary
• 24h: +$2,500 (+0.28%)
• 7d: +$15,000 (+1.69%)
• Total: +$125,000 (+16.1%)

🔔 Report generated at 2025-11-04 20:38:23 UTC
```

---

## Current P&L Report Structure

The system generates this data structure:

```json
{
  "realized": {
    "USDT": {
      "realized_pnl": 500.00,
      "total_bought": 250000.00,
      "total_sold": 50000.00,
      "avg_buy_price": 0.999,
      "avg_sell_price": 1.001
    },
    "ALKIMI": {
      "realized_pnl": 15000.00,
      "total_bought": 4000000.00,
      "total_sold": 500000.00,
      "avg_buy_price": 0.17,
      "avg_sell_price": 0.20
    }
  },
  "unrealized": {
    "USDT": {
      "unrealized_pnl": 200.00,
      "avg_entry": 0.999,
      "current_price": 1.00,
      "current_amount": 200000.00,
      "cost_basis": 199800.00,
      "current_value": 200000.00
    },
    "ALKIMI": {
      "unrealized_pnl": 109500.00,
      "avg_entry": 0.17,
      "current_price": 0.20,
      "current_amount": 3500000.00,
      "cost_basis": 595000.00,
      "current_value": 700000.00
    }
  },
  "timeframes": {
    "24h": {
      "ALKIMI": {
        "pnl": 2500.00,
        "pnl_percent": 0.36,
        "volume": 50000.00,
        "trade_count": 4
      },
      "summary": {
        "total_pnl_usd": 2500.00,
        "total_pnl_percent": 0.28
      }
    },
    "7d": {...},
    "30d": {...},
    "all": {...}
  },
  "summary": {
    "total_realized_pnl": 15500.00,
    "total_unrealized_pnl": 109700.00,
    "total_pnl": 125200.00,
    "current_portfolio_value": 900000.00,
    "total_return_percent": 16.1
  }
}
```

---

## Questions for You

Let me understand what reporting you need:

### 1. **Asset Focus**
- You're tracking **USDT** and **ALKIMI**
- Are you mainly interested in ALKIMI P&L (since USDT is stable)?
- Or do you need detailed USDT P&L too?

### 2. **P&L Breakdown Preferences**

**What's most useful to see daily/regularly?**

Option A - **Simple Summary** (Current):
```
Total P&L: +$125,000 (+16.1%)
24h: +$2,500 (+0.28%)
7d: +$15,000 (+1.69%)
```

Option B - **Per-Asset Detail**:
```
ALKIMI:
  Realized P&L: +$15,000
  Unrealized P&L: +$109,500
  Total P&L: +$124,500
  24h change: +$2,500

USDT:
  Realized P&L: +$500
  Unrealized P&L: +$200
  Total P&L: +$700
  24h change: $0
```

Option C - **Combined View** (Show both):
```
Total P&L: +$125,200
  - Realized: +$15,500
  - Unrealized: +$109,700

By Asset:
  - ALKIMI: +$124,500
  - USDT: +$700

Timeframes:
  - 24h: +$2,500
  - 7d: +$15,000
```

### 3. **Cost Basis Tracking**

**Current:** FIFO accounting from Aug 19, 2025

**Questions:**
- Is FIFO the right method for you? (vs LIFO, average cost, etc.)
- Is Aug 19, 2025 the correct start date?
- Do you want to see the cost basis breakdown in reports?

### 4. **Fee Handling**

**Current:** Fees are included in cost basis
- Buy fees increase cost basis
- Sell fees decrease revenue

**Is this correct for your needs?**

### 5. **Exchange-Specific P&L**

**Not currently shown** - Would you want to see:
```
P&L by Exchange:
  - MEXC: +$45,000
  - Kraken: +$8,000
  - KuCoin: +$38,000
  - Gate.io: +$34,200
```

### 6. **Historical Tracking**

**Not currently stored** - Would you want:
- Daily P&L history (track change over time)
- P&L charts/trends
- Best/worst trading days
- Monthly summaries

### 7. **USDT Specifics**

Since USDT is a stablecoin (~$1.00):
- Do you need detailed USDT P&L? (Usually minimal)
- Or just track if USDT balance changes significantly?
- Should USDT be treated differently in reports?

### 8. **Alert Preferences**

**Current:** Alert if portfolio changes >5% in 24h

**Would you also want alerts for:**
- Realized P&L milestones (e.g., +$10k in a day)
- Unrealized P&L thresholds
- ALKIMI price changes
- Large trades (>$X amount)

---

## Potential Enhancements

Based on your needs, we could add:

### Option 1: **Simplified for ALKIMI Focus**
```
📊 ALKIMI Performance
Current Holdings: 3,500,000 ALKIMI ($700,000)
Average Entry: $0.17
Current Price: $0.20
Total Gain: +$124,500 (+21.8%)

Recent Activity:
  - 24h: +$2,500 (+0.36%)
  - 7d: +$15,000 (+2.19%)
```

### Option 2: **Trading Performance**
```
📈 Trading Summary (Last 30 Days)
Total Trades: 40
  - Buys: 22 ($425,000)
  - Sells: 18 ($472,500)

Net P&L: +$47,500 (+11.2%)
Win Rate: 72% (13/18 profitable sells)
Average Trade: +$2,638
Best Trade: +$8,450
```

### Option 3: **Cost Basis Detail**
```
📊 Position Details
ALKIMI Holdings: 3,500,000

Cost Basis Breakdown:
  - 1,500,000 @ $0.15 (Aug 19-Sep 1)
  - 1,000,000 @ $0.18 (Sep 2-Sep 15)
  - 800,000 @ $0.20 (Sep 16-Oct 1)
  - 200,000 @ $0.22 (Oct 2-Nov 4)

Weighted Average: $0.17
Current Price: $0.20
Unrealized Gain: +$105,000
```

### Option 4: **Cash Flow View**
```
💰 Cash Flow (Last 30 Days)
Inflows:
  - ALKIMI sales: +$95,000
  - USDT interest: +$125
  Total: +$95,125

Outflows:
  - ALKIMI purchases: -$85,000
  - Trading fees: -$425
  Total: -$85,425

Net Cash Flow: +$9,700
```

---

## Let's Discuss

**Key Questions:**

1. **What's your primary goal?**
   - Track overall ALKIMI performance?
   - Monitor active trading P&L?
   - Watch for portfolio changes?
   - Tax reporting prep?

2. **What decision are you making with this data?**
   - When to buy/sell more?
   - Risk management?
   - Performance reporting to stakeholders?
   - Personal tracking?

3. **How detailed do you want reports?**
   - High-level summary (current)
   - Detailed breakdown
   - Different reports for different frequencies

4. **What's most important to see at a glance?**
   - Total portfolio value?
   - Recent P&L changes?
   - Per-asset performance?
   - Cost basis vs current price?

Once I understand your needs better, we can adjust the calculations and reports to show exactly what's most valuable to you! 📊
