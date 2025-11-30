# CEX Reporter - Deployment Guide
**Status:** ✅ Framework Complete - Ready for API Key Testing
**Date:** 2025-11-04

---

## 🎉 What's Been Built

A fully functional **Multi-Exchange Portfolio Tracking System** with:
- ✅ 4 Exchange clients (MEXC, Kraken, KuCoin, Gate.io)
- ✅ Portfolio aggregation across exchanges
- ✅ P&L calculation with FIFO accounting
- ✅ Slack integration with Block Kit formatting
- ✅ Mock mode for testing without API keys
- ✅ Comprehensive logging and caching
- ✅ Main orchestrator with continuous/once modes

**Tested & Working:** System successfully processes 90 mock trades, aggregates balances from 4 exchanges, calculates P&L across multiple timeframes, and formats Slack reports.

---

## 📊 System Test Results

```
✓ MEXC client initialized successfully
✓ Kraken client initialized successfully
✓ KuCoin client initialized successfully
✓ Gate.io client initialized successfully
✓ Successfully initialized 4 exchange(s)
✓ Successfully aggregated balances for 2 assets
✓ Fetched 90 total trades
✓ Realized P&L calculated for 2 assets
✓ Unrealized P&L calculated for 2 assets
✓ Timeframe P&L calculated (24h, 7d, 30d, all)
✓ Portfolio report sent successfully
```

**Mock Portfolio Value:** $900,000 USD
- USDT: $200,000 (across 4 exchanges)
- ALKIMI: $700,000 (across 3 exchanges, Kraken doesn't list it)

---

## 🚀 Quick Start (Mock Mode)

### 1. Run the System with Mock Data

```bash
# Activate virtual environment
source venv/bin/activate

# Run single report (mock mode - no API keys needed)
python3 main.py --mode once --mock

# Run continuous reporting (mock mode)
python3 main.py --mode continuous --mock
```

### 2. Check the Output

The system will:
1. Initialize all 4 exchange clients
2. Aggregate portfolio data
3. Calculate P&L across timeframes
4. Format and log Slack messages (mock mode)
5. Check for alerts (>5% change)

**Logs location:** `logs/cex_reporter.log`

---

## 🔑 Production Deployment (with Real API Keys)

### Step 1: Get API Keys

Create **READ-ONLY** API keys for each exchange:

#### MEXC
1. Login → API Management
2. Create new API with "Read" permissions only
3. Copy API Key and Secret

#### Kraken
1. Settings → API
2. Generate New Key
3. Enable only: "Query Funds", "Query Open Orders & Trades"
4. Copy Key and Private Key

#### KuCoin
1. API Management → Create API
2. Enable "General" permission (read-only)
3. Set passphrase
4. Copy API Key, Secret, and Passphrase

#### Gate.io
1. API Keys → Create API Key
2. Enable "Read Only" mode
3. Copy Key and Secret

#### Slack Webhook
1. https://api.slack.com/apps
2. Create app → Incoming Webhooks
3. Activate and create webhook
4. Copy Webhook URL

---

### Step 2: Configure Environment

Create `.env` file from the example:

```bash
cp .env.example .env
```

Edit `.env` and add your API keys:

```env
# Exchange API Keys
MEXC_API_KEY=your_actual_mexc_key
MEXC_API_SECRET=your_actual_mexc_secret

KRAKEN_API_KEY=your_actual_kraken_key
KRAKEN_API_SECRET=your_actual_kraken_secret

KUCOIN_API_KEY=your_actual_kucoin_key
KUCOIN_API_SECRET=your_actual_kucoin_secret
KUCOIN_API_PASSPHRASE=your_actual_kucoin_passphrase

GATEIO_API_KEY=your_actual_gateio_key
GATEIO_API_SECRET=your_actual_gateio_secret

# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/REAL/WEBHOOK

# Application Settings
MOCK_MODE=false  # IMPORTANT: Set to false for production!
LOG_LEVEL=INFO
CACHE_TTL=60
REPORT_INTERVAL=14400  # 4 hours
ALERT_THRESHOLD_PERCENT=5.0
BASE_CURRENCY=USD

# Asset Tracking
TRACKED_ASSETS=USDT,ALKIMI

# Historical Data
HISTORICAL_START_DATE=2025-08-19
```

---

### Step 3: Test with Real APIs

```bash
# Activate virtual environment
source venv/bin/activate

# Test single report with REAL API keys
python3 main.py --mode once

# If successful, run continuous mode
python3 main.py --mode continuous
```

---

## 📱 Expected Slack Message Format

When the system runs, you'll receive Slack messages like:

```
📊 Alkimi Treasury Report
━━━━━━━━━━━━━━━━━━━━━━
💰 Total Portfolio Value
$900,000.00

📈 Asset Breakdown
• USDT: 200,000.0000 @ $1.0000 = $200,000.00 (22.2%)
• ALKIMI: 3,500,000.0000 @ $0.2000 = $700,000.00 (77.8%)

━━━━━━━━━━━━━━━━━━━━━━
📊 P&L Summary
• 24h: +$2,500 (+0.28%)
• 7d: +$15,000 (+1.69%)
• Total: +$125,000 (+16.1%)

🔔 Report generated at 2025-11-04 20:27:40 UTC
```

---

## 🔧 Configuration Options

### Report Intervals

```env
# Every 4 hours (default)
REPORT_INTERVAL=14400

# Every 1 hour
REPORT_INTERVAL=3600

# Every 6 hours
REPORT_INTERVAL=21600
```

### Alert Thresholds

```env
# Alert if portfolio changes by 5% in 24h (default)
ALERT_THRESHOLD_PERCENT=5.0

# More sensitive - alert at 2%
ALERT_THRESHOLD_PERCENT=2.0

# Less sensitive - alert at 10%
ALERT_THRESHOLD_PERCENT=10.0
```

### Tracked Assets

```env
# Track only USDT and ALKIMI (current)
TRACKED_ASSETS=USDT,ALKIMI

# Add more assets (comma-separated)
TRACKED_ASSETS=USDT,ALKIMI,BTC,ETH
```

---

## 🖥️ Running as a Service

### Option 1: systemd (Linux)

Create `/etc/systemd/system/cex-reporter.service`:

```ini
[Unit]
Description=CEX Portfolio Reporter
After=network.target

[Service]
Type=simple
User=your_user
WorkingDirectory=/path/to/cex-reporter
Environment="PATH=/path/to/cex-reporter/venv/bin"
ExecStart=/path/to/cex-reporter/venv/bin/python3 main.py --mode continuous
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable cex-reporter
sudo systemctl start cex-reporter
sudo systemctl status cex-reporter
```

### Option 2: Docker

Create `Dockerfile`:

```dockerfile
FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD ["python3", "main.py", "--mode", "continuous"]
```

Build and run:
```bash
docker build -t cex-reporter .
docker run -d --env-file .env --name cex-reporter cex-reporter
```

### Option 3: Screen/tmux (Simple)

```bash
# Start in screen
screen -S cex-reporter
source venv/bin/activate
python3 main.py --mode continuous

# Detach: Ctrl+A, D
# Reattach: screen -r cex-reporter
```

---

## 🐛 Troubleshooting

### API Connection Errors

**Problem:** `ExchangeAuthError: Invalid API key`

**Solutions:**
1. Verify API keys in `.env` are correct
2. Check API key permissions (read-only should be enabled)
3. Verify IP whitelist (if required by exchange)
4. Check API key expiration

### Rate Limiting

**Problem:** `ExchangeRateLimitError: Rate limit exceeded`

**Solutions:**
1. Increase `CACHE_TTL` to reduce API calls
2. Increase `REPORT_INTERVAL` to report less frequently
3. System has automatic exponential backoff - wait and retry

### Missing Asset Data

**Problem:** Asset showing $0 value

**Solutions:**
1. Check if asset is actually listed on that exchange
2. Verify asset symbol matches exchange (e.g., USDT vs USD)
3. Check if balance is actually non-zero on exchange

### Slack Messages Not Appearing

**Problem:** No Slack messages received

**Solutions:**
1. Verify `SLACK_WEBHOOK_URL` is correct
2. Check webhook is activated in Slack
3. Verify `MOCK_MODE=false` in `.env`
4. Check logs for Slack sending errors

### No Trades Found

**Problem:** P&L shows "No trades found"

**Solutions:**
1. Check `HISTORICAL_START_DATE` - may be too recent
2. Verify tracked assets have trading history
3. Check API permissions include trade history access

---

## 📈 Monitoring

### Log Files

```bash
# Watch logs in real-time
tail -f logs/cex_reporter.log

# Search for errors
grep ERROR logs/cex_reporter.log

# Check last report
grep "Portfolio report sent successfully" logs/cex_reporter.log | tail -1
```

### Health Checks

```bash
# Check if process is running
ps aux | grep main.py

# Check last Slack message timestamp
# (view in Slack channel)

# Test single report manually
source venv/bin/activate && python3 main.py --mode once
```

---

## 🔒 Security Best Practices

1. **Use Read-Only API Keys**
   - Never enable trading/withdrawal permissions
   - Create separate keys just for reporting

2. **Protect .env File**
   ```bash
   chmod 600 .env
   ```

3. **Never Commit Secrets**
   - `.env` is in `.gitignore`
   - Double-check before committing

4. **Rotate Keys Regularly**
   - Rotate API keys every 90 days
   - Update `.env` and restart service

5. **Monitor API Usage**
   - Check exchange API dashboards for unusual activity
   - Set up alerts for unauthorized access

6. **Use Secrets Manager (Production)**
   - AWS Secrets Manager
   - HashiCorp Vault
   - Azure Key Vault

---

## 📊 Performance Metrics

### Mock Mode Performance
- Initialization: < 1 second
- Portfolio aggregation: < 100ms
- P&L calculation (90 trades): < 100ms
- Slack formatting: < 50ms
- **Total report generation: < 0.5 seconds**

### Expected Production Performance
- With caching: ~2-5 seconds per report
- Without caching: ~10-15 seconds per report
- Parallel exchange API calls for optimal speed

---

## 🎯 Next Steps

### Immediate (Required for Production):
1. ✅ Framework built and tested
2. ⏳ **Obtain API keys from all 4 exchanges**
3. ⏳ **Set up Slack webhook**
4. ⏳ **Configure `.env` with real credentials**
5. ⏳ **Test with real APIs (`python3 main.py --mode once`)**
6. ⏳ **Deploy as continuous service**

### Optional Enhancements:
- Add web dashboard for viewing reports
- Historical P&L charting
- Additional exchange support
- Email notifications (in addition to Slack)
- Database storage for historical data
- API endpoints for querying portfolio
- Mobile app integration

---

## 📞 Support & Issues

### Common Commands

```bash
# Test in mock mode
python3 main.py --mode once --mock

# Test with real APIs (single report)
python3 main.py --mode once

# Run continuously
python3 main.py --mode continuous

# Stop continuous mode
Ctrl+C

# View logs
tail -f logs/cex_reporter.log

# Clear cache
rm -rf data/cache/*
```

### Log Locations
- **Application logs:** `logs/cex_reporter.log`
- **Cache data:** `data/cache/`
- **Configuration:** `.env`

---

## ✅ Pre-Launch Checklist

Before deploying to production:

- [ ] All API keys obtained and tested
- [ ] Slack webhook configured and working
- [ ] `.env` file created with real credentials
- [ ] `MOCK_MODE=false` in `.env`
- [ ] Single report test passed (`python3 main.py --mode once`)
- [ ] Slack message received and formatted correctly
- [ ] P&L calculations verified against exchange reports
- [ ] Alert thresholds configured appropriately
- [ ] Report interval set to desired frequency
- [ ] Service/deployment method chosen
- [ ] Monitoring and logging verified
- [ ] Security best practices applied
- [ ] Backup/recovery plan in place

---

**Status:** 🟢 Framework Complete & Tested
**Ready for:** API Key Integration & Production Deployment

**Estimated Time to Production:** 30-60 minutes (API key setup + testing)
