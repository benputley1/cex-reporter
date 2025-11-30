# Railway Deployment Configuration - Implementation Summary

This document summarizes the Railway deployment configuration that has been implemented for the ALKIMI Slack bot project.

## What Was Implemented

### 1. Modified `main.py` - Added Refresh Mode

**File**: `/Users/ben/Desktop/cex-reporter/main.py`

**Changes**:
- Added new `--mode refresh` argument option (alongside existing `once` and `continuous`)
- Implemented new `run_refresh()` method in `CEXReporter` class
- Refresh mode performs silent data collection without sending Slack reports

**Key Features of Refresh Mode**:
```python
async def run_refresh(self):
    """Run data refresh only - no Slack reporting"""
    # Initializes exchanges
    # Fetches current balances and trades
    # Updates trade_cache.db
    # Saves daily snapshot
    # Logs summary but does NOT send to Slack
    # Exits cleanly
```

**Usage**:
```bash
# Run once and send Slack report
python main.py --mode once

# Run continuously with periodic reports
python main.py --mode continuous

# Run once, update database, NO Slack report (NEW)
python main.py --mode refresh
```

### 2. Updated `railway.toml` - Bot Service Configuration

**File**: `/Users/ben/Desktop/cex-reporter/railway.toml`

**Purpose**: Configuration for the always-running Slack bot service

**Configuration**:
```toml
[build]
builder = "dockerfile"

[deploy]
startCommand = "python bot_main.py"
healthcheckPath = "/"
healthcheckTimeout = 300
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10

[service]
internalPort = 8080
```

### 3. Created `railway-cron.toml` - Cron Service Configuration

**File**: `/Users/ben/Desktop/cex-reporter/railway-cron.toml` (NEW)

**Purpose**: Configuration for the hourly data refresh cron job

**Configuration**:
```toml
[build]
builder = "dockerfile"

[deploy]
startCommand = "python main.py --mode refresh"
restartPolicyType = "NEVER"
```

**Note**: Cron schedule (`0 * * * *`) is configured in Railway UI, not in this file.

### 4. Updated `Dockerfile` - Support for Both Services

**File**: `/Users/ben/Desktop/cex-reporter/Dockerfile`

**Changes**:
- Added documentation for two deployment modes
- Created `/app/data/snapshots` and `/app/data/functions` directories
- Updated default CMD to `python bot_main.py`
- Added notes about Railway volume mounting at `/app/data`

**Key Features**:
- Multi-stage build for optimized image size
- Python 3.11-slim base image
- Supports both bot service and cron service via different start commands
- Volume-ready: `/app/data` directory structure pre-created

### 5. Verified `.dockerignore` - Already Correct

**File**: `/Users/ben/Desktop/cex-reporter/.dockerignore`

**Status**: No changes needed - already excludes:
- Local data/ and logs/ directories (will be mounted as volumes)
- Python cache files
- Environment files
- Development files

### 6. Created Comprehensive Deployment Documentation

**File**: `/Users/ben/Desktop/cex-reporter/docs/RAILWAY_DEPLOYMENT.md` (NEW)

**Sections**:
1. Architecture Overview - Two services + shared volume
2. Prerequisites - Railway account, API keys
3. Step-by-Step Setup - Complete Railway configuration guide
4. Service 1: Slack Bot (always-on) - Full configuration
5. Service 2: Cron Data Refresh - Full configuration
6. Shared Volume Setup - Volume creation and mounting
7. Environment Variables - Complete list for both services
8. Cron Schedule Reference - Schedule syntax examples
9. Monitoring & Maintenance - Logs, health checks, troubleshooting
10. Common Issues - Bot not responding, cron not running, database locks
11. Updating the Application - Git push, manual deploy, rollback
12. Cost Optimization - Pricing estimates and tips
13. Troubleshooting Commands - Railway CLI reference
14. Security Best Practices - API key management

**Key Features**:
- Complete environment variable reference
- Common troubleshooting scenarios with solutions
- Railway CLI commands
- Cost estimates (~$8-11/month)
- Security best practices

### 7. Updated `.env.example` - Deployment Paths

**File**: `/Users/ben/Desktop/cex-reporter/.env.example`

**Changes**:
- Added Railway deployment path configuration (commented out)
- Clear separation between local development and Railway paths

**New Section**:
```bash
# Local development paths
TRADE_CACHE_DB=data/trade_cache.db
LOG_DIR=logs
DATA_DIR=data
DEPOSITS_FILE=deposits & withdrawals.xlsx

# Railway deployment paths (uncomment for Railway)
# TRADE_CACHE_DB=/app/data/trade_cache.db
# DB_PATH=/app/data/trade_cache.db
# DATA_DIR=/app/data
# SNAPSHOTS_DIR=/app/data/snapshots
# LOG_DIR=/app/logs
```

## File Summary

### Modified Files (3)
1. `/Users/ben/Desktop/cex-reporter/main.py` - Added `--mode refresh` support
2. `/Users/ben/Desktop/cex-reporter/railway.toml` - Updated for bot service
3. `/Users/ben/Desktop/cex-reporter/Dockerfile` - Updated for both services
4. `/Users/ben/Desktop/cex-reporter/.env.example` - Added deployment paths

### New Files (3)
1. `/Users/ben/Desktop/cex-reporter/railway-cron.toml` - Cron service configuration
2. `/Users/ben/Desktop/cex-reporter/docs/RAILWAY_DEPLOYMENT.md` - Complete deployment guide
3. `/Users/ben/Desktop/cex-reporter/RAILWAY_DEPLOYMENT_SUMMARY.md` - This file

### Verified Files (1)
1. `/Users/ben/Desktop/cex-reporter/.dockerignore` - Already correct, no changes needed

## Architecture Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                     Railway Project                          │
│                   "alkimi-trading-bot"                       │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────────────┐      ┌──────────────────────┐    │
│  │  Service 1: Bot      │      │ Service 2: Cron      │    │
│  │  (Always Running)    │      │ (Hourly)             │    │
│  ├──────────────────────┤      ├──────────────────────┤    │
│  │ bot_main.py          │      │ main.py --mode       │    │
│  │                      │      │ refresh              │    │
│  │ - Slack interactions │      │                      │    │
│  │ - LLM queries        │      │ - Fetch CEX trades   │    │
│  │ - P&L calculations   │      │ - Fetch DEX trades   │    │
│  │ - Read from DB       │      │ - Update trade_cache │    │
│  │                      │      │ - Save snapshots     │    │
│  └──────────┬───────────┘      └──────────┬───────────┘    │
│             │                             │                 │
│             │    ┌─────────────────┐     │                 │
│             └────►  Shared Volume  ◄─────┘                 │
│                  │  /app/data      │                        │
│                  ├─────────────────┤                        │
│                  │ trade_cache.db  │                        │
│                  │ snapshots/      │                        │
│                  │ functions/      │                        │
│                  └─────────────────┘                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Data Flow

### Hourly Cron Job (Service 2)
```
1. Cron triggers at :00 (every hour)
2. python main.py --mode refresh executes
3. Initialize all exchange clients (MEXC, Gate.io, KuCoin, etc.)
4. Fetch current balances from all exchanges
5. Fetch recent trades from all exchanges
6. Update /app/data/trade_cache.db with new trades
7. Save daily snapshot to /app/data/snapshots/YYYY-MM-DD.json
8. Log summary (trade count, balances)
9. Exit cleanly (no Slack message)
```

### User Query (Service 1 - Bot)
```
1. User sends message in Slack: "@alkimi show me P&L for November"
2. Slack bot receives message
3. Claude LLM analyzes query
4. Generates SQL query or Python code
5. Reads from /app/data/trade_cache.db (populated by cron)
6. Calculates P&L from cached trades
7. Formats result with rich Slack blocks
8. Sends response to user in Slack
```

## Key Benefits of This Architecture

1. **Separation of Concerns**
   - Bot handles user interactions
   - Cron handles data collection
   - Clean, maintainable code

2. **Shared Data**
   - Single source of truth (trade_cache.db)
   - No data synchronization issues
   - Both services access same database

3. **Cost Effective**
   - Cron runs ~5 minutes/hour = ~2.5 hours/month
   - Bot always-on but minimal resource usage when idle
   - Total: ~$8-11/month on Railway

4. **Scalable**
   - Can adjust cron frequency (30 min, 2 hours, etc.)
   - Can scale bot resources independently
   - Can add more cron jobs for different tasks

5. **Resilient**
   - Bot restarts on failure (up to 10 retries)
   - Cron failures don't affect bot
   - SQLite handles concurrent access safely

## Environment Variables Required

Both services need the same environment variables. Here's the checklist:

### Critical (Service Won't Start Without These)
- [ ] SLACK_BOT_TOKEN
- [ ] SLACK_APP_TOKEN
- [ ] SLACK_SIGNING_SECRET
- [ ] ANTHROPIC_API_KEY
- [ ] TRADE_CACHE_DB=/app/data/trade_cache.db
- [ ] DATA_DIR=/app/data

### Important (For Full Functionality)
- [ ] All exchange API keys (MEXC, Gate.io, KuCoin, Kraken)
- [ ] SLACK_WEBHOOK_URL
- [ ] TRACKED_ASSETS=USDT,ALKIMI
- [ ] LOG_LEVEL=INFO

### Optional (Enhanced Features)
- [ ] SUI_RPC_URL (for DEX tracking)
- [ ] ALKIMI_TOKEN_CONTRACT (for DEX tracking)
- [ ] SUI_WALLET_* addresses (for DEX tracking)
- [ ] COINGECKO_API_KEY (for price fallback)

## Testing the Implementation

### Local Testing (Refresh Mode)
```bash
# Activate virtual environment
source venv/bin/activate  # or: venv\Scripts\activate on Windows

# Test refresh mode locally
python main.py --mode refresh

# Expected output:
# ========================================================
# DATA REFRESH MODE - No Slack reporting
# ========================================================
# Initializing exchange clients...
# Fetching balances and trades...
# Saving daily snapshot...
# Fetching and caching trades...
# ========================================================
# DATA REFRESH SUMMARY
# ========================================================
# Total trades cached: X
# Complete data window starts: YYYY-MM-DD
# Current USDT balance: $X,XXX.XX
# Current ALKIMI balance: X,XXX
# ========================================================
# Data refresh complete (no Slack report sent)
# ========================================================
```

### Railway Deployment Testing

1. **Bot Service**:
   ```bash
   railway logs -s alkimi-bot -f
   # Should see: "Bot will be available in Slack once connected"
   ```

2. **Cron Service** (wait for top of hour):
   ```bash
   railway logs -s cex-data-refresh
   # Should see: "DATA REFRESH SUMMARY"
   ```

3. **End-to-End Test**:
   - In Slack: `@alkimi show me today's trades`
   - Should return trades from most recent cron run

## Next Steps for Deployment

1. **Create Railway Project**: Follow docs/RAILWAY_DEPLOYMENT.md
2. **Create Shared Volume**: Name it `alkimi-data`, mount at `/app/data`
3. **Deploy Bot Service**: Connect GitHub repo, use railway.toml
4. **Deploy Cron Service**: Same repo, use railway-cron.toml concept
5. **Set Environment Variables**: Copy all from .env to Railway
6. **Test**: Send message to bot, wait for cron to run
7. **Monitor**: Check logs, verify data updates

## Support

For detailed deployment instructions, see:
- `/Users/ben/Desktop/cex-reporter/docs/RAILWAY_DEPLOYMENT.md`

For bot usage instructions, see:
- `/Users/ben/Desktop/cex-reporter/docs/BOT_QUICK_REFERENCE.md`
- `/Users/ben/Desktop/cex-reporter/docs/SLACK_BOT_SETUP.md`

---

**Implementation Complete!** All files configured for Railway deployment with two-service architecture.
