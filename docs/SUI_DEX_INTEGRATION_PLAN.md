cre# Sui DEX Integration Plan

## Executive Summary
This document outlines the plan to integrate Sui blockchain DEX trades into the existing CEX Reporter system, enabling consolidated reporting across both centralized exchanges (CEXs) and decentralized exchanges (DEXs) on Sui network.

## 1. Current Architecture Analysis

### Existing Components
- **Exchange Interface**: Abstract base class (`ExchangeInterface`) that all exchange adapters implement
- **Trade Data Model**: Standardized `Trade` dataclass with fields: timestamp, symbol, side, amount, price, fee
- **Trade Cache**: SQLite database storing trades with exchange/account identification
- **Reporting Scripts**:
  - `price_impact.py` - Market impact analysis
  - `recent_activity.py` - Trading activity summary
  - `check_balances.py` - Current balance checker
  - `cache_stats.py` - Cache statistics

### Key Constraints
- All exchanges must implement the `ExchangeInterface` abstract methods
- Trades must conform to the `Trade` dataclass structure
- TradeCache expects `exchange` and `account_name` identifiers
- Current system assumes ALKIMI/USDT trading pairs

## 2. Sui DEX Landscape Research

### Major Sui DEXs Likely to List ALKIMI
1. **Cetus Protocol** (Leading Sui DEX)
   - Concentrated liquidity AMM
   - API: REST API + GraphQL
   - Best option for initial integration

2. **Turbos Finance**
   - Concentrated liquidity protocol
   - API: GraphQL API

3. **Aftermath Finance**
   - Multi-pool AMM
   - API: REST API

4. **DeepBook** (Sui Native Order Book)
   - Native to Sui blockchain
   - API: Via Sui RPC nodes

5. **KriyaDEX**
   - Order book + AMM hybrid
   - API: REST API + GraphQL

### Data Sources
**Option A: DEX-Specific APIs** (Recommended)
- Pros: Easier to implement, formatted data, rate limit control
- Cons: Requires API keys, may have data retention limits
- Example: Cetus API, Turbos GraphQL

**Option B: Sui Blockchain Direct Queries**
- Pros: Complete historical data, no API keys needed
- Cons: Complex parsing, requires understanding transaction structure, higher latency
- Tools: Sui RPC nodes, Sui GraphQL

**Option C: Blockchain Data Aggregators**
- Pros: Normalized data across DEXs, easier integration
- Cons: Third-party dependency, potential costs
- Examples: Coin
Gecko API, Birdeye API, DefiLlama

## 3. Technical Architecture

### 3.1 New Components to Build

#### A. Sui DEX Base Adapter (`src/exchanges/sui_dex_base.py`)
```python
class SuiDexBase(ExchangeInterface):
    """
    Abstract base for Sui DEX integrations.
    Handles common Sui blockchain interactions.
    """
    - Wallet address tracking
    - Transaction parsing
    - Price normalization (handle decimals)
    - Fee calculation from blockchain data
```

#### B. Specific DEX Implementations
```
src/exchanges/sui/
├── __init__.py
├── cetus.py           # Cetus Protocol adapter
├── turbos.py          # Turbos Finance adapter
├── aftermath.py       # Aftermath Finance adapter
└── deepbook.py        # DeepBook adapter
```

#### C. Sui Transaction Parser (`src/exchanges/sui/parser.py`)
```python
class SuiTransactionParser:
    """
    Parse Sui blockchain transactions into Trade objects.
    """
    - parse_swap_transaction()
    - extract_amounts()
    - determine_side() (buy vs sell)
    - calculate_effective_price()
    - extract_fees()
```

#### D. Configuration Extensions (`config/settings.py`)
```python
# Add to settings:
SUI_WALLET_ADDRESSES = [
    {
        'address': '0x...',
        'label': 'Treasury Wallet 1',
        'dexs': ['cetus', 'turbos']  # Which DEXs to monitor
    }
]
SUI_RPC_URL = 'https://fullnode.mainnet.sui.io'
```

### 3.2 Data Mapping Challenges

#### Challenge 1: Buy vs Sell Determination
**CEX**: Explicit side field in API response
**DEX**: Must infer from transaction direction
- Solution: Compare input/output tokens
  - If ALKIMI out → SELL
  - If ALKIMI in → BUY

#### Challenge 2: Price Calculation
**CEX**: Direct price field in API
**DEX**: Calculate from swap amounts
- Solution: `price = quote_amount / base_amount`
- Handle token decimals correctly
- Account for slippage in swaps

#### Challenge 3: Fee Structure
**CEX**: Single fee field in quote currency
**DEX**: Multiple fee types (LP fee, protocol fee, gas)
- Solution: Aggregate all fees, convert to USDT equivalent
- Store detailed breakdown in metadata if needed

#### Challenge 4: Trade Identification
**CEX**: Unique trade_id from exchange
**DEX**: Use transaction hash as trade_id
- Solution: Prefix with DEX name: `cetus_0x1234...`

#### Challenge 5: Account Identification
**CEX**: API key = account
**DEX**: Wallet address = account
- Solution: Store wallet addresses in config with labels
- Use label as `account_name` in cache

### 3.3 Database Schema Updates

The existing schema already supports DEX integration well:
```sql
CREATE TABLE IF NOT EXISTS trades (
    exchange TEXT NOT NULL,        -- 'cetus', 'turbos', etc.
    account_name TEXT NOT NULL,    -- Wallet label
    trade_id TEXT,                 -- Transaction hash
    timestamp TEXT NOT NULL,
    symbol TEXT NOT NULL,          -- 'ALKIMI'
    side TEXT NOT NULL,            -- 'buy' or 'sell'
    amount REAL NOT NULL,
    price REAL NOT NULL,
    fee REAL NOT NULL,
    fee_currency TEXT,
    ...
)
```

**Optional Enhancement**: Add metadata column for DEX-specific data
```sql
ALTER TABLE trades ADD COLUMN metadata TEXT;  -- JSON blob
-- Store: pool_id, liquidity, slippage, tx_hash, etc.
```

## 4. Implementation Phases

### Phase 1: Research & Proof of Concept (Week 1)
**Goals:**
- Identify which Sui DEXs actually list ALKIMI
- Verify wallet addresses that need monitoring
- Test API access for chosen DEXs
- Create simple script to fetch one transaction

**Deliverables:**
- List of DEXs to integrate (prioritized)
- API documentation collection
- Test transaction data samples
- `scripts/test_sui_connection.py` - Basic connectivity test

**Estimated Effort**: 2-3 days

### Phase 2: Core DEX Adapter (Week 1-2)
**Goals:**
- Implement `SuiDexBase` abstract class
- Build Cetus Protocol adapter (most popular)
- Create transaction parser
- Implement trade normalization logic

**Files to Create:**
```
src/exchanges/sui/
├── __init__.py
├── base.py              # SuiDexBase class
├── cetus.py             # Cetus implementation
└── parser.py            # Transaction parsing utilities
```

**Key Methods:**
```python
class CetusClient(SuiDexBase):
    async def get_trades(self, since: datetime) -> List[Trade]:
        # 1. Query Cetus API for swap transactions
        # 2. Filter by wallet address
        # 3. Parse transactions into Trade objects
        # 4. Return normalized trades

    async def get_balances(self) -> Dict[str, float]:
        # Query on-chain balances for wallet

    async def get_prices(self, symbols: List[str]) -> Dict[str, float]:
        # Get current pool prices
```

**Testing:**
- Unit tests for transaction parsing
- Integration test with live API
- Validate Trade object creation

**Estimated Effort**: 3-4 days

### Phase 3: Configuration & Integration (Week 2)
**Goals:**
- Add Sui wallet configuration to settings
- Update main.py to include DEX clients
- Integrate with existing TradeCache
- Test end-to-end data flow

**Configuration Example:**
```python
# config/settings.py
sui_wallets = [
    {
        'address': '0xYOUR_WALLET_ADDRESS',
        'account_name': 'TREASURY',
        'dexs': ['cetus']  # Which DEXs this wallet trades on
    }
]
```

**Main.py Updates:**
```python
# Add alongside CEX initialization
from src.exchanges.sui.cetus import CetusClient

# Initialize Sui DEX clients
sui_clients = []
for wallet in settings.sui_wallets:
    if 'cetus' in wallet['dexs']:
        client = CetusClient(
            wallet_address=wallet['address'],
            account_name=wallet['account_name']
        )
        await client.initialize()
        sui_clients.append(client)

# Existing trade fetching logic works the same
for client in sui_clients:
    trades = await client.get_trades(since=data_window_start)
    cache.save_trades(trades, client.exchange_name, client.account_name)
```

**Estimated Effort**: 2 days

### Phase 4: Additional DEX Support (Week 3)
**Goals:**
- Implement 2-3 additional DEX adapters
- Create unified wallet balance checker across DEXs
- Add DEX-specific error handling

**Files:**
```
src/exchanges/sui/turbos.py
src/exchanges/sui/aftermath.py
scripts/check_sui_balances.py
```

**Estimated Effort**: 2-3 days

### Phase 5: Enhanced Reporting (Week 3-4)
**Goals:**
- Update reporting scripts to distinguish CEX vs DEX
- Add DEX-specific metrics (gas costs, slippage)
- Create new utility scripts for DEX analysis

**Script Updates:**
- `price_impact.py` - Add CEX vs DEX breakdown
- `recent_activity.py` - Show DEX activity separately
- Create `scripts/dex_analysis.py` - DEX-specific insights

**New Metrics:**
- Total gas spent on DEX trades
- Average slippage per trade
- Best execution venue (CEX vs DEX price comparison)

**Estimated Effort**: 2-3 days

### Phase 6: Testing & Documentation (Week 4)
**Goals:**
- Comprehensive testing across all DEX adapters
- Performance testing with large datasets
- User documentation
- Deployment guide

**Testing Checklist:**
- [ ] All DEX adapters fetch trades correctly
- [ ] Trades cache properly with deduplication
- [ ] Reporting scripts show correct aggregated data
- [ ] Error handling for network issues
- [ ] Rate limiting works correctly
- [ ] Historical data backfill completes successfully

**Documentation:**
- Update README with DEX setup instructions
- Create TROUBLESHOOTING.md for DEX-specific issues
- API key/wallet setup guide

**Estimated Effort**: 2-3 days

## 5. Risk Assessment & Mitigations

### Risk 1: DEX API Instability
**Impact**: High - Could break trade fetching
**Probability**: Medium
**Mitigation**:
- Implement robust error handling with retries
- Use blockchain fallback if API fails
- Monitor API health proactively

### Risk 2: Complex Transaction Parsing
**Impact**: High - Incorrect trade data
**Probability**: High
**Mitigation**:
- Start with simplest DEX (Cetus)
- Extensive unit testing with real transaction samples
- Manual verification of first 100 transactions
- Gradual rollout with monitoring

### Risk 3: Token Decimal Handling
**Impact**: Critical - Wrong amounts/prices
**Probability**: Medium
**Mitigation**:
- Always fetch token metadata (decimals) from chain
- Create utility function for decimal normalization
- Add validation checks (sanity ranges for prices)

### Risk 4: Gas Cost Tracking
**Impact**: Medium - Incomplete P&L picture
**Probability**: Low
**Mitigation**:
- Parse gas from transaction receipts
- Convert SUI gas to USDT for cost basis
- Include in trade fee calculation

### Risk 5: Rate Limiting
**Impact**: Medium - Slower data fetching
**Probability**: Medium
**Mitigation**:
- Implement exponential backoff
- Cache aggressively
- Consider running own Sui RPC node

## 6. Dependencies & Prerequisites

### Python Packages
```bash
# Add to requirements.txt
pysui>=0.40.0              # Sui SDK for Python
aiohttp>=3.9.0             # Already installed
web3>=6.0.0                # For hex/address handling
```

### External Services
1. **Sui RPC Node Access**
   - Option A: Public nodes (free, rate limited)
   - Option B: Private node (Alchemy, QuickNode)
   - Option C: Self-hosted node (most reliable)

2. **DEX API Keys** (if required)
   - Cetus: Check if API key needed
   - Turbos: Check requirements
   - Others: TBD based on research

### Configuration Requirements
- Sui wallet addresses to monitor
- Which DEXs each wallet trades on
- Acceptable DEX list (whitelist approach)

## 7. Success Metrics

### Technical Metrics
- [ ] All DEX trades fetched within 5 minutes of occurrence
- [ ] <1% error rate in trade parsing
- [ ] 100% cache hit rate for historical data
- [ ] Reports generate in <10 seconds including DEX data

### Business Metrics
- [ ] Complete view of ALKIMI trading activity (CEX + DEX)
- [ ] Accurate P&L including DEX gas costs
- [ ] Identify arbitrage opportunities between CEX and DEX
- [ ] Track DEX vs CEX execution quality

## 8. Future Enhancements (Post-MVP)

### Phase 2 Features
1. **Cross-Chain Integration**
   - Support ALKIMI on other chains (Ethereum, etc.)
   - Unified reporting across all chains

2. **Advanced DEX Analytics**
   - Liquidity provider position tracking
   - Impermanent loss calculation
   - Pool health monitoring

3. **Automated Alerts**
   - Large trades on DEX (> $X threshold)
   - Unusual price deviation CEX vs DEX
   - Low liquidity warnings

4. **DEX Trade Simulation**
   - Estimate execution before trading
   - Compare routes across multiple DEXs
   - Gas optimization suggestions

## 9. Open Questions (To Resolve in Phase 1)

1. **Which Sui DEXs actually have ALKIMI liquidity?**
   - Need to verify ALKIMI listing status
   - Check trading volumes

2. **What wallet addresses need monitoring?**
   - Treasury wallets
   - Market making wallets
   - Any other relevant addresses

3. **Historical data availability?**
   - How far back can we fetch DEX trades?
   - Do we need to backfill from blockchain?

4. **API rate limits?**
   - What are the limits for each DEX API?
   - Do we need paid tiers?

5. **Token contract addresses?**
   - What is ALKIMI's token address on Sui?
   - Any wrapped versions to track?

## 10. Getting Started

### Immediate Next Steps
1. **Research Phase** (You can do this now):
   - Check which Sui DEXs list ALKIMI
   - Identify your Sui wallet addresses
   - Review DEX API documentation
   - Collect sample transaction data

2. **Quick Win** - Manual Integration Test:
   ```bash
   # Create a quick script to fetch one DEX transaction
   python scripts/test_sui_fetch.py --wallet 0xYOUR_ADDRESS --dex cetus
   ```

3. **Decision Points**:
   - Confirm which DEXs to prioritize (based on volume)
   - Choose API vs blockchain direct query approach
   - Set timeline for integration (2-4 weeks realistic)

### Recommended Approach
**Start with Cetus Protocol only** - It's likely the most liquid Sui DEX. Once that's working and integrated into your reporting, expand to other DEXs incrementally.

This phased approach minimizes risk and delivers value quickly while building toward comprehensive coverage.

---

## Appendix A: Code Templates

### Template: DEX Client Structure
```python
# src/exchanges/sui/cetus.py
from typing import List, Dict
from datetime import datetime
from src.exchanges.base import ExchangeInterface, Trade, TradeSide

class CetusClient(ExchangeInterface):
    """Cetus Protocol DEX adapter for Sui blockchain"""

    def __init__(self, wallet_address: str, config: Dict = None,
                 mock_mode: bool = False, account_name: str = None):
        super().__init__(
            exchange_name='cetus',
            config=config or {},
            mock_mode=mock_mode,
            account_name=account_name
        )
        self.wallet_address = wallet_address
        self.rpc_url = config.get('sui_rpc_url', 'https://fullnode.mainnet.sui.io')

    async def initialize(self):
        """Initialize connection to Cetus API and Sui RPC"""
        # Set up HTTP clients, verify wallet address format
        self._initialized = True

    async def get_trades(self, since: datetime) -> List[Trade]:
        """Fetch swap transactions for wallet since datetime"""
        # 1. Query Cetus pools for ALKIMI
        # 2. Get swap transactions involving wallet address
        # 3. Parse into Trade objects
        # 4. Return chronologically sorted list
        pass

    async def get_balances(self) -> Dict[str, float]:
        """Query on-chain balances for wallet"""
        pass

    async def get_prices(self, symbols: List[str]) -> Dict[str, float]:
        """Get current prices from Cetus pools"""
        pass

    async def close(self):
        """Cleanup resources"""
        pass
```

### Template: Transaction Parser
```python
# src/exchanges/sui/parser.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

@dataclass
class ParsedSwap:
    """Intermediate representation of DEX swap"""
    tx_hash: str
    timestamp: datetime
    token_in: str
    amount_in: float
    token_out: str
    amount_out: float
    gas_used: float
    gas_price: float

def parse_cetus_transaction(tx_data: dict) -> Optional[Trade]:
    """
    Parse Cetus transaction into Trade object.

    Args:
        tx_data: Raw transaction data from Cetus API or Sui RPC

    Returns:
        Trade object or None if not a valid swap
    """
    # Extract relevant fields
    # Determine if ALKIMI buy or sell
    # Calculate effective price
    # Normalize decimals
    # Return Trade object
    pass
```

## Appendix B: Testing Strategy

### Unit Tests
```python
# tests/test_sui_parser.py
def test_parse_alkimi_sell():
    """Test parsing ALKIMI → USDT swap"""
    tx_data = load_sample_transaction('alkimi_sell.json')
    trade = parse_cetus_transaction(tx_data)

    assert trade.symbol == 'ALKIMI'
    assert trade.side == TradeSide.SELL
    assert trade.amount > 0
    assert trade.price > 0

def test_parse_alkimi_buy():
    """Test parsing USDT → ALKIMI swap"""
    # Similar test for buy side
    pass

def test_decimal_normalization():
    """Ensure token decimals handled correctly"""
    # ALKIMI might use 6 decimals, USDT uses 6, etc.
    pass
```

### Integration Tests
```python
# tests/test_cetus_integration.py
@pytest.mark.asyncio
async def test_fetch_recent_trades():
    """Test fetching trades from live API"""
    client = CetusClient(
        wallet_address=TEST_WALLET,
        mock_mode=False
    )
    await client.initialize()

    since = datetime.now() - timedelta(days=7)
    trades = await client.get_trades(since)

    assert isinstance(trades, list)
    if trades:
        assert all(isinstance(t, Trade) for t in trades)

    await client.close()
```

---

**Document Version**: 1.0
**Last Updated**: 2025-11-07
**Status**: Draft - Awaiting Research Phase Completion
