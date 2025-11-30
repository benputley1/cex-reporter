# Sui DEX Integration - Quick Start Guide

## TL;DR
This guide helps you quickly integrate Sui DEX trades into your existing CEX Reporter system for unified reporting across centralized and decentralized exchanges.

## Before You Start - Answer These Questions

1. **Which Sui DEXs list ALKIMI?**
   - [ ] Cetus Protocol
   - [ ] Turbos Finance
   - [ ] Aftermath Finance
   - [ ] DeepBook
   - [ ] KriyaDEX
   - [ ] Other: ___________

2. **What wallet addresses need monitoring?**
   ```
   Wallet 1: 0x_________________________ (Treasury)
   Wallet 2: 0x_________________________ (Market Making)
   Wallet 3: 0x_________________________ (Trading)
   ```

3. **ALKIMI Token Details on Sui:**
   ```
   Token Address: 0x_________________________
   Token Decimals: ___
   Main Trading Pairs: ALKIMI/USDT, ALKIMI/SUI, etc.
   ```

## Phase 1: Research (Do This First)

### Step 1: Verify DEX Listings
```bash
# Check if ALKIMI is listed on Cetus
# Visit: https://app.cetus.zone/
# Search for ALKIMI token
# Note the pool addresses and liquidity
```

### Step 2: Find Your Transactions
```bash
# Visit Sui Explorer: https://suiscan.xyz/
# Enter your wallet address
# Filter for swap transactions
# Save a few transaction hashes for testing
```

### Step 3: Test API Access
```bash
# Try fetching data from Cetus API
curl -X GET "https://api-sui.cetus.zone/v2/sui/pools" | jq .

# Or use Sui RPC
curl -X POST https://fullnode.mainnet.sui.io:443 \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"sui_getRecentTransactions","params":[]}'
```

## Phase 2: Quick Implementation (Start Here)

### Install Dependencies
```bash
# Add to requirements.txt
echo "pysui>=0.40.0" >> requirements.txt
pip install -r requirements.txt
```

### Create Directory Structure
```bash
mkdir -p src/exchanges/sui
touch src/exchanges/sui/__init__.py
touch src/exchanges/sui/base.py
touch src/exchanges/sui/cetus.py
touch src/exchanges/sui/parser.py
```

### Create Test Script
```bash
# Create scripts/test_sui_connection.py
python scripts/test_sui_connection.py --wallet YOUR_WALLET_ADDRESS
```

### Add Configuration
```python
# In config/settings.py, add:

# Sui DEX Configuration
SUI_WALLET_ADDRESSES = env.list('SUI_WALLET_ADDRESSES', default=[])
SUI_RPC_URL = env.str('SUI_RPC_URL', default='https://fullnode.mainnet.sui.io')

# Parse wallet configs
sui_wallets = []
for addr in SUI_WALLET_ADDRESSES:
    # Format: address:label:dexs
    # Example: 0x123...:TREASURY:cetus,turbos
    parts = addr.split(':')
    sui_wallets.append({
        'address': parts[0],
        'account_name': parts[1] if len(parts) > 1 else 'MAIN',
        'dexs': parts[2].split(',') if len(parts) > 2 else ['cetus']
    })
```

### Update .env
```bash
# Add to .env
SUI_WALLET_ADDRESSES=0xYOUR_WALLET:TREASURY:cetus,0xANOTHER:MM1:cetus
SUI_RPC_URL=https://fullnode.mainnet.sui.io
```

## Phase 3: Integration with Existing System

### The existing system already supports DEX integration!

**No changes needed to:**
- TradeCache (already supports any exchange name)
- Trade dataclass (works for DEX trades)
- Reporting scripts (will automatically include DEX data)

**Only need to add:**
1. DEX client implementations
2. Transaction parsing logic
3. Configuration for wallets

### Integration Points

```python
# In main.py, add DEX clients alongside CEX clients:

from src.exchanges.sui.cetus import CetusClient

# After initializing CEX clients...
dex_clients = []

for wallet in settings.sui_wallets:
    if 'cetus' in wallet['dexs']:
        client = CetusClient(
            wallet_address=wallet['address'],
            config={'sui_rpc_url': settings.sui_rpc_url},
            account_name=wallet['account_name']
        )
        await client.initialize()
        dex_clients.append(client)

# Fetch trades (same as CEX)
for client in dex_clients:
    trades = await client.get_trades(since=data_window_start)
    cache.save_trades(trades, client.exchange_name, client.account_name)
```

**That's it!** Your existing reporting scripts will now include DEX trades.

## Reporting Output Examples

### Before (CEX Only)
```
BREAKDOWN BY EXCHANGE:
🔴 mexc/MM1         139 sells    1,030,816 ALKIMI
```

### After (CEX + DEX)
```
BREAKDOWN BY EXCHANGE:
🔴 mexc/MM1         139 sells    1,030,816 ALKIMI
🟢 cetus/TREASURY    45 buys       250,000 ALKIMI
🔴 cetus/MM1         12 sells       50,000 ALKIMI
```

## Key Implementation Details

### Buy vs Sell Detection
```python
def determine_side(token_in: str, token_out: str) -> TradeSide:
    """
    Determine if swap is buy or sell from perspective of ALKIMI holder.

    token_in: What you gave up
    token_out: What you received
    """
    if token_out == 'ALKIMI':
        return TradeSide.BUY   # You bought ALKIMI
    elif token_in == 'ALKIMI':
        return TradeSide.SELL  # You sold ALKIMI
    else:
        raise ValueError("Transaction doesn't involve ALKIMI")
```

### Price Calculation
```python
def calculate_price(amount_alkimi: float, amount_usdt: float, side: TradeSide) -> float:
    """
    Calculate effective price per ALKIMI.

    Returns: Price in USDT per ALKIMI
    """
    if side == TradeSide.SELL:
        # You sold X ALKIMI for Y USDT
        # Price = USDT received / ALKIMI sold
        return amount_usdt / amount_alkimi
    else:
        # You bought X ALKIMI for Y USDT
        # Price = USDT spent / ALKIMI received
        return amount_usdt / amount_alkimi
```

### Fee Aggregation
```python
def calculate_total_fee(tx_data: dict) -> float:
    """
    Aggregate all fees in DEX transaction.

    DEX fees include:
    - LP swap fee (e.g., 0.3% of trade)
    - Protocol fee (if any)
    - Gas fee (in SUI, convert to USDT)
    """
    lp_fee = tx_data['swap_fee']  # In USDT
    gas_sui = tx_data['gas_used'] * tx_data['gas_price']
    gas_usdt = gas_sui * get_sui_price()  # Convert SUI → USDT

    return lp_fee + gas_usdt
```

## Testing Checklist

- [ ] Can fetch transactions from DEX API/RPC
- [ ] Parser correctly identifies ALKIMI swaps
- [ ] Buy vs sell determination is accurate
- [ ] Prices match what you expect from DEX UI
- [ ] Fees are calculated correctly
- [ ] Trades save to cache without duplicates
- [ ] Reporting scripts show DEX trades
- [ ] Slack notifications include DEX activity

## Troubleshooting

### "No trades found"
- Verify wallet address format (Sui uses 0x prefix)
- Check if wallet actually has transactions on that DEX
- Ensure time range is correct
- Check API rate limits

### "Invalid price calculation"
- Verify token decimals are correct
- Check if you're handling decimals properly
- Ensure you're using correct quote currency (USDT vs SUI)

### "Duplicate trades in cache"
- Use transaction hash as trade_id
- Ensure uniqueness constraint in database works
- Check timestamp format consistency

## Timeline Estimate

- **Week 1**: Research + Basic Cetus integration (5-7 days)
- **Week 2**: Testing + Additional DEXs (5-7 days)
- **Week 3**: Polish + Documentation (3-5 days)

**Total**: ~2-3 weeks for full integration

## Success Metrics

After integration, you should be able to:
1. Run `python scripts/recent_activity.py` and see both CEX and DEX trades
2. Run `python scripts/price_impact.py` and get complete market view
3. Get Slack notifications for all trading activity
4. Track total P&L including DEX gas costs

## Next Steps

1. Complete the research questions at the top
2. Read the full plan: `docs/SUI_DEX_INTEGRATION_PLAN.md`
3. Start with Phase 1 (Research)
4. Create test script for connection validation
5. Implement Cetus adapter
6. Test with real data
7. Expand to other DEXs

## Resources

- **Cetus Docs**: https://cetus-1.gitbook.io/cetus-docs
- **Sui RPC Docs**: https://docs.sui.io/references/sui-api
- **Sui Explorer**: https://suiscan.xyz/
- **Full Integration Plan**: `docs/SUI_DEX_INTEGRATION_PLAN.md`

---

**Questions?** Review the detailed plan or start with Phase 1 research to validate assumptions.
