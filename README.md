# ALKIMI CEX + DEX Reporter

> Complete trading visibility across centralized and decentralized exchanges with AI-powered analysis for high-frequency trading operations.

## Features

### Trading Data
- **4 CEX Exchanges**: MEXC, Kraken, KuCoin, Gate.io (12 accounts)
- **All Sui DEXs**: Cetus, Bluefin, Turbos + any new listings via token contract monitoring
- **Real-time Tracking**: Hourly reports, on-demand queries
- **Trade Caching**: SQLite persistence beyond API retention limits

### AI Analysis (Claude-powered)
- Natural language queries via Slack bot (`@alkimi-bot`)
- Automated pattern detection
- Arbitrage opportunity alerts
- Whale movement tracking
- Daily briefings for HFT traders

### Treasury Management
- Realized P&L tracking (FIFO accounting)
- Unrealized gains calculation
- Multi-wallet monitoring
- Historical daily snapshots

### Reporting
- Automated Slack reports (configurable interval)
- Exchange breakdown with volume metrics
- Net position tracking
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
│   │   ├── base.py              # ExchangeInterface
│   │   ├── mexc.py              # MEXC client
│   │   ├── kraken.py            # Kraken client
│   │   ├── kucoin.py            # KuCoin client
│   │   ├── gateio.py            # Gate.io client
│   │   ├── cetus.py             # Cetus DEX (positions)
│   │   └── sui_monitor.py       # Sui token contract monitor
│   │
│   ├── analytics/               # Analysis engines
│   │   ├── simple_tracker.py    # Main reporting engine
│   │   ├── position_tracker.py  # Position & P&L tracking
│   │   ├── pnl.py               # FIFO P&L calculations
│   │   ├── portfolio.py         # Portfolio aggregation
│   │   └── claude_analyst.py    # AI-powered analysis
│   │
│   ├── data/                    # Data management
│   │   ├── trade_cache.py       # SQLite trade persistence
│   │   ├── daily_snapshot.py    # Daily balance snapshots
│   │   ├── deposits_loader.py   # Initial deposit tracking
│   │   └── coingecko_client.py  # Price fallback
│   │
│   ├── reporting/               # Output formatting
│   │   ├── slack.py             # Slack webhook client
│   │   └── simple_formatter.py  # Report formatting
│   │
│   ├── bot/                     # Slack bot interface
│   │   └── slack_bot.py         # Conversational AI bot
│   │
│   └── utils/                   # Shared utilities
│       ├── logging.py           # Structured logging
│       ├── cache.py             # Response caching
│       └── trade_deduplication.py
│
├── scripts/                     # Utility scripts
│   ├── check_balances.py        # Balance checker
│   ├── recent_activity.py       # Activity summary
│   ├── price_impact.py          # Price impact analysis
│   └── cache_stats.py           # Cache statistics
│
├── docs/                        # Documentation
│   ├── DEX_INTEGRATION_RAILWAY_PLAN.md
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
| **Slack** | | |
| `SLACK_WEBHOOK_URL` | Yes | Slack webhook for reports |
| `SLACK_BOT_TOKEN` | No | Bot token for @alkimi-bot |
| `SLACK_APP_TOKEN` | No | App token for socket mode |
| **Application** | | |
| `MOCK_MODE` | No | Use mock data (default: false) |
| `LOG_LEVEL` | No | Logging level (default: INFO) |
| `REPORT_INTERVAL` | No | Report interval in seconds |

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

```
@alkimi-bot What was our best performing venue yesterday?

@alkimi-bot Show me the spread between MEXC and Gate.io

@alkimi-bot Summarize overnight activity

@alkimi-bot What arbitrage opportunities exist?

@alkimi-bot What's our total unrealized P&L?
```

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
