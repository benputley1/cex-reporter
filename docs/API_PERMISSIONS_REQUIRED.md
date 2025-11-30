# API Permissions Required for Deposit/Withdrawal Tracking

## Issue

The deposit and withdrawal tracking feature is implemented but currently returning 0 results because the API keys don't have the required **wallet permissions** enabled.

### Error Message
```
gateio {"message":"Request API key does not have wallet permission","label":"FORBIDDEN"}
```

## Root Cause

Exchange APIs have different permission levels:
- **Read/Trading permissions**: Allow reading balances and trade history
- **Wallet permissions**: Required to access deposit/withdrawal history

Currently, the API keys only have read/trading permissions, which is why:
- ✅ Balance fetching works
- ✅ Trade history fetching works
- ❌ Deposit history returns permission error (caught silently)
- ❌ Withdrawal history returns permission error (caught silently)

## Solution

You need to **enable wallet/withdrawal permissions** for the API keys on each exchange.

### For Gate.io

1. Log into Gate.io
2. Go to API Management
3. For each API key (MM1, MM2, TM):
   - Edit the API key settings
   - Enable **"Wallet" permission** (or "Withdrawal" permission)
   - Save changes
4. Note: You may need to regenerate the API secret after changing permissions

### For Other Exchanges

Similar steps apply:

**MEXC:**
- Enable "Withdrawal" permission in API settings

**KuCoin:**
- Enable "Transfer" permission in API settings
- Note: KuCoin has granular permissions - may need both "View" and "Transfer" under the Wallet section

**Kraken:**
- Enable "Query Funds" and "Withdraw Funds" permissions
- Note: Kraken requires these for viewing deposit/withdrawal history even if not actually withdrawing

## Security Considerations

**Important**: Wallet permissions are sensitive. Consider:

1. **IP Whitelist**: Restrict API keys to specific IPs where this application runs
2. **Read-only**: If available, use "view wallet" rather than "withdraw" permission
3. **Separate Keys**: Consider using different API keys for trading vs. reporting
4. **2FA**: Enable 2FA for API key creation/modification

## Testing After Enabling Permissions

Once permissions are enabled, test with:

```bash
python3 test_deposits.py
```

Expected output:
```
✓ Gate.io connected successfully

--- USDT Deposits ---
API returned X deposits
First deposit sample:
  Status: ok
  Amount: XXXX.XX
  ...
```

## Current Status

| Exchange | Account | Wallet Permission | Status |
|----------|---------|------------------|--------|
| Gate.io  | MM1     | ❌ Not enabled   | Need to enable |
| Gate.io  | MM2     | ❌ Not enabled   | Need to enable |
| Gate.io  | TM      | ❌ Not enabled   | Need to enable |
| MEXC     | MM1     | ❌ Not enabled   | Need to enable |
| MEXC     | MM2     | ❌ Not enabled   | Need to enable |
| MEXC     | TM1     | ❌ Not enabled   | Need to enable |
| KuCoin   | MM1     | ❌ Not enabled   | Need to enable |
| KuCoin   | MM2     | ❌ Not enabled   | Need to enable |
| Kraken   | MAIN    | ❌ Not enabled   | Need to enable |

## Implementation Status

✅ **Code is ready** - Deposit/withdrawal tracking is fully implemented
❌ **Waiting on permissions** - Need wallet permissions enabled on API keys

Once permissions are enabled, the system will automatically:
- Fetch deposit/withdrawal history
- Calculate accurate starting positions
- Display deposit/withdrawal summary in Slack reports
- Separate trading P&L from account transfers
