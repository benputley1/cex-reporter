# Exchange-Specific Notes

## Asset Mappings

### Kraken

**Important:** Kraken lists **USD** (fiat currency) instead of **USDT** (Tether stablecoin).

#### How It's Handled

The system automatically maps `USDT` → `USD` when querying Kraken:

```python
# Configuration in config/settings.py
asset_mapping = {
    'kraken': {
        'USDT': 'USD',  # Kraken uses USD (fiat) not USDT (stablecoin)
    }
}
```

#### What This Means

1. **You track USDT** in your configuration:
   ```env
   TRACKED_ASSETS=USDT,ALKIMI
   ```

2. **System queries USD from Kraken** automatically:
   - Balance requests: looks for `USD` balance on Kraken
   - Trade history: looks for `USD/EUR` or similar pairs
   - Prices: treats USD as $1.00 (same as USDT)

3. **Reports show USDT** consistently:
   - All exchanges report under the standard "USDT" name
   - Kraken's USD balance appears as USDT in reports
   - Portfolio aggregation works seamlessly

#### Example

**Your Balances:**
- MEXC: 50,000 USDT
- Kraken: 75,000 USD (reported as USDT)
- KuCoin: 30,000 USDT
- Gate.io: 45,000 USDT

**Portfolio Report:**
```
USDT Total: 200,000 USDT ($200,000)
  - MEXC: 50,000
  - Kraken: 75,000 (actually USD)
  - KuCoin: 30,000
  - Gate.io: 45,000
```

#### Why This Matters

- **USD is fiat currency** held in your Kraken account
- **USDT is a stablecoin** (Tether token)
- Both are pegged to ~$1.00 USD
- For reporting purposes, they're treated equivalently
- The system handles the conversion transparently

### MEXC

- **USDT:** Native support ✅
- **ALKIMI:** Listed (verify current status)
- **Notes:** Standard USDT stablecoin

### KuCoin

- **USDT:** Native support ✅
- **ALKIMI:** Listed (verify current status)
- **Notes:** Standard USDT stablecoin

### Gate.io

- **USDT:** Native support ✅
- **ALKIMI:** Listed (verify current status)
- **Notes:** Standard USDT stablecoin

---

## Asset Availability by Exchange

| Asset | MEXC | Kraken | KuCoin | Gate.io |
|-------|------|--------|--------|---------|
| **USDT** | ✅ USDT | ⚠️ USD | ✅ USDT | ✅ USDT |
| **ALKIMI** | ✅ | ❌ | ✅ | ✅ |

**Legend:**
- ✅ = Listed and supported
- ❌ = Not listed (balance will be $0)
- ⚠️ = Different symbol used (mapped automatically)

---

## Adding Custom Mappings

If other exchanges use different symbols, add them to `config/settings.py`:

```python
@property
def asset_mapping(self) -> Dict[str, Dict[str, str]]:
    return {
        'kraken': {
            'USDT': 'USD',
        },
        'binance': {
            'USDT': 'USDT',  # Binance uses standard USDT
        },
        # Add more mappings as needed
    }
```

---

## Verification Steps

When setting up with real API keys:

1. **Test Kraken Connection:**
   ```bash
   python3 main.py --mode once
   ```

2. **Check Logs:**
   ```bash
   grep "Kraken" logs/cex_reporter.log
   ```

   Look for: `Mapped USDT to USD on Kraken, balance: 75000.00`

3. **Verify Slack Report:**
   - Kraken balance should appear under "USDT"
   - Total USDT should include Kraken's USD balance

---

## Troubleshooting

### "No USD balance found on Kraken"

**Problem:** Kraken returns 0 for USD balance

**Solutions:**
1. Verify you have USD (fiat) in your Kraken account, not USDT
2. Check API key has "Query Funds" permission
3. Ensure USD balance is not locked/staked

### "USDT not found on Kraken"

**Problem:** Old code looking for USDT instead of USD

**Solution:** Make sure you're using the latest version with asset mapping

### "Kraken balance not in total"

**Problem:** Kraken USD not included in portfolio total

**Solution:**
1. Check logs for mapping: `grep "Mapped USDT to USD" logs/cex_reporter.log`
2. Verify Kraken client initialized: `grep "Kraken client initialized" logs/cex_reporter.log`

---

**Last Updated:** 2025-11-04
**System Version:** 2.0
