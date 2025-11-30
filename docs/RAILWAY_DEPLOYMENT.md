# Railway Deployment Guide

This guide covers deploying the ALKIMI Slack bot and data refresh system on Railway with two services sharing a persistent volume.

## Architecture Overview

The deployment consists of two Railway services that share data via a persistent volume:

### Service 1: alkimi-bot (Always Running)
- **Type**: Web Service (always-on)
- **Command**: `python bot_main.py`
- **Purpose**: Handles Slack user interactions, LLM queries, P&L calculations
- **Resources**: 512MB RAM minimum (recommended: 1GB for Claude API operations)
- **Restart Policy**: On Failure

### Service 2: cex-data-refresh (Hourly Cron)
- **Type**: Cron Job
- **Command**: `python main.py --mode refresh`
- **Schedule**: `0 * * * *` (every hour at :00 minutes)
- **Purpose**: Fetch latest CEX/DEX trades, update database, save daily snapshots
- **Resources**: 512MB RAM minimum

### Shared Volume
Both services mount `/app/data` containing:
- `trade_cache.db` - SQLite database with trades, saved functions, configuration
- `snapshots/` - Daily balance JSON files for historical tracking
- `functions/` - User-saved Python functions

## Prerequisites

1. **Railway Account**: Sign up at https://railway.app
2. **GitHub Repository**: Your code should be in a GitHub repository
3. **API Keys Ready**:
   - Slack Bot Token (xoxb-...)
   - Slack App Token (xapp-...)
   - Slack Signing Secret
   - Anthropic API Key
   - Exchange API credentials (MEXC, Gate.io, KuCoin, etc.)

## Step-by-Step Setup

### 1. Create Railway Project

```bash
# Install Railway CLI (optional, but recommended)
npm install -g @railway/cli

# Login to Railway
railway login

# Create new project
railway init
```

Or use the Railway web dashboard:
1. Go to https://railway.app/dashboard
2. Click "New Project"
3. Select "Empty Project"
4. Name it: `alkimi-trading-bot`

### 2. Create Shared Volume

**IMPORTANT**: Create the volume BEFORE creating services.

1. In Railway Dashboard → Your Project
2. Click "Create" → "Volume"
3. Configure:
   - **Name**: `alkimi-data`
   - **Mount Path**: `/app/data`
   - Click "Create"

### 3. Create Service 1: Slack Bot (Always-On)

#### 3.1 Create the Service

1. Railway Dashboard → Your Project → "Create" → "GitHub Repo"
2. Connect your repository
3. Select the repository containing this code
4. Railway will auto-detect the Dockerfile

#### 3.2 Configure the Service

1. **Service Name**: Click on the service → Settings → rename to `alkimi-bot`

2. **Build Settings**:
   - Builder: Dockerfile (auto-detected)
   - Root Directory: `/` (unless your code is in a subdirectory)

3. **Deploy Settings**:
   - Start Command: `python bot_main.py`
   - Custom Dockerfile Path: `Dockerfile` (default)

4. **Restart Policy**:
   - Type: On Failure
   - Max Retries: 10

5. **Resources** (Settings → Resources):
   - Memory: 1GB (recommended for Claude API operations)
   - CPU: Shared (default)

#### 3.3 Attach Volume to Bot Service

1. Service Settings → Volumes
2. Click "Attach Existing Volume"
3. Select: `alkimi-data`
4. Mount Path: `/app/data` (should be pre-filled)
5. Click "Attach"

#### 3.4 Set Environment Variables

Navigate to Service → Variables and add ALL of the following:

**Slack Configuration (REQUIRED)**
```bash
SLACK_BOT_TOKEN=xoxb-your-bot-token-here
SLACK_APP_TOKEN=xapp-your-app-token-here
SLACK_SIGNING_SECRET=your-signing-secret-here
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
```

**Claude AI (REQUIRED)**
```bash
ANTHROPIC_API_KEY=sk-ant-your-api-key-here
CLAUDE_MODEL=claude-sonnet-4-20250514
```

**Database Paths (REQUIRED)**
```bash
TRADE_CACHE_DB=/app/data/trade_cache.db
DB_PATH=/app/data/trade_cache.db
DATA_DIR=/app/data
SNAPSHOTS_DIR=/app/data/snapshots
LOG_DIR=/app/logs
```

**Exchange API Keys (REQUIRED for data collection)**

MEXC Accounts:
```bash
MEXC_MM1_API_KEY=your_mexc_mm1_api_key
MEXC_MM1_API_SECRET=your_mexc_mm1_api_secret
MEXC_MM2_API_KEY=your_mexc_mm2_api_key
MEXC_MM2_API_SECRET=your_mexc_mm2_api_secret
MEXC_TM1_API_KEY=your_mexc_tm1_api_key
MEXC_TM1_API_SECRET=your_mexc_tm1_api_secret
```

Gate.io Accounts:
```bash
GATEIO_MM1_API_KEY=your_gateio_mm1_api_key
GATEIO_MM1_API_SECRET=your_gateio_mm1_api_secret
GATEIO_MM2_API_KEY=your_gateio_mm2_api_key
GATEIO_MM2_API_SECRET=your_gateio_mm2_api_secret
GATEIO_TM_API_KEY=your_gateio_tm_api_key
GATEIO_TM_API_SECRET=your_gateio_tm_api_secret
```

KuCoin Accounts:
```bash
KUCOIN_MM1_API_KEY=your_kucoin_mm1_api_key
KUCOIN_MM1_API_SECRET=your_kucoin_mm1_api_secret
KUCOIN_MM1_API_PASSPHRASE=your_kucoin_mm1_passphrase
KUCOIN_MM2_API_KEY=your_kucoin_mm2_api_key
KUCOIN_MM2_API_SECRET=your_kucoin_mm2_api_secret
KUCOIN_MM2_API_PASSPHRASE=your_kucoin_mm2_passphrase
```

Kraken:
```bash
KRAKEN_API_KEY=your_kraken_api_key
KRAKEN_API_SECRET=your_kraken_api_secret
```

**Application Settings**
```bash
LOG_LEVEL=INFO
MOCK_MODE=false
TRACKED_ASSETS=USDT,ALKIMI
HISTORICAL_START_DATE=2025-08-19
BASE_CURRENCY=USD
REPORT_INTERVAL=14400
ALERT_THRESHOLD_PERCENT=5.0
```

**Sui Blockchain (for DEX tracking)**
```bash
SUI_RPC_URL=https://fullnode.mainnet.sui.io
ALKIMI_TOKEN_CONTRACT=your_alkimi_token_contract_address
SUI_WALLET_TREASURY=your_treasury_wallet_address
SUI_WALLET_MM1=your_mm1_wallet_address
SUI_WALLET_MM2=your_mm2_wallet_address
```

### 4. Create Service 2: Cron Data Refresh

#### 4.1 Create the Cron Service

1. Railway Dashboard → Your Project → "Create" → "Cron Job"
2. Connect the SAME GitHub repository
3. Railway will use the same Dockerfile

#### 4.2 Configure the Cron Service

1. **Service Name**: Rename to `cex-data-refresh`

2. **Deploy Settings**:
   - Start Command: `python main.py --mode refresh`
   - Cron Schedule: `0 * * * *`

3. **Build Settings**:
   - Builder: Dockerfile (same as bot service)

4. **Resources**:
   - Memory: 512MB
   - CPU: Shared

#### 4.3 Attach Volume to Cron Service

1. Service Settings → Volumes
2. Click "Attach Existing Volume"
3. Select: `alkimi-data` (same volume as bot)
4. Mount Path: `/app/data`
5. Click "Attach"

#### 4.4 Set Environment Variables

The cron service needs the SAME environment variables as the bot service (especially exchange API keys and database paths).

**Recommended Approach**: Copy all variables from the bot service.

**Critical Variables for Cron**:
```bash
# Database paths (MUST match bot service)
TRADE_CACHE_DB=/app/data/trade_cache.db
DATA_DIR=/app/data
SNAPSHOTS_DIR=/app/data/snapshots

# All exchange API credentials
MEXC_MM1_API_KEY=...
MEXC_MM1_API_SECRET=...
# ... (all other exchange keys)

# Application settings
LOG_LEVEL=INFO
MOCK_MODE=false
TRACKED_ASSETS=USDT,ALKIMI
```

**Note**: The cron service does NOT need Slack or Anthropic API keys, but it's simpler to use the same .env configuration.

### 5. Deploy Both Services

1. **Trigger Deployment**:
   - Railway auto-deploys on git push to main/master
   - Or manually trigger: Dashboard → Service → "Deploy"

2. **Monitor Deployment**:
   ```bash
   # Via CLI
   railway logs -s alkimi-bot
   railway logs -s cex-data-refresh
   ```

   Or via Dashboard → Service → "Deployments" tab

3. **Verify Bot Service**:
   - Check logs for: "Bot will be available in Slack once connected"
   - In Slack, send a DM to your bot: `/alkimi help`
   - Should receive help message

4. **Verify Cron Service**:
   - Wait for top of the hour
   - Check logs for: "DATA REFRESH SUMMARY"
   - Should see trade counts and balance updates

### 6. Verify Shared Volume

Both services should be reading/writing to the same SQLite database.

1. Check bot logs for: `Database: /app/data/trade_cache.db`
2. Run a query in Slack: `@alkimi show me trades from today`
3. Check cron logs for: `Total trades cached: X`
4. The bot should be able to query trades cached by the cron job

## Cron Schedule Reference

The cron service uses standard cron syntax:

```
┌───────────── minute (0 - 59)
│ ┌───────────── hour (0 - 23)
│ │ ┌───────────── day of month (1 - 31)
│ │ │ ┌───────────── month (1 - 12)
│ │ │ │ ┌───────────── day of week (0 - 6) (Sunday to Saturday)
│ │ │ │ │
* * * * *
```

**Common Schedules**:
- `0 * * * *` - Every hour at :00 minutes (recommended)
- `*/30 * * * *` - Every 30 minutes
- `0 */2 * * *` - Every 2 hours
- `0 9,17 * * *` - 9 AM and 5 PM daily
- `0 0 * * *` - Midnight daily

## Monitoring & Maintenance

### View Logs

**Via Railway CLI**:
```bash
# Bot service
railway logs -s alkimi-bot

# Cron service
railway logs -s cex-data-refresh

# Follow logs in real-time
railway logs -s alkimi-bot -f
```

**Via Dashboard**:
1. Service → "Deployments" → Click deployment → "View Logs"

### Health Checks

**Bot Service**:
1. Send `/alkimi help` in Slack
2. Check response time and content
3. Monitor logs for errors

**Cron Service**:
1. Check logs after each hourly run
2. Look for "Data refresh complete"
3. Verify trade counts are increasing

**Database Health**:
```bash
# Connect to bot service shell (via Railway CLI)
railway shell -s alkimi-bot

# Check database
python -c "from src.data import TradeCache; tc = TradeCache(); print(f'Trades: {len(tc.get_all_trades())}')"
```

### Common Issues

#### Bot Not Responding in Slack

**Symptoms**: No response to mentions or DMs

**Solutions**:
1. Check Railway logs for errors
2. Verify SLACK_BOT_TOKEN is correct
3. Confirm Socket Mode is enabled in Slack app settings
4. Check Slack app has correct scopes:
   - `app_mentions:read`
   - `chat:write`
   - `commands`
   - `im:history`
   - `im:read`
5. Reinstall Slack app to workspace if needed

#### Cron Job Not Running

**Symptoms**: No hourly logs, data not updating

**Solutions**:
1. Check cron schedule syntax in Railway
2. Verify service is active (not paused)
3. Check Railway logs for errors
4. Ensure start command is `python main.py --mode refresh`

#### Database Lock Errors

**Symptoms**: SQLite database locked errors in logs

**Solutions**:
1. Verify volume mount path is correct on BOTH services: `/app/data`
2. Check both services use same TRADE_CACHE_DB path
3. SQLite has built-in retry logic, occasional locks are normal
4. If persistent, consider reducing cron frequency

#### Volume Mount Issues

**Symptoms**: Database not found, data not persisting

**Solutions**:
1. Verify volume is attached to BOTH services
2. Check mount path is `/app/data` on both
3. Verify environment variable: `TRADE_CACHE_DB=/app/data/trade_cache.db`
4. Check Railway Dashboard → Volume → "Mounts" shows both services

### Updating the Application

**Via Git Push** (recommended):
```bash
git add .
git commit -m "Update bot features"
git push origin main
# Railway auto-deploys both services
```

**Manual Deploy**:
1. Railway Dashboard → Service → "Deploy Latest"

**Rollback**:
1. Railway Dashboard → Service → "Deployments"
2. Find previous deployment
3. Click "..." → "Rollback"

### Cost Optimization

**Railway Pricing** (as of 2024):
- Hobby Plan: $5/month (500 hours execution time)
- Pro Plan: $20/month + usage

**Estimated Monthly Usage**:
- Bot Service: ~730 hours (always-on) = ~$7-10/month
- Cron Service: ~2 hours/month (5 min × 24 × 30) = ~$0.50/month
- Volume: 1GB = $0.10/GB/month
- **Total**: ~$8-11/month on Pro plan

**Optimization Tips**:
1. Use Hobby plan if bot is low-traffic
2. Reduce cron frequency to every 2-4 hours if acceptable
3. Monitor memory usage and reduce allocations if possible
4. Use Railway's auto-sleep for bot during off-hours (if acceptable)

## Troubleshooting Commands

```bash
# Check service status
railway status

# View environment variables
railway variables

# Access service shell
railway shell -s alkimi-bot

# Check volume mounts
railway volume list

# Restart service
railway restart -s alkimi-bot

# View recent deployments
railway deployments

# Check build logs
railway logs -s alkimi-bot --deployment
```

## Security Best Practices

1. **Never commit API keys**: Use Railway environment variables
2. **Rotate keys regularly**: Update in Railway Dashboard → Variables
3. **Use read-only exchange APIs**: Where possible, limit API permissions
4. **Monitor logs**: Check for unauthorized access attempts
5. **Keep dependencies updated**: Regularly update requirements.txt
6. **Use Railway secrets**: For highly sensitive data

## Support & Resources

- **Railway Docs**: https://docs.railway.app
- **Railway Discord**: https://discord.gg/railway
- **Slack API Docs**: https://api.slack.com/docs
- **Project GitHub**: Your repository URL

## Next Steps

After successful deployment:

1. **Test bot features**: Try natural language queries in Slack
2. **Set up alerts**: Configure Slack alerts for important events
3. **Create saved functions**: Use `/alkimi save-function` for common queries
4. **Monitor performance**: Check logs and response times
5. **Customize reports**: Adjust formatting in `src/reporting/`

---

**Deployment Complete!** Your ALKIMI bot should now be live on Railway with hourly data refresh. 🚀
