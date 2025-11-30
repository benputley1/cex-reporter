# Proposed Directory Structure After Sui DEX Integration

```
cex-reporter/
├── README.md                        # Updated with DEX integration notes
├── requirements.txt                 # Add: pysui>=0.40.0
├── .env                            # Add: SUI_WALLET_ADDRESSES, SUI_RPC_URL
├── .env.example                    # Updated with Sui config examples
│
├── main.py                         # Updated to include DEX clients
│
├── config/
│   ├── __init__.py
│   └── settings.py                 # Add: SUI wallet and RPC configuration
│
├── src/
│   ├── exchanges/
│   │   ├── __init__.py
│   │   ├── base.py                 # ExchangeInterface (unchanged)
│   │   │
│   │   ├── mexc.py                 # Existing CEX adapters
│   │   ├── kraken.py
│   │   ├── kucoin.py
│   │   ├── gateio.py
│   │   │
│   │   └── sui/                    # 🆕 NEW: Sui DEX adapters
│   │       ├── __init__.py
│   │       ├── base.py             # SuiDexBase abstract class
│   │       ├── parser.py           # Transaction parsing utilities
│   │       ├── cetus.py            # Cetus Protocol adapter
│   │       ├── turbos.py           # Turbos Finance adapter
│   │       ├── aftermath.py        # Aftermath Finance adapter
│   │       └── deepbook.py         # DeepBook adapter
│   │
│   ├── analytics/
│   │   ├── portfolio.py            # May add DEX-specific metrics
│   │   └── pnl.py                  # May include gas cost tracking
│   │
│   ├── reporting/
│   │   ├── formatter.py            # May add DEX formatting
│   │   └── slack.py                # Unchanged
│   │
│   ├── data/
│   │   └── trade_cache.py          # Unchanged (already supports DEX)
│   │
│   └── utils/
│       ├── cache.py                # Unchanged
│       └── logging.py              # Unchanged
│
├── scripts/                        # Existing utility scripts
│   ├── check_balances.py           # Unchanged (will auto-include DEX)
│   ├── recent_activity.py          # Unchanged (will auto-include DEX)
│   ├── price_impact.py             # Unchanged (will auto-include DEX)
│   ├── cache_stats.py              # Unchanged
│   │
│   ├── test_sui_connection.py      # 🆕 NEW: Test Sui connectivity
│   ├── check_sui_balances.py       # 🆕 NEW: DEX-specific balance check
│   └── dex_analysis.py             # 🆕 NEW: DEX-specific analytics
│
├── tests/
│   ├── test_exchanges.py           # Add: DEX adapter tests
│   ├── test_analytics.py           # Unchanged
│   ├── test_reporting.py           # Unchanged
│   │
│   └── test_sui/                   # 🆕 NEW: Sui-specific tests
│       ├── __init__.py
│       ├── test_parser.py          # Transaction parsing tests
│       ├── test_cetus.py           # Cetus adapter tests
│       └── fixtures/               # Sample transaction data
│           ├── alkimi_buy.json
│           ├── alkimi_sell.json
│           └── multi_hop_swap.json
│
├── data/
│   └── trade_cache.db              # Unchanged (will store DEX trades)
│
├── docs/                           # 🆕 NEW: Documentation
│   ├── SUI_DEX_INTEGRATION_PLAN.md      # Full integration plan
│   ├── SUI_DEX_QUICK_START.md           # Quick reference guide
│   ├── PROPOSED_STRUCTURE.md            # This file
│   ├── TROUBLESHOOTING_DEX.md           # DEX-specific troubleshooting
│   └── API_REFERENCES.md                # DEX API documentation links
│
├── archive/                        # Existing archived scripts
│   ├── README.md
│   └── [old test files...]
│
└── logs/                           # Application logs
    └── [log files...]
```

## Key Changes Summary

### 🆕 New Directories
- `src/exchanges/sui/` - All Sui DEX adapter implementations
- `tests/test_sui/` - Sui-specific test files
- `docs/` - Documentation and plans

### 🆕 New Files
**Source Code:**
- `src/exchanges/sui/base.py` - Abstract base for DEX adapters
- `src/exchanges/sui/parser.py` - Transaction parsing logic
- `src/exchanges/sui/cetus.py` - Cetus Protocol implementation
- `src/exchanges/sui/turbos.py` - Turbos Finance implementation
- `src/exchanges/sui/aftermath.py` - Aftermath Finance implementation
- `src/exchanges/sui/deepbook.py` - DeepBook implementation

**Scripts:**
- `scripts/test_sui_connection.py` - Validate Sui API connectivity
- `scripts/check_sui_balances.py` - DEX wallet balance checker
- `scripts/dex_analysis.py` - DEX-specific analytics

**Tests:**
- `tests/test_sui/test_parser.py` - Transaction parsing tests
- `tests/test_sui/test_cetus.py` - Cetus adapter integration tests
- `tests/test_sui/fixtures/*.json` - Sample transaction data

**Documentation:**
- `docs/SUI_DEX_INTEGRATION_PLAN.md` - Complete implementation plan
- `docs/SUI_DEX_QUICK_START.md` - Quick start guide
- `docs/TROUBLESHOOTING_DEX.md` - DEX troubleshooting guide
- `docs/API_REFERENCES.md` - DEX API documentation

### ✏️ Modified Files
**Configuration:**
- `config/settings.py` - Add SUI wallet and RPC URL settings
- `.env` - Add SUI_WALLET_ADDRESSES and SUI_RPC_URL
- `.env.example` - Add example Sui configuration
- `requirements.txt` - Add `pysui>=0.40.0`

**Main Application:**
- `main.py` - Initialize DEX clients alongside CEX clients

**Documentation:**
- `README.md` - Add DEX integration section

### 🔄 Unchanged Files (DEX data flows through automatically)
- `src/data/trade_cache.py` - Already supports any exchange
- `scripts/check_balances.py` - Auto-includes DEX balances
- `scripts/recent_activity.py` - Auto-includes DEX trades
- `scripts/price_impact.py` - Auto-includes DEX trades
- `src/reporting/slack.py` - Works with DEX data

## Implementation Order

1. **Phase 1**: Create `docs/` and research
2. **Phase 2**: Create `src/exchanges/sui/` with base classes
3. **Phase 3**: Implement Cetus adapter
4. **Phase 4**: Create test scripts
5. **Phase 5**: Update configuration files
6. **Phase 6**: Add tests
7. **Phase 7**: Implement additional DEX adapters
8. **Phase 8**: Create DEX-specific scripts

## Database Impact

**No schema changes required!** The existing schema already supports DEX data:

```sql
CREATE TABLE IF NOT EXISTS trades (
    exchange TEXT NOT NULL,        -- 'cetus', 'turbos', etc.
    account_name TEXT NOT NULL,    -- Wallet label like 'TREASURY'
    trade_id TEXT,                 -- Transaction hash
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,
    side TEXT NOT NULL,
    amount REAL NOT NULL,
    price REAL NOT NULL,
    fee REAL NOT NULL,
    ...
)
```

**Optional**: Add metadata column for advanced DEX analytics:
```sql
ALTER TABLE trades ADD COLUMN metadata TEXT;  -- JSON: pool_id, slippage, etc.
```

## Backward Compatibility

**100% backward compatible!**
- All existing scripts work unchanged
- CEX functionality unaffected
- DEX data simply appears alongside CEX data
- Can be deployed incrementally (one DEX at a time)

## Deployment Strategy

### Option 1: All at Once
```bash
git checkout -b feature/sui-dex-integration
# Implement all changes
# Test thoroughly
git merge to main
```

### Option 2: Incremental (Recommended)
```bash
# Step 1: Add docs
git checkout -b docs/sui-dex-plan
git commit -m "Add Sui DEX integration documentation"

# Step 2: Add Cetus adapter
git checkout -b feature/cetus-adapter
git commit -m "Add Cetus Protocol support"

# Step 3: Add other DEXs
git checkout -b feature/additional-dexs
git commit -m "Add Turbos and Aftermath support"
```

## Testing Approach

### Unit Tests
```bash
pytest tests/test_sui/test_parser.py -v
```

### Integration Tests
```bash
pytest tests/test_sui/test_cetus.py --integration -v
```

### End-to-End Tests
```bash
python scripts/test_sui_connection.py --wallet 0xYOUR_WALLET
python main.py --mode once  # Should include DEX trades
python scripts/recent_activity.py  # Should show DEX activity
```

## Rollback Plan

If issues arise, DEX integration can be disabled without affecting CEX functionality:

```python
# In config/settings.py
ENABLE_SUI_DEX = env.bool('ENABLE_SUI_DEX', default=False)

# In main.py
if settings.ENABLE_SUI_DEX:
    # Initialize DEX clients
    pass
```

Set `ENABLE_SUI_DEX=false` in `.env` to disable.

---

**Document Status**: Proposed structure for review
**Last Updated**: 2025-11-07
