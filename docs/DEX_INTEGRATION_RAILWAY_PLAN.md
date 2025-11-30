# DEX Integration + Railway Deployment Plan
## HFT-Ready CEX Reporter Enhancement

**Objective:** Provide complete CEX + DEX trading visibility by Monday for HFT trader, with Railway deployment and comprehensive P&L + treasury value tracking targeting £500k/month revenue.

**Timeline:** 2 days (Nov 29-30, 2025)

---

## Executive Summary

### Key Insight: Smart Contract Tracking > Individual DEX APIs
Instead of integrating Cetus, Bluefin, and Turbos separately, we'll track the **ALKIMI token contract on Sui** to capture ALL DEX trades regardless of venue. This approach:
- Captures 100% of DEX activity (not just known DEXs)
- Single integration point vs 3+ separate APIs
- Future-proof for new DEX listings
- Simpler implementation

### Current State
- **CEX Integration:** 4 exchanges, 12 accounts, working well ($417K sell proceeds tracked)
- **DEX Integration:** Cetus 70% built (positions only, no trade history)
- **Deployment:** Local only, no Docker/Railway
- **Critical Issues:** Hardcoded paths, credentials in .env.example, no DB migrations

### Target State (Monday)
- Complete DEX trade visibility via Sui blockchain monitoring
- Key wallet tracking for treasury movements
- Railway deployment with PostgreSQL persistence
- Unified CEX + DEX reporting in Slack
- Treasury value tracking (realized + unrealized)

---

## Phase 1: Critical Fixes & Deployment Prep (4-6 hours)

### 1.1 Security & Configuration Fixes

**Remove credentials from .env.example:**
```bash
# Replace actual keys with placeholders
MEXC_MM1_API_KEY=your_mexc_mm1_api_key_here
```

**Add missing environment variables to settings.py:**
```python
TRADE_CACHE_DB = os.getenv('TRADE_CACHE_DB', 'data/trade_cache.db')
LOG_DIR = os.getenv('LOG_DIR', 'logs')
DATA_DIR = os.getenv('DATA_DIR', 'data')
DEPOSITS_FILE = os.getenv('DEPOSITS_FILE', 'deposits & withdrawals.xlsx')
```

**Fix hardcoded paths:**
- `src/data/deposits_loader.py:28-31` - Use env var
- `src/data/trade_cache.py:23` - Use env var
- `src/utils/logging.py:143` - Use env var

### 1.2 Docker Configuration

**Create Dockerfile:**
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PYTHONUNBUFFERED=1
CMD ["python", "main.py", "--mode", "continuous"]
```

**Create docker-compose.yml:**
```yaml
version: '3.8'
services:
  cex-reporter:
    build: .
    env_file: .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
    restart: unless-stopped
```

### 1.3 Railway Configuration

**Create railway.toml:**
```toml
[build]
builder = "dockerfile"

[deploy]
startCommand = "python main.py --mode continuous"
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

**Environment variables for Railway:**
- All exchange API keys
- `MOCK_MODE=false`
- `LOG_LEVEL=INFO`
- `REPORT_INTERVAL=3600` (1 hour for HFT visibility)

---

## Phase 2: Sui Blockchain Integration (6-8 hours)

### 2.1 Architecture: Token Contract Monitoring

**Approach:** Query Sui blockchain for ALL transactions involving the ALKIMI token contract, then filter for swap events across any DEX.

**New file: `src/exchanges/sui_monitor.py`**
```python
class SuiTokenMonitor:
    """
    Monitor ALKIMI token contract on Sui for all DEX trades.
    Captures swaps from Cetus, Bluefin, Turbos, and any other DEX.
    """

    def __init__(self,
                 token_contract: str,  # ALKIMI contract address
                 wallet_addresses: List[str],  # Treasury/MM wallets
                 rpc_url: str = "https://fullnode.mainnet.sui.io"):
        self.token_contract = token_contract
        self.wallet_addresses = wallet_addresses
        self.rpc_url = rpc_url

    async def get_all_trades(self, since: datetime) -> List[Trade]:
        """Fetch all ALKIMI trades from any DEX since timestamp"""
        # 1. Query token transfer events
        # 2. Filter for swap patterns (paired with SUI/USDC transfers)
        # 3. Identify DEX from package address
        # 4. Parse into Trade objects
        pass

    async def get_wallet_balances(self) -> Dict[str, Dict[str, float]]:
        """Get ALKIMI + SUI balances for all monitored wallets"""
        pass

    async def get_treasury_value(self) -> TreasurySnapshot:
        """Calculate total treasury value (tokens * current price)"""
        pass
```

### 2.2 DEX Identification Logic

```python
# Known DEX package addresses on Sui
DEX_PACKAGES = {
    "0x1eabed72c53feb73c694be3b5f478fe4f4b": "cetus",
    "0x2c68443db9e8c813b194010c11040a3c": "bluefin",
    "0x91bfbc386a41afcfd9b2533058d7e91": "turbos",
}

def identify_dex(package_id: str) -> str:
    """Identify which DEX a swap occurred on"""
    for prefix, name in DEX_PACKAGES.items():
        if package_id.startswith(prefix):
            return name
    return "unknown_dex"
```

### 2.3 Configuration Updates

**Add to .env:**
```
# Sui Blockchain Configuration
SUI_RPC_URL=https://fullnode.mainnet.sui.io
ALKIMI_TOKEN_CONTRACT=0x...  # ALKIMI token address on Sui
SUI_WALLET_TREASURY=0x...    # Main treasury wallet
SUI_WALLET_MM1=0x...         # Market making wallet 1
SUI_WALLET_MM2=0x...         # Market making wallet 2
```

**Add to settings.py:**
```python
@property
def sui_config(self) -> Dict:
    return {
        'rpc_url': os.getenv('SUI_RPC_URL', 'https://fullnode.mainnet.sui.io'),
        'token_contract': os.getenv('ALKIMI_TOKEN_CONTRACT', ''),
        'wallets': self._parse_sui_wallets()
    }

def _parse_sui_wallets(self) -> List[Dict]:
    wallets = []
    for key, value in os.environ.items():
        if key.startswith('SUI_WALLET_'):
            name = key.replace('SUI_WALLET_', '')
            wallets.append({'address': value, 'name': name})
    return wallets
```

### 2.4 Dependencies

**Add to requirements.txt:**
```
pysui>=0.50.0        # Sui Python SDK
httpx>=0.25.0        # Modern async HTTP client
```

---

## Phase 3: Unified Reporting (3-4 hours)

### 3.1 Enhanced Trade Cache Schema

**Migration: Add DEX support and treasury tracking**
```sql
-- Add metadata column for DEX-specific data
ALTER TABLE trades ADD COLUMN metadata TEXT;
ALTER TABLE trades ADD COLUMN dex_name TEXT;

-- New table for treasury snapshots
CREATE TABLE treasury_snapshots (
    id INTEGER PRIMARY KEY,
    timestamp TEXT NOT NULL,
    total_alkimi REAL NOT NULL,
    alkimi_price REAL NOT NULL,
    total_value_usd REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    unrealized_pnl REAL NOT NULL,
    breakdown TEXT  -- JSON with per-wallet details
);
```

### 3.2 Updated SimpleTracker

**Modify `src/analytics/simple_tracker.py`:**

```python
async def get_report(self) -> Dict:
    # Existing CEX data
    cex_trades = await self._fetch_cex_trades()
    cex_balances = await self._fetch_cex_balances()

    # NEW: DEX data from Sui monitor
    dex_trades = await self.sui_monitor.get_all_trades(since=window_start)
    dex_balances = await self.sui_monitor.get_wallet_balances()

    # Combine for unified view
    all_trades = cex_trades + dex_trades

    # NEW: Treasury value calculation
    treasury = await self._calculate_treasury_value(cex_balances, dex_balances)

    return {
        'cex_activity': self._summarize_by_venue(cex_trades),
        'dex_activity': self._summarize_by_venue(dex_trades),
        'combined_pnl': self._calculate_combined_pnl(all_trades),
        'treasury_value': treasury,
        'holdings_by_venue': {...}
    }
```

### 3.3 Enhanced Slack Formatter

**Update `src/reporting/simple_formatter.py`:**

```python
def format_unified_report(self, report: Dict) -> str:
    """
    📊 ALKIMI TRADING REPORT

    💰 TREASURY VALUE
    Total: $X.XX (↑X.X% 24h)
    Realized P&L: $X.XX
    Unrealized P&L: $X.XX

    📈 CEX ACTIVITY (24h)
    MEXC: $XX,XXX (XXX trades)
    Gate.io: $XX,XXX (XXX trades)
    ...

    🌊 DEX ACTIVITY (24h)
    Cetus: $XX,XXX (XX swaps)
    Bluefin: $XX,XXX (XX swaps)
    Turbos: $XX,XXX (XX swaps)

    📊 COMBINED METRICS
    Total Volume: $XXX,XXX
    Net Position: +/-XXX,XXX ALKIMI
    Best Execution: [venue]
    """
```

---

## Phase 4: Code Quality & Efficiency (2-3 hours)

### 4.1 Extract Exchange Code Duplication

**Create `src/exchanges/ccxt_base.py`:**
```python
class CCXTBaseClient(ExchangeInterface):
    """
    Common functionality for all CCXT-based exchanges.
    Reduces ~40% code duplication across mexc.py, kraken.py, etc.
    """

    async def _paginated_fetch_trades(self, symbol, since, limit=500):
        """Shared pagination logic"""
        pass

    async def _safe_fetch_balance(self):
        """Shared balance fetching with error handling"""
        pass
```

### 4.2 Parallel Exchange Initialization

**Update main.py (lines 79-101):**
```python
# BEFORE: Sequential (27 seconds)
for exchange in exchanges:
    await exchange.initialize()

# AFTER: Parallel (3 seconds)
await asyncio.gather(*[ex.initialize() for ex in exchanges])
```

### 4.3 Remove Hardcoded Business Logic

**Move from simple_tracker.py to config:**
```python
# config/business_rules.py
OTC_TRANSACTIONS = [
    {
        'date': '2025-11-XX',
        'counterparty': 'RAMAN',
        'alkimi_amount': 3_000_000,
        'usd_cost': 82_000,
        'price': 0.027333333
    }
]
```

---

## Phase 5: Testing & Validation (2-3 hours)

### 5.1 Test Scripts

**Create `scripts/test_sui_connection.py`:**
```python
"""Test Sui RPC connectivity and token contract queries"""
async def main():
    monitor = SuiTokenMonitor(...)
    # Test RPC connection
    # Fetch sample transactions
    # Validate trade parsing
```

**Create `scripts/test_dex_trades.py`:**
```python
"""Validate DEX trade detection across all venues"""
async def main():
    trades = await monitor.get_all_trades(since=datetime.now() - timedelta(days=7))
    print(f"Found {len(trades)} DEX trades")
    for dex, count in groupby_dex(trades):
        print(f"  {dex}: {count}")
```

### 5.2 Validation Checklist

- [ ] Sui RPC connection works
- [ ] ALKIMI token contract queries return data
- [ ] Swap transactions correctly identified
- [ ] DEX venue correctly labeled
- [ ] Trade amounts/prices correctly parsed
- [ ] Wallet balances match on-chain
- [ ] Combined CEX + DEX report generates
- [ ] Slack message formats correctly
- [ ] Docker container runs successfully
- [ ] Railway deployment works

---

## File Changes Summary

### New Files
```
src/exchanges/sui_monitor.py      # Sui blockchain token monitoring
src/exchanges/ccxt_base.py        # Shared CCXT functionality
config/business_rules.py          # OTC and special transactions
scripts/test_sui_connection.py    # Sui connectivity test
scripts/test_dex_trades.py        # DEX trade validation
Dockerfile                        # Container configuration
docker-compose.yml                # Local development
railway.toml                      # Railway deployment config
```

### Modified Files
```
config/settings.py                # Add Sui config, fix paths
.env.example                      # Remove credentials, add Sui vars
src/data/trade_cache.py           # Add migrations, env var paths
src/data/deposits_loader.py       # Fix hardcoded paths
src/utils/logging.py              # Fix hardcoded paths
src/analytics/simple_tracker.py   # Add DEX integration, treasury value
src/reporting/simple_formatter.py # Add DEX sections to reports
main.py                           # Add Sui monitor, parallel init
requirements.txt                  # Add pysui, httpx
```

---

## Implementation Order (2 Days)

### Day 1 (Nov 29) - Foundation
1. **Morning:** Critical fixes (security, paths, env vars)
2. **Afternoon:** Docker + Railway configuration
3. **Evening:** Deploy basic CEX reporter to Railway

### Day 2 (Nov 30) - DEX Integration
1. **Morning:** Sui monitor implementation
2. **Afternoon:** Unified reporting + treasury tracking
3. **Evening:** Testing, validation, documentation

### Monday Ready
- HFT trader has complete visibility into:
  - All CEX trades (4 exchanges, 12 accounts)
  - All DEX trades (any Sui DEX via contract monitoring)
  - Treasury value (realized + unrealized)
  - Per-venue performance comparison
- System running on Railway with hourly reports

---

## Success Metrics

| Metric | Target |
|--------|--------|
| DEX trade capture rate | 100% (via contract monitoring) |
| Report latency | < 5 minutes from trade execution |
| System uptime | 99%+ on Railway |
| Treasury value accuracy | Within 1% of on-chain values |
| Combined P&L tracking | Realized + unrealized separated |

---

## Risk Mitigation

| Risk | Mitigation |
|------|------------|
| Sui RPC rate limits | Use dedicated RPC provider (Alchemy/QuickNode) if needed |
| Unknown DEX format | Log unrecognized swaps, add parsing incrementally |
| Railway cold starts | Use always-on Railway plan |
| Missing historical DEX data | Backfill from blockchain after initial deployment |

---

---

## Phase 6: Claude AI Analysis Layer (3-4 hours)

### 6.1 Architecture: AI-Powered Trading Insights

**Railway provides Claude API access** - we can build an intelligent analysis layer that queries PostgreSQL and provides actionable insights.

**New file: `src/analytics/claude_analyst.py`**
```python
import anthropic
from typing import Dict, List

class ClaudeAnalyst:
    """
    AI-powered trading analysis using Claude API.
    Queries PostgreSQL for data, generates insights for HFT trader.
    """

    def __init__(self, api_key: str, db_connection):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.db = db_connection

    async def analyze_trading_patterns(self, timeframe: str = "24h") -> str:
        """Analyze recent trading patterns across CEX + DEX"""
        # 1. Query trade data from PostgreSQL
        trades = await self._fetch_trades(timeframe)

        # 2. Build context for Claude
        context = self._build_trade_context(trades)

        # 3. Get Claude's analysis
        response = self.client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=1024,
            messages=[{
                "role": "user",
                "content": f"""Analyze this ALKIMI trading data and provide actionable insights:

{context}

Focus on:
1. Volume patterns across venues (CEX vs DEX)
2. Price discrepancies / arbitrage opportunities
3. Unusual activity or whale movements
4. Recommended actions for market making
5. Risk alerts

Be concise and actionable."""
            }]
        )
        return response.content[0].text

    async def detect_arbitrage_opportunities(self) -> List[Dict]:
        """Real-time arbitrage detection between CEX and DEX"""
        # Compare prices across venues
        # Flag opportunities > threshold
        pass

    async def generate_daily_briefing(self) -> str:
        """Morning briefing for HFT trader"""
        # Overnight activity summary
        # Key metrics and trends
        # Recommended focus areas
        pass

    async def analyze_whale_activity(self, threshold_usd: float = 10000) -> str:
        """Detect and analyze large trades"""
        pass
```

### 6.2 Automated Insights in Slack

**Update Slack reporting to include AI analysis:**
```python
async def send_report_with_insights(self, report: Dict):
    """
    📊 ALKIMI TRADING REPORT

    [Standard metrics...]

    🤖 AI ANALYSIS
    ─────────────────
    {claude_insights}

    ⚠️ ALERTS
    • [Arbitrage opportunity detected: MEXC vs Cetus, 2.3% spread]
    • [Whale alert: 500K ALKIMI sold on Bluefin]
    """
```

### 6.3 PostgreSQL Schema for AI Context

```sql
-- Store AI-generated insights for historical reference
CREATE TABLE ai_insights (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    insight_type TEXT NOT NULL,  -- 'pattern', 'arbitrage', 'whale', 'briefing'
    content TEXT NOT NULL,
    confidence FLOAT,
    actioned BOOLEAN DEFAULT FALSE,
    metadata JSONB
);

-- Materialized views for fast AI queries
CREATE MATERIALIZED VIEW hourly_venue_summary AS
SELECT
    date_trunc('hour', timestamp) as hour,
    exchange,
    dex_name,
    COUNT(*) as trade_count,
    SUM(amount * price) as volume_usd,
    AVG(price) as avg_price,
    MAX(price) as high_price,
    MIN(price) as low_price
FROM trades
GROUP BY 1, 2, 3;

-- Refresh every 5 minutes
CREATE INDEX idx_hourly_summary ON hourly_venue_summary (hour DESC);
```

### 6.4 Configuration

**Add to .env:**
```
# Claude API (Railway provides this)
ANTHROPIC_API_KEY=sk-ant-...
CLAUDE_MODEL=claude-sonnet-4-20250514
CLAUDE_ANALYSIS_ENABLED=true
CLAUDE_ANALYSIS_INTERVAL=3600  # Run analysis every hour
```

**Add to settings.py:**
```python
@property
def claude_config(self) -> Dict:
    return {
        'api_key': os.getenv('ANTHROPIC_API_KEY', ''),
        'model': os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514'),
        'enabled': os.getenv('CLAUDE_ANALYSIS_ENABLED', 'false').lower() == 'true',
        'interval': int(os.getenv('CLAUDE_ANALYSIS_INTERVAL', '3600'))
    }
```

### 6.5 Analysis Types

| Analysis | Frequency | Use Case |
|----------|-----------|----------|
| **Pattern Detection** | Hourly | Identify trends, volume shifts |
| **Arbitrage Scanner** | Every 5 min | CEX/DEX price gaps > 1% |
| **Whale Alerts** | Real-time | Trades > $10K flagged |
| **Daily Briefing** | 8am daily | Morning summary for trader |
| **Risk Assessment** | On-demand | Concentration, exposure analysis |

### 6.6 Trader Interaction: Conversational AI Interface

**The HFT trader interacts with the system via natural language queries to Claude.**

#### Option A: Slack Bot (Recommended for Day 1)
```
Trader in Slack: @alkimi-bot What was our best performing venue yesterday?

Bot Response:
📊 Yesterday's Venue Performance (Nov 28)

Best: Gate.io
• Volume: $47,230 (892 trades)
• Avg sell price: $0.0434 (highest across venues)
• Net P&L: +$1,247

Comparison:
1. Gate.io: $0.0434 avg (+12% vs MEXC)
2. Cetus DEX: $0.0412 avg
3. KuCoin: $0.0381 avg
4. MEXC: $0.0387 avg (highest volume but worst price)

💡 Recommendation: Shift more volume to Gate.io for better execution
```

#### Implementation: Slack Bot with Claude
```python
# src/bot/slack_bot.py
from slack_bolt.async_app import AsyncApp

app = AsyncApp(token=os.environ["SLACK_BOT_TOKEN"])

@app.message(re.compile(r"@alkimi-bot (.+)"))
async def handle_query(message, say, context):
    query = context["matches"][0]

    # Get relevant data from PostgreSQL
    data_context = await build_data_context(query)

    # Ask Claude to answer
    response = await claude_analyst.answer_query(
        query=query,
        data_context=data_context
    )

    await say(response)
```

#### Sample Queries the Trader Can Ask:
```
"What's the current spread between MEXC and Cetus?"
"Show me all trades over $5K in the last hour"
"Why did volume spike on Bluefin at 2pm?"
"Compare my execution quality this week vs last week"
"What arbitrage opportunities exist right now?"
"Summarize overnight activity"
"Which wallet has the most exposure?"
"What's our total unrealized P&L?"
```

#### Option B: Web Chat Interface (Post-Monday Enhancement)
```python
# src/api/chat_endpoint.py
from fastapi import FastAPI, WebSocket

@app.websocket("/chat")
async def chat_endpoint(websocket: WebSocket):
    await websocket.accept()
    while True:
        query = await websocket.receive_text()

        # Stream Claude's response
        async for chunk in claude_analyst.stream_answer(query):
            await websocket.send_text(chunk)
```

#### Configuration for Slack Bot
```
# Add to .env
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_SIGNING_SECRET=...
```

```
# Add to requirements.txt
slack-bolt>=1.18.0
```

### 6.7 Sample Claude Prompts

**Arbitrage Detection:**
```
Given current prices:
- MEXC: $0.0334
- Gate.io: $0.0434
- Cetus DEX: $0.0385
- Bluefin DEX: $0.0372

Identify profitable arbitrage routes considering:
- Trading fees (0.1% CEX, 0.3% DEX)
- Gas costs (~$0.01 on Sui)
- Slippage estimates
- Position size limits
```

**Pattern Analysis:**
```
Trading data (last 24h):
{trade_summary}

Identify:
1. Unusual volume spikes and likely causes
2. Price momentum direction
3. Venue preference shifts
4. Potential market manipulation signals
```

---

## Updated File Changes Summary

### New Files (Updated)
```
src/exchanges/sui_monitor.py      # Sui blockchain token monitoring
src/exchanges/ccxt_base.py        # Shared CCXT functionality
src/analytics/claude_analyst.py   # NEW: AI-powered analysis
config/business_rules.py          # OTC and special transactions
scripts/test_sui_connection.py    # Sui connectivity test
scripts/test_dex_trades.py        # DEX trade validation
scripts/test_claude_analysis.py   # NEW: Test AI insights
Dockerfile                        # Container configuration
docker-compose.yml                # Local development
railway.toml                      # Railway deployment config
migrations/001_initial.sql        # NEW: PostgreSQL schema
migrations/002_ai_insights.sql    # NEW: AI tables
```

### Dependencies Update
```
# Add to requirements.txt
anthropic>=0.39.0     # Claude API client
psycopg2-binary>=2.9.0  # PostgreSQL driver
sqlalchemy>=2.0.0     # ORM for PostgreSQL
```

---

---

## Phase 7: Repository Organization & Documentation (2-3 hours)

### 7.1 Directory Structure Reorganization

**Current structure is flat - reorganize for clarity:**

```
cex-reporter/
├── README.md                    # Updated comprehensive guide
├── CHANGELOG.md                 # NEW: Track all changes
├── CONTRIBUTING.md              # NEW: For HFT trader/team
├── .env.example                 # Sanitized template
├── Dockerfile
├── docker-compose.yml
├── railway.toml
├── requirements.txt
│
├── config/
│   ├── settings.py
│   ├── business_rules.py       # NEW: OTC transactions, special cases
│   └── logging_config.py       # NEW: Extracted from utils
│
├── src/
│   ├── __init__.py
│   ├── exchanges/
│   │   ├── __init__.py
│   │   ├── base.py             # ExchangeInterface
│   │   ├── ccxt_base.py        # NEW: Shared CCXT logic
│   │   ├── mexc.py
│   │   ├── kraken.py
│   │   ├── kucoin.py
│   │   ├── gateio.py
│   │   ├── cetus.py            # Existing (positions)
│   │   └── sui_monitor.py      # NEW: Token contract monitoring
│   │
│   ├── analytics/
│   │   ├── __init__.py
│   │   ├── simple_tracker.py
│   │   ├── position_tracker.py
│   │   ├── pnl.py
│   │   ├── portfolio.py
│   │   └── claude_analyst.py   # NEW: AI analysis
│   │
│   ├── data/
│   │   ├── __init__.py
│   │   ├── trade_cache.py      # SQLite (legacy)
│   │   ├── postgres_client.py  # NEW: PostgreSQL
│   │   ├── daily_snapshot.py
│   │   ├── deposits_loader.py
│   │   └── coingecko_client.py
│   │
│   ├── reporting/
│   │   ├── __init__.py
│   │   ├── slack.py
│   │   └── simple_formatter.py
│   │
│   ├── bot/                    # NEW: Slack bot
│   │   ├── __init__.py
│   │   └── slack_bot.py
│   │
│   └── utils/
│       ├── __init__.py
│       ├── cache.py
│       ├── logging.py
│       └── trade_deduplication.py
│
├── scripts/
│   ├── check_balances.py
│   ├── recent_activity.py
│   ├── price_impact.py
│   ├── cache_stats.py
│   ├── backtest_*.py
│   ├── test_sui_connection.py  # NEW
│   ├── test_dex_trades.py      # NEW
│   └── test_claude_analysis.py # NEW
│
├── migrations/                  # NEW: Database migrations
│   ├── 001_initial_schema.sql
│   ├── 002_dex_support.sql
│   └── 003_ai_insights.sql
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── test_exchanges/
│   ├── test_analytics/
│   ├── test_sui_monitor.py     # NEW
│   └── test_data_accuracy.py   # NEW: Critical validation
│
├── docs/
│   ├── SUI_DEX_INTEGRATION_PLAN.md
│   ├── SUI_DEX_QUICK_START.md
│   ├── API_REFERENCE.md        # NEW
│   ├── DEPLOYMENT.md           # NEW: Railway guide
│   └── TRADER_GUIDE.md         # NEW: For HFT trader
│
└── data/                        # Git-ignored runtime data
    ├── trade_cache.db
    ├── snapshots/
    └── logs/
```

### 7.2 Comprehensive README Update

**New README.md structure:**

```markdown
# ALKIMI CEX + DEX Reporter

> Complete trading visibility across centralized and decentralized exchanges
> with AI-powered analysis for high-frequency trading operations.

## Features

### Trading Data
- **4 CEX Exchanges**: MEXC, Kraken, KuCoin, Gate.io (12 accounts)
- **All Sui DEXs**: Cetus, Bluefin, Turbos + any new listings
- **Real-time Tracking**: Hourly reports, on-demand queries

### AI Analysis (Claude-powered)
- Natural language queries via Slack bot
- Automated pattern detection
- Arbitrage opportunity alerts
- Whale movement tracking
- Daily briefings

### Treasury Management
- Realized P&L tracking (FIFO)
- Unrealized gains calculation
- Multi-wallet monitoring
- Historical snapshots

## Quick Start

### Local Development
\`\`\`bash
git clone <repo>
cp .env.example .env
# Edit .env with your API keys
docker-compose up
\`\`\`

### Railway Deployment
\`\`\`bash
railway login
railway up
# Configure environment variables in Railway dashboard
\`\`\`

## Architecture

[Diagram: CEX APIs + Sui RPC → PostgreSQL → Claude Analysis → Slack]

## For Traders

See [TRADER_GUIDE.md](docs/TRADER_GUIDE.md) for:
- How to query the bot
- Available commands
- Setting up alerts
- Understanding reports

## API Reference

See [API_REFERENCE.md](docs/API_REFERENCE.md)

## Configuration

| Variable | Required | Description |
|----------|----------|-------------|
| MEXC_*_API_KEY | Yes | MEXC API credentials |
| ... | ... | ... |
| ANTHROPIC_API_KEY | Yes | Claude API for analysis |
| SUI_RPC_URL | Yes | Sui blockchain RPC |
| ALKIMI_TOKEN_CONTRACT | Yes | Token address on Sui |

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md)

## Changelog

See [CHANGELOG.md](CHANGELOG.md)
```

### 7.3 CHANGELOG.md

```markdown
# Changelog

## [2.0.0] - 2025-11-30

### Added
- **Sui DEX Integration**: Monitor all ALKIMI trades on Sui blockchain
- **Claude AI Analysis**: Natural language queries, pattern detection
- **Slack Bot**: Interactive `@alkimi-bot` for trader queries
- **PostgreSQL Support**: Persistent storage for Railway deployment
- **Treasury Tracking**: Realized + unrealized P&L
- **Docker/Railway**: Production deployment configuration

### Changed
- Reorganized repository structure
- Extracted shared CCXT logic to base class
- Environment-based configuration for all paths
- Parallel exchange initialization (9x faster startup)

### Fixed
- Removed hardcoded paths for deployment compatibility
- Removed credentials from .env.example
- Fixed sequential initialization bottleneck

### Security
- Sanitized all example configuration files
- Added input validation for API responses

## [1.0.0] - 2025-11-01
- Initial CEX reporter with 4 exchanges
- Slack reporting
- SQLite trade cache
```

---

## Phase 8: Data Accuracy Testing & Validation (3-4 hours)

### 8.1 Testing Strategy

**Critical: Verify data accuracy before HFT trader relies on it.**

```
Test Categories:
1. CEX Data Accuracy     - Compare against exchange UI
2. DEX Data Accuracy     - Compare against block explorer
3. P&L Calculations      - Manual verification of FIFO
4. Treasury Balances     - Match on-chain values
5. AI Response Quality   - Fact-check Claude outputs
```

### 8.2 CEX Data Validation Tests

**Create `tests/test_data_accuracy.py`:**

```python
import pytest
from datetime import datetime, timedelta

class TestCEXDataAccuracy:
    """Validate CEX trade data against known reference points"""

    @pytest.mark.asyncio
    async def test_mexc_trade_count_matches(self):
        """Compare trade count with MEXC UI export"""
        # Export last 24h trades from MEXC UI
        # Compare count with our database
        db_count = await get_trade_count('mexc', hours=24)
        expected_count = 145  # From manual MEXC export
        assert abs(db_count - expected_count) <= 2  # Allow small variance

    @pytest.mark.asyncio
    async def test_balance_accuracy(self):
        """Verify balances match exchange APIs"""
        for exchange in ['mexc', 'kraken', 'kucoin', 'gateio']:
            our_balance = await get_our_balance(exchange, 'ALKIMI')
            api_balance = await fetch_direct_from_api(exchange, 'ALKIMI')
            assert abs(our_balance - api_balance) < 1.0  # Within 1 token

    @pytest.mark.asyncio
    async def test_sell_proceeds_calculation(self):
        """Verify sell proceeds match manual calculation"""
        # Known reference: Oct 7 - Nov 22 = $417,060.65
        proceeds = await calculate_sell_proceeds(
            start='2025-10-07',
            end='2025-11-22'
        )
        expected = 417060.65
        assert abs(proceeds - expected) < 100  # Within $100

    @pytest.mark.asyncio
    async def test_trade_deduplication(self):
        """Ensure no duplicate trades in database"""
        duplicates = await find_duplicate_trades()
        assert len(duplicates) == 0, f"Found {len(duplicates)} duplicates"
```

### 8.3 DEX Data Validation Tests

```python
class TestDEXDataAccuracy:
    """Validate Sui DEX data against blockchain"""

    @pytest.mark.asyncio
    async def test_sui_wallet_balance(self):
        """Compare wallet balance with Sui explorer"""
        our_balance = await sui_monitor.get_wallet_balance(TREASURY_WALLET)
        explorer_balance = await fetch_from_suiscan(TREASURY_WALLET, 'ALKIMI')
        assert our_balance == explorer_balance

    @pytest.mark.asyncio
    async def test_dex_trade_detection(self):
        """Verify we detect trades that appear on block explorer"""
        # Use known transaction hash
        known_tx = "0x123..."  # Real swap tx from Suiscan
        trades = await sui_monitor.get_all_trades(since=datetime.now() - timedelta(days=1))
        tx_hashes = [t.trade_id for t in trades]
        assert known_tx in tx_hashes, "Known DEX trade not detected"

    @pytest.mark.asyncio
    async def test_dex_identification(self):
        """Verify correct DEX attribution"""
        # Manually verify a Cetus trade is labeled as Cetus
        cetus_trade = await get_trade_by_tx("0x456...")
        assert cetus_trade.metadata['dex'] == 'cetus'

    @pytest.mark.asyncio
    async def test_price_calculation(self):
        """Verify swap price matches expected"""
        trade = await get_trade_by_tx("0x789...")
        # Manual: 10000 ALKIMI swapped for 340 USDC = $0.034/ALKIMI
        assert abs(trade.price - 0.034) < 0.001
```

### 8.4 P&L Validation Tests

```python
class TestPnLAccuracy:
    """Validate P&L calculations"""

    @pytest.mark.asyncio
    async def test_fifo_calculation(self):
        """Verify FIFO cost basis is correct"""
        # Known scenario:
        # Buy 1000 @ $0.04, Buy 500 @ $0.05, Sell 800
        # FIFO: Sell 800 from first lot @ $0.04 cost basis
        result = calculate_fifo_pnl([
            Trade(side='buy', amount=1000, price=0.04),
            Trade(side='buy', amount=500, price=0.05),
            Trade(side='sell', amount=800, price=0.045),
        ])
        expected_cost_basis = 800 * 0.04  # $32
        expected_proceeds = 800 * 0.045   # $36
        expected_pnl = 4.0                # $4 profit
        assert abs(result.realized_pnl - expected_pnl) < 0.01

    @pytest.mark.asyncio
    async def test_unrealized_pnl(self):
        """Verify unrealized P&L calculation"""
        holdings = 6_388_000  # Current ALKIMI balance
        avg_cost = 0.104622  # From deposits
        current_price = 0.027
        expected_unrealized = holdings * (current_price - avg_cost)
        # Expected: Large unrealized loss due to price decline
        actual = await calculate_unrealized_pnl()
        assert abs(actual - expected_unrealized) < 1000
```

### 8.5 AI Response Validation

```python
class TestAIAccuracy:
    """Validate Claude responses contain accurate data"""

    @pytest.mark.asyncio
    async def test_ai_volume_accuracy(self):
        """Verify AI-reported volumes match database"""
        response = await claude_analyst.answer_query(
            "What was total volume yesterday?"
        )
        # Extract number from response
        ai_volume = extract_volume_from_response(response)
        db_volume = await get_daily_volume(yesterday)
        # Allow 5% variance for rounding
        assert abs(ai_volume - db_volume) / db_volume < 0.05

    @pytest.mark.asyncio
    async def test_ai_no_hallucination(self):
        """Ensure AI doesn't invent data"""
        response = await claude_analyst.answer_query(
            "Show me trades on FakeExchange"
        )
        assert "no data" in response.lower() or "not found" in response.lower()
```

### 8.6 Validation Script for Manual Review

**Create `scripts/validate_data.py`:**

```python
"""
Manual data validation script.
Run before going live to verify accuracy.
"""

async def main():
    print("=" * 60)
    print("ALKIMI REPORTER DATA VALIDATION")
    print("=" * 60)

    # 1. CEX Balance Check
    print("\n📊 CEX BALANCE VERIFICATION")
    for exchange in EXCHANGES:
        our_bal = await get_balance(exchange)
        print(f"  {exchange}: {our_bal:,.2f} ALKIMI")
    print("  → Manually verify against exchange UIs")

    # 2. Recent Trade Check
    print("\n📈 RECENT TRADE VERIFICATION (last 24h)")
    trades = await get_recent_trades(hours=24)
    print(f"  Total trades: {len(trades)}")
    print(f"  Buy volume: ${sum(t.amount*t.price for t in trades if t.side=='buy'):,.2f}")
    print(f"  Sell volume: ${sum(t.amount*t.price for t in trades if t.side=='sell'):,.2f}")
    print("  → Compare with exchange trade history")

    # 3. DEX Data Check
    print("\n🌊 DEX DATA VERIFICATION")
    dex_trades = await sui_monitor.get_all_trades(since=yesterday)
    print(f"  DEX trades found: {len(dex_trades)}")
    by_dex = group_by_dex(dex_trades)
    for dex, count in by_dex.items():
        print(f"    {dex}: {count} trades")
    print("  → Verify sample transactions on Suiscan")

    # 4. Treasury Value Check
    print("\n💰 TREASURY VALUE VERIFICATION")
    treasury = await calculate_treasury_value()
    print(f"  Total ALKIMI: {treasury.total_alkimi:,.0f}")
    print(f"  Current price: ${treasury.price:.4f}")
    print(f"  Total value: ${treasury.total_value:,.2f}")
    print(f"  Unrealized P&L: ${treasury.unrealized_pnl:,.2f}")

    # 5. Historical Accuracy
    print("\n📅 HISTORICAL REFERENCE CHECK")
    print("  Known: Oct 7 - Nov 22 sell proceeds = $417,060.65")
    calculated = await calculate_sell_proceeds('2025-10-07', '2025-11-22')
    print(f"  Calculated: ${calculated:,.2f}")
    diff = abs(calculated - 417060.65)
    print(f"  Difference: ${diff:,.2f} {'✅' if diff < 100 else '❌'}")

    print("\n" + "=" * 60)
    print("Review complete. Address any ❌ items before going live.")

if __name__ == "__main__":
    asyncio.run(main())
```

### 8.7 Continuous Validation

**Add to hourly report cycle:**

```python
async def generate_report_with_validation(self):
    report = await self.get_report()

    # Quick sanity checks
    validations = []

    # Check balances are positive
    for asset, balance in report['total_balances'].items():
        if balance < 0:
            validations.append(f"⚠️ Negative balance: {asset}")

    # Check prices are reasonable
    if report.get('alkimi_price', 0) > 1.0 or report.get('alkimi_price', 0) < 0.001:
        validations.append(f"⚠️ Unusual price: ${report['alkimi_price']}")

    # Check for data freshness
    latest_trade = report.get('latest_trade_time')
    if latest_trade and (datetime.now() - latest_trade).hours > 24:
        validations.append("⚠️ No trades in 24h - check connections")

    if validations:
        report['validation_warnings'] = validations

    return report
```

---

## Updated Implementation Order (2 Days)

### Day 1 (Nov 29) - Foundation + Database
1. **Morning:** Critical fixes (security, paths, env vars)
2. **Afternoon:** PostgreSQL setup + Docker configuration
3. **Evening:** Deploy to Railway, run validation script

### Day 2 (Nov 30) - DEX + AI + Documentation
1. **Morning:** Sui monitor implementation + DEX validation
2. **Afternoon:** Claude analyst + Slack bot + P&L validation
3. **Evening:** README update, CHANGELOG, final testing

---

## Future Enhancements (Post-Monday)

1. **Real-time WebSocket feeds** - Sub-second CEX data
2. **Bot signal API** - REST endpoints for trading signals
3. **Strategy backtesting** - Framework for testing new strategies
4. **Advanced AI features:**
   - Sentiment analysis from on-chain data
   - Predictive volume modeling
   - Automated strategy suggestions
   - Natural language trade queries ("What was our best performing venue last week?")
