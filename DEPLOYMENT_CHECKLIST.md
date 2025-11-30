# Railway Deployment Checklist

Quick reference checklist for deploying the ALKIMI Slack bot to Railway.

## Pre-Deployment Checklist

### Code Changes (✓ Complete)
- [x] Modified `main.py` with `--mode refresh` support
- [x] Updated `railway.toml` for bot service
- [x] Created `railway-cron.toml` for cron service
- [x] Updated `Dockerfile` for both services
- [x] Verified `.dockerignore` is correct
- [x] Created `docs/RAILWAY_DEPLOYMENT.md`
- [x] Updated `.env.example` with deployment paths

### API Keys & Credentials (To Do)
- [ ] Slack Bot Token (xoxb-...)
- [ ] Slack App Token (xapp-...)
- [ ] Slack Signing Secret
- [ ] Anthropic API Key
- [ ] MEXC API keys (MM1, MM2, TM1)
- [ ] Gate.io API keys (MM1, MM2, TM)
- [ ] KuCoin API keys (MM1, MM2) + passphrases
- [ ] Kraken API keys (if used)
- [ ] Slack Webhook URL

### Repository Setup (To Do)
- [ ] Push all changes to GitHub
- [ ] Verify main/master branch is up to date
- [ ] Tag release (optional): `git tag v1.0-railway`

## Railway Deployment Steps

### 1. Create Railway Project
- [ ] Sign up at https://railway.app
- [ ] Create new project: "alkimi-trading-bot"

### 2. Create Shared Volume (FIRST!)
- [ ] Click "Create" → "Volume"
- [ ] Name: `alkimi-data`
- [ ] Mount Path: `/app/data`

### 3. Deploy Bot Service (Service 1)
- [ ] Create service from GitHub repo
- [ ] Rename service: `alkimi-bot`
- [ ] Set start command: `python bot_main.py`
- [ ] Attach volume: `alkimi-data` at `/app/data`
- [ ] Set all environment variables (see below)
- [ ] Set restart policy: On Failure (10 retries)
- [ ] Set memory: 1GB
- [ ] Deploy

### 4. Deploy Cron Service (Service 2)
- [ ] Create cron service from same GitHub repo
- [ ] Rename service: `cex-data-refresh`
- [ ] Set start command: `python main.py --mode refresh`
- [ ] Set cron schedule: `0 * * * *`
- [ ] Attach volume: `alkimi-data` at `/app/data`
- [ ] Copy all environment variables from bot service
- [ ] Set memory: 512MB
- [ ] Deploy

### 5. Environment Variables (Both Services)

**Critical Variables**:
```bash
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
SLACK_SIGNING_SECRET=...
ANTHROPIC_API_KEY=sk-ant-...
TRADE_CACHE_DB=/app/data/trade_cache.db
DB_PATH=/app/data/trade_cache.db
DATA_DIR=/app/data
SNAPSHOTS_DIR=/app/data/snapshots
LOG_DIR=/app/logs
```

**Exchange APIs** (copy all from .env):
```bash
MEXC_MM1_API_KEY=...
MEXC_MM1_API_SECRET=...
# ... (all exchange credentials)
```

**Application Settings**:
```bash
LOG_LEVEL=INFO
MOCK_MODE=false
TRACKED_ASSETS=USDT,ALKIMI
HISTORICAL_START_DATE=2025-08-19
```

## Post-Deployment Verification

### Test Bot Service
- [ ] Check Railway logs for: "Bot will be available in Slack"
- [ ] In Slack, send DM: `/alkimi help`
- [ ] Verify bot responds with help message
- [ ] Test query: `@alkimi show me today's balances`

### Test Cron Service
- [ ] Wait for top of hour
- [ ] Check Railway logs for: "DATA REFRESH SUMMARY"
- [ ] Verify trade count increases
- [ ] Check bot can query cached data

### Verify Shared Volume
- [ ] Both services show `/app/data` mounted in Railway
- [ ] Bot logs show: `Database: /app/data/trade_cache.db`
- [ ] Cron logs show same database path
- [ ] Query from bot returns trades cached by cron

## Monitoring Setup

### Set Up Alerts
- [ ] Railway dashboard → Project → Settings → Notifications
- [ ] Enable deployment notifications
- [ ] Enable error notifications

### Create Slack Channel for Logs (Optional)
- [ ] Create #alkimi-bot-logs channel
- [ ] Configure Railway to send alerts there

### Bookmark Key URLs
- [ ] Railway project dashboard
- [ ] Bot service logs
- [ ] Cron service logs
- [ ] Slack app management

## Common First-Time Issues

### Bot Not Responding
1. Check SLACK_BOT_TOKEN is correct
2. Verify Socket Mode enabled in Slack app
3. Reinstall app to workspace
4. Check scopes: app_mentions:read, chat:write, commands

### Cron Not Running
1. Verify cron schedule syntax: `0 * * * *`
2. Check start command: `python main.py --mode refresh`
3. Verify service is active (not paused)

### Database Not Found
1. Check volume mounted at `/app/data` on BOTH services
2. Verify TRADE_CACHE_DB=/app/data/trade_cache.db
3. Check volume "Mounts" tab shows both services

## Quick Commands

```bash
# View bot logs
railway logs -s alkimi-bot -f

# View cron logs
railway logs -s cex-data-refresh

# Check service status
railway status

# Restart bot
railway restart -s alkimi-bot

# Access bot shell
railway shell -s alkimi-bot

# List volumes
railway volume list
```

## Cost Estimate

- Bot Service: ~730 hours/month (always-on) = $7-10/month
- Cron Service: ~2.5 hours/month = $0.50/month
- Volume: 1GB = $0.10/month
- **Total**: ~$8-11/month on Railway Pro plan

## Support Resources

- Full Guide: `/Users/ben/Desktop/cex-reporter/docs/RAILWAY_DEPLOYMENT.md`
- Railway Docs: https://docs.railway.app
- Railway Discord: https://discord.gg/railway
- Slack API: https://api.slack.com/docs

---

**Ready to Deploy!** Follow this checklist step-by-step for a smooth Railway deployment.
