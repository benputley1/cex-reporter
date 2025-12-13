# ALKIMI CEX + DEX Reporter

> Complete trading visibility across centralized and decentralized exchanges with AI-powered analysis for high-frequency trading operations.

## Features

### Trading Data
- **4 CEX Exchanges**: MEXC, Kraken, KuCoin, Gate.io (12 accounts)
- **All Sui DEXs**: Cetus, Bluefin, Turbos + any new listings via token contract monitoring
- **Real-time Tracking**: Hourly reports, on-demand queries
- **Trade Caching**: Async SQLite with connection pooling
- **Parallel Queries**: 4x faster data fetching with `asyncio.gather`
- **Duplicate Prevention**: Unique constraints and deduplication

### AI Analysis (Claude-powered)
- Natural language queries via Slack bot (`@alkimi-bot`)
- **60-second timeout** with graceful error handling
- **20-message context window** with conversation summarization
- Automated pattern detection
- Arbitrage opportunity alerts
- Whale movement tracking
- Daily briefings for HFT traders

### Treasury Management
- Realized P&L tracking (FIFO, LIFO, AVG accounting)
- Unrealized gains calculation
- Multi-wallet monitoring
- Historical daily snapshots
- **Transfer tracking** (deposits/withdrawals separate from trades)
- **OTC transaction management**

### Alerts & Monitoring
- **Whale Alerts**: Automatic alerts for trades >$10K
- **Price Movement Alerts**: Alerts for >5% price changes in 1 hour
- **Failure Alerts**: System health alerts with recovery notifications
- **Health Monitoring**: Component status, latency tracking, circuit breakers

### Reporting
- Automated Slack reports (configurable interval)
- Exchange breakdown with volume metrics
- Net position tracking
- **Color-coded values** (green/red for positive/negative)
- **Sparkline trends** for visual analysis
- Alert system for significant changes (>5%)

## Quick Start

### Local Development (Python)
```bash
# Clone and setup
git clone <repo>
cd cex-reporter
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your API keys

# Run once
python main.py --mode once

# Run continuous (reports every 4 hours)
python main.py --mode continuous
```

### Docker Deployment
```bash
# Build and run
docker build -t alkimi-cex-reporter .
docker run -d --env-file .env alkimi-cex-reporter

# Or with docker-compose
docker-compose up -d
```

### Railway Deployment
```bash
railway login
railway up
# Configure environment variables in Railway dashboard
```

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CEX + DEX Reporter                        │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────────┐  │
│  │ CEX Clients  │  │ Sui Monitor  │  │ Claude AI Analyst    │  │
│  │ (CCXT)       │  │ (RPC)        │  │ (Anthropic API)      │  │
│  │ - MEXC       │  │ - Token txns │  │ - Pattern detection  │  │
│  │ - Kraken     │  │ - DEX swaps  │  │ - Arbitrage alerts   │  │
│  │ - KuCoin     │  │ - Balances   │  │ - NL queries         │  │
│  │ - Gate.io    │  │              │  │                      │  │
│  └──────┬───────┘  └──────┬───────┘  └──────────┬───────────┘  │
│         │                 │                      │              │
│         └────────┬────────┴──────────────────────┘              │
│                  │                                               │
│         ┌────────▼────────┐                                     │
│         │  Trade Cache    │                                     │
│         │  (SQLite/PG)    │                                     │
│         └────────┬────────┘                                     │
│                  │                                               │
│    ┌─────────────┼─────────────┐                                │
│    │             │             │                                │
│    ▼             ▼             ▼                                │
│ ┌──────┐   ┌──────────┐   ┌──────────┐                         │
│ │Slack │   │ Slack    │   │ Reports  │                         │
│ │Report│   │ Bot      │   │ CSV/JSON │                         │
│ └──────┘   └──────────┘   └──────────┘                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Directory Structure

```
cex-reporter/
├── README.md                    # This file
├── CHANGELOG.md                 # Version history
├── .env.example                 # Configuration template
├── Dockerfile                   # Container build
├── docker-compose.yml           # Local development
├── railway.toml                 # Railway deployment
├── requirements.txt             # Python dependencies
│
├── config/
│   └── settings.py              # Configuration management
│
├── src/
│   ├── exchanges/               # Exchange clients
│   │   ├── base.py              # CCXTExchangeBase with retry & circuit breaker
│   │   ├── mexc.py              # MEXC client
│   │   ├── kraken.py            # Kraken client
│   │   ├── kucoin.py            # KuCoin client
│   │   ├── gateio.py            # Gate.io client
│   │   ├── cetus.py             # Cetus DEX (positions)
│   │   └── sui_monitor.py       # Sui token contract monitor
│   │
│   ├── analytics/               # Analysis engines
│   │   ├── simple_tracker.py    # Main reporting engine (parallel queries)
│   │   ├── position_tracker.py  # Position & P&L tracking
│   │   ├── pnl.py               # FIFO P&L calculations
│   │   ├── portfolio.py         # Portfolio aggregation
│   │   └── claude_analyst.py    # AI-powered analysis
│   │
│   ├── data/                    # Data management
│   │   ├── trade_cache.py       # Async SQLite with deduplication
│   │   ├── daily_snapshot.py    # Daily balance snapshots
│   │   ├── deposits_loader.py   # Initial deposit tracking
│   │   └── coingecko_client.py  # Price fallback
│   │
│   ├── reporting/               # Output formatting
│   │   ├── slack.py             # Slack webhook client (legacy)
│   │   └── simple_formatter.py  # Report formatting
│   │
│   ├── bot/                     # Slack bot interface
│   │   ├── slack_bot.py         # AlkimiBot with alerts & commands
│   │   ├── conversational_agent.py  # LLM agent with context memory
│   │   ├── formatters.py        # Rich Slack formatting
│   │   ├── error_classifier.py  # Error categorization
│   │   └── data_provider.py     # Repository facade
│   │
│   ├── repositories/            # Data access layer (NEW)
│   │   ├── trade_repository.py
│   │   ├── balance_repository.py
│   │   ├── snapshot_repository.py
│   │   ├── query_repository.py
│   │   ├── thread_repository.py
│   │   ├── price_repository.py
│   │   └── otc_repository.py
│   │
│   ├── monitoring/              # Health & alerts (NEW)
│   │   └── health.py            # HealthChecker with component status
│   │
│   └── utils/                   # Shared utilities
│       ├── logging.py           # Structured logging
│       ├── cache.py             # Response caching
│       ├── retry.py             # Exponential backoff decorator (NEW)
│       └── circuit_breaker.py   # Circuit breaker pattern (NEW)
│
├── scripts/                     # Utility scripts
│   ├── check_balances.py        # Balance checker
│   ├── recent_activity.py       # Activity summary
│   ├── price_impact.py          # Price impact analysis
│   └── cache_stats.py           # Cache statistics
│
├── tests/                       # Test suite
│   └── test_pnl_config.py       # P&L calculation tests (42 tests)
│
├── docs/                        # Documentation
│   ├── CIRCUIT_BREAKER.md       # Circuit breaker guide
│   └── SUI_DEX_INTEGRATION_PLAN.md
│
└── data/                        # Runtime data (git-ignored)
    ├── trade_cache.db
    └── snapshots/
```

## Configuration

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| **CEX API Keys** | | |
| `MEXC_MM1_API_KEY` | Yes | MEXC Market Maker 1 API key |
| `MEXC_MM1_API_SECRET` | Yes | MEXC Market Maker 1 secret |
| `GATEIO_*_API_KEY` | Yes | Gate.io API credentials |
| `KUCOIN_*_API_KEY` | Yes | KuCoin API credentials |
| `KUCOIN_*_API_PASSPHRASE` | Yes | KuCoin API passphrase |
| `KRAKEN_API_KEY` | Yes | Kraken API credentials |
| **Sui DEX** | | |
| `SUI_RPC_URL` | No | Sui RPC endpoint |
| `ALKIMI_TOKEN_CONTRACT` | No | ALKIMI token address on Sui |
| `SUI_WALLET_TREASURY` | No | Treasury wallet address |
| **Claude AI** | | |
| `ANTHROPIC_API_KEY` | No | Claude API key |
| `CLAUDE_MODEL` | No | Model (default: claude-sonnet-4-20250514) |
| `CLAUDE_ANALYSIS_ENABLED` | No | Enable AI analysis |
| `AGENT_TIMEOUT_SECONDS` | No | LLM timeout (default: 60) |
| `MAX_CONTEXT_MESSAGES` | No | Conversation memory (default: 20) |
| **Slack** | | |
| `SLACK_WEBHOOK_URL` | Yes | Slack webhook for reports |
| `SLACK_BOT_TOKEN` | No | Bot token for @alkimi-bot |
| `SLACK_APP_TOKEN` | No | App token for socket mode |
| **Alerts** | | |
| `WHALE_ALERT_THRESHOLD_USD` | No | Whale alert threshold (default: 10000) |
| `WHALE_ALERT_CHANNEL` | No | Whale alert channel (default: #trading-alerts) |
| `PRICE_ALERT_THRESHOLD_PERCENT` | No | Price alert threshold (default: 5.0) |
| `PRICE_ALERT_CHANNEL` | No | Price alert channel (default: #trading-alerts) |
| `FAILURE_ALERT_CHANNEL` | No | System alert channel (default: #ops-alerts) |
| `FAILURE_ALERT_THRESHOLD` | No | Consecutive failures before alert (default: 3) |
| **Application** | | |
| `MOCK_MODE` | No | Use mock data (default: false) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |
| `REPORT_INTERVAL` | No | Report interval in seconds |
| `EXCHANGE_TIMEOUT_SECONDS` | No | Exchange API timeout (default: 30) |
| `THREAD_CLEANUP_INTERVAL_HOURS` | No | Thread cleanup interval (default: 6) |
| `THREAD_RETENTION_DAYS` | No | Thread retention period (default: 7) |

## Utility Scripts

### Check Balances
```bash
python scripts/check_balances.py         # Console output
python scripts/check_balances.py --slack # Post to Slack
```

### Recent Activity
```bash
python scripts/recent_activity.py --hours 24
python scripts/recent_activity.py --days 7 --slack
```

### Price Impact Analysis
```bash
python scripts/price_impact.py --days 7
```

### Trade Cache Stats
```bash
python scripts/cache_stats.py
```

## Slack Bot Usage

Once configured with `SLACK_BOT_TOKEN`, interact with the bot:

### Natural Language Queries
```
@alkimi-bot What was our best performing venue yesterday?
@alkimi-bot Show me the spread between MEXC and Gate.io
@alkimi-bot Summarize overnight activity
@alkimi-bot What arbitrage opportunities exist?
@alkimi-bot What's our total unrealized P&L?
```

### Quick Commands
| Command | Alias | Description |
|---------|-------|-------------|
| `/alkimi balance` | `/alkimi bal` | Quick balance summary |
| `/alkimi price` | `/alkimi p` | Current ALKIMI price |
| `/alkimi today` | - | Today's P&L |
| `/alkimi week` | - | Last 7 days P&L |
| `/alkimi month` | - | Last 30 days P&L |
| `/alkimi health` | - | System health status |
| `/alkimi help` | - | Show all commands |

### Slash Commands
```
/alkimi pnl              # Full P&L report
/alkimi sql <query>      # Execute SQL query
/alkimi run <function>   # Run saved function
/alkimi functions        # List saved functions
/alkimi config           # Show P&L config
/alkimi otc list         # List OTC transactions
```

### Automatic Alerts
The bot automatically sends alerts to configured channels:
- **Whale Alerts**: Trades >$10K → `#trading-alerts`
- **Price Alerts**: >5% price change → `#trading-alerts`
- **System Alerts**: Component failures → `#ops-alerts`

## P&L Calculation

### FIFO Accounting
- Tracks all purchases with timestamps
- Matches sales to earliest purchases first
- Includes trading fees in cost basis

### Realized vs Unrealized
- **Realized**: Profit/loss from completed sales
- **Unrealized**: Current holdings × (market price - avg cost)

### Cost Basis
Loaded from `deposits & withdrawals.xlsx` for initial ALKIMI deposits.

## Development

### Running Tests
```bash
pytest                    # All tests
pytest --cov=src tests/   # With coverage
pytest -v                 # Verbose
```

### Code Quality
```bash
black src/ tests/         # Format
flake8 src/ tests/        # Lint
mypy src/                 # Type check
```

## Troubleshooting

### API Connection Issues
- Verify API keys in `.env`
- Check API key permissions (read-only is sufficient)
- Ensure IP whitelist if required by exchange

### Kraken Nonce Errors
- Normal for concurrent API calls
- System handles gracefully with retries

### Slack Messages Not Sending
- Verify webhook URL is correct
- Check Slack app permissions
- Review logs in `logs/` directory

## Security

- Use read-only API keys only
- Never commit `.env` file
- Rotate API keys regularly
- `.env.example` contains only placeholder values

## Changelog

### v3.0.0 (2025-12-13)
**Major infrastructure and AlkimiBot improvements**

#### Core Infrastructure
- **Async SQLite**: Migrated to `aiosqlite` with connection pooling
- **Parallel Queries**: 4x faster data fetching with `asyncio.gather`
- **Duplicate Prevention**: Unique index on trades, `INSERT OR IGNORE`
- **API Retry Logic**: Exponential backoff decorator for all exchange calls
- **Circuit Breakers**: Auto-disable failing exchanges with recovery detection
- **Transfer Tracking**: Separate deposits/withdrawals from trades
- **Repository Pattern**: DataProvider decomposed into 7 focused repositories
- **CCXT Base Class**: Centralized logging and error handling

#### AlkimiBot Enhancements
- **Agent Timeout**: 60-second timeout with graceful error messages
- **Error Classification**: User-friendly errors with recovery suggestions
- **Conversation Memory**: 20-message context window with summarization
- **Quick Commands**: `/alkimi bal`, `/alkimi p`, `/alkimi today/week/month`
- **Health Command**: `/alkimi health` shows system status
- **Response Formatting**: Color-coded values, sparklines, rich Slack blocks
- **Thread Cleanup**: Automatic background cleanup every 6 hours

#### Alerts & Monitoring
- **Whale Alerts**: Automatic alerts for trades >$10K
- **Price Alerts**: Alerts for >5% price changes in 1 hour
- **Failure Alerts**: System health alerts with recovery notifications
- **Health Monitoring**: Component status, latency tracking

#### Testing
- **P&L Tests**: 42 unit tests with 77% coverage
- All cost basis methods tested (FIFO, LIFO, AVG)

### v2.0.0 (2025-11-30)
- Added Sui DEX integration via token contract monitoring
- Added Claude AI analysis layer
- Added Slack bot conversational interface
- Added Docker and Railway deployment configs
- Fixed hardcoded paths for deployment compatibility
- Removed credentials from .env.example

### v1.0.0 (2025-11-01)
- Initial CEX reporter with 4 exchanges
- Slack reporting
- SQLite trade cache
- FIFO P&L tracking

## License

MIT License - See LICENSE file for details.
