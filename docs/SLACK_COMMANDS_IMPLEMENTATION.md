# Slack Commands Implementation Guide

This guide walks through implementing slash commands for the CEX Reporter.

## Prerequisites

- Existing Slack workspace and app
- CEX Reporter installed and working
- Python 3.9+
- ngrok account (free) for testing

## Step-by-Step Implementation

### Phase 1: Set Up Web Server (30 minutes)

#### 1.1 Install Dependencies

```bash
cd /Users/ben/Desktop/cex-reporter
source venv/bin/activate
pip install fastapi uvicorn python-multipart slack-sdk python-dotenv
pip freeze > requirements.txt
```

#### 1.2 Create Server Structure

```bash
mkdir -p src/slack_server
touch src/slack_server/__init__.py
touch src/slack_server/server.py
touch src/slack_server/commands.py
touch src/slack_server/verification.py
```

---

### Phase 2: Implement Basic Server (45 minutes)

#### 2.1 Create Verification Module

File: `src/slack_server/verification.py`

```python
import hmac
import hashlib
import time
from typing import Optional

def verify_slack_signature(
    signing_secret: str,
    timestamp: str,
    signature: str,
    body: str
) -> bool:
    """
    Verify that the request came from Slack.

    Args:
        signing_secret: Your Slack app's signing secret
        timestamp: X-Slack-Request-Timestamp header
        signature: X-Slack-Signature header
        body: Raw request body

    Returns:
        True if signature is valid
    """
    # Prevent replay attacks
    if abs(time.time() - int(timestamp)) > 60 * 5:
        return False

    # Create signature base string
    sig_basestring = f"v0:{timestamp}:{body}"

    # Create HMAC SHA256 hash
    my_signature = 'v0=' + hmac.new(
        signing_secret.encode(),
        sig_basestring.encode(),
        hashlib.sha256
    ).hexdigest()

    # Compare signatures
    return hmac.compare_digest(my_signature, signature)
```

#### 2.2 Create Command Handlers

File: `src/slack_server/commands.py`

```python
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from config.settings import settings
from src.analytics.position_tracker import PositionTracker
from src.reporting.position_formatter import PositionFormatter
from src.reporting.slack import SlackClient
from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient


class CommandHandler:
    """Handle slash command execution"""

    def __init__(self):
        self.position_tracker = PositionTracker()
        self.position_formatter = PositionFormatter()
        self.slack_client = SlackClient()

    async def handle_cex_report(self, command_args: str) -> Dict[str, Any]:
        """Generate full position report"""

        # Initialize exchanges
        exchanges = await self._initialize_exchanges()

        # Generate report
        position_data = await self.position_tracker.get_position_report(exchanges)

        # Format for Slack
        message = self.position_formatter.format_position_report(position_data)

        # Send to Slack
        await self.slack_client.send_message(message)

        # Cleanup
        for exchange in exchanges:
            await exchange.close()

        return {
            "text": "✅ Position report generated successfully!"
        }

    async def handle_buysell_analysis(self, command_args: str) -> Dict[str, Any]:
        """Generate buy/sell analysis"""

        # Parse month from args (e.g., "october" or "2025-10")
        month = self._parse_month(command_args)

        if not month:
            return {
                "text": "Usage: `/cex-buysell [month]`\nExample: `/cex-buysell october` or `/cex-buysell 2025-10`"
            }

        # Run analysis in background
        # (Implementation here)

        return {
            "text": f"🔄 Generating buy/sell analysis for {month}..."
        }

    async def _initialize_exchanges(self):
        """Initialize all exchange clients"""
        exchange_classes = [
            ('mexc', 'MEXC', MEXCClient),
            ('kraken', 'Kraken', KrakenClient),
            ('kucoin', 'KuCoin', KuCoinClient),
            ('gateio', 'Gate.io', GateioClient),
        ]

        exchanges = []

        for exchange_key, display_name, exchange_class in exchange_classes:
            accounts = settings.get_exchange_accounts(exchange_key)
            if not accounts:
                continue

            for account_config in accounts:
                try:
                    exchange = exchange_class(
                        config=account_config,
                        account_name=account_config['account_name']
                    )
                    await exchange.initialize()
                    exchanges.append(exchange)
                except Exception as e:
                    print(f"Failed to initialize {display_name}: {e}")

        return exchanges

    def _parse_month(self, args: str) -> str:
        """Parse month from command arguments"""
        if not args:
            return "last 14 days"

        args = args.strip().lower()

        # Month name mapping
        month_map = {
            'january': '01', 'february': '02', 'march': '03',
            'april': '04', 'may': '05', 'june': '06',
            'july': '07', 'august': '08', 'september': '09',
            'october': '10', 'november': '11', 'december': '12'
        }

        if args in month_map:
            current_year = datetime.now().year
            return f"{current_year}-{month_map[args]}"

        return args
```

#### 2.3 Create Main Server

File: `src/slack_server/server.py`

```python
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
import os
import asyncio
from dotenv import load_dotenv

from .verification import verify_slack_signature
from .commands import CommandHandler

load_dotenv()

app = FastAPI(title="CEX Reporter Slack Commands")
command_handler = CommandHandler()

# Store in-progress tasks
background_tasks = {}


@app.post("/slack/commands")
async def handle_slash_command(request: Request):
    """Handle incoming slash commands from Slack"""

    # Get request data
    body = await request.body()
    form_data = await request.form()

    # Verify Slack signature
    signing_secret = os.getenv('SLACK_SIGNING_SECRET')
    timestamp = request.headers.get('X-Slack-Request-Timestamp', '')
    signature = request.headers.get('X-Slack-Signature', '')

    if not verify_slack_signature(signing_secret, timestamp, signature, body.decode()):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # Parse command
    command = form_data.get('command', '')
    text = form_data.get('text', '')
    user_id = form_data.get('user_id', '')

    # Respond immediately (Slack requires response within 3 seconds)
    if command == '/cex-report':
        # Queue background task
        task = asyncio.create_task(command_handler.handle_cex_report(text))
        background_tasks[user_id] = task

        return JSONResponse({
            "response_type": "in_channel",
            "text": "🔄 Generating position report... This may take a minute."
        })

    elif command == '/cex-buysell':
        return await command_handler.handle_buysell_analysis(text)

    elif command == '/cex-help':
        return JSONResponse({
            "response_type": "ephemeral",
            "text": (
                "*CEX Reporter Commands*\n\n"
                "`/cex-report` - Generate full position report\n"
                "`/cex-buysell [month]` - Buy/sell analysis (e.g., `/cex-buysell october`)\n"
                "`/cex-help` - Show this help message"
            )
        })

    else:
        return JSONResponse({
            "response_type": "ephemeral",
            "text": f"Unknown command: {command}\nUse `/cex-help` for available commands."
        })


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

---

### Phase 3: Configure Slack App (20 minutes)

#### 3.1 Get Signing Secret

1. Go to https://api.slack.com/apps
2. Select your CEX Reporter app
3. Go to "Basic Information"
4. Scroll to "App Credentials"
5. Copy the "Signing Secret"

#### 3.2 Add to .env File

```bash
# Add to .env
SLACK_SIGNING_SECRET=your_signing_secret_here
```

#### 3.3 Create Slash Commands in Slack

1. In your Slack app settings, go to "Slash Commands"
2. Click "Create New Command"

**Command 1: /cex-report**
- Command: `/cex-report`
- Request URL: `https://your-ngrok-url.ngrok.io/slack/commands`
- Short Description: `Generate position report`
- Usage Hint: `[optional: october, 2025-10]`

**Command 2: /cex-buysell**
- Command: `/cex-buysell`
- Request URL: `https://your-ngrok-url.ngrok.io/slack/commands`
- Short Description: `Buy/sell analysis`
- Usage Hint: `[month, e.g., october or 2025-10]`

**Command 3: /cex-help**
- Command: `/cex-help`
- Request URL: `https://your-ngrok-url.ngrok.io/slack/commands`
- Short Description: `Show help for CEX Reporter commands`

#### 3.4 Reinstall App to Workspace

After adding commands, you'll need to reinstall the app:
1. Go to "Install App"
2. Click "Reinstall to Workspace"
3. Approve permissions

---

### Phase 4: Test Locally with ngrok (15 minutes)

#### 4.1 Install ngrok

```bash
# macOS
brew install ngrok

# Or download from: https://ngrok.com/download
```

#### 4.2 Start Server

```bash
# Terminal 1: Start FastAPI server
cd /Users/ben/Desktop/cex-reporter
source venv/bin/activate
python -m src.slack_server.server
```

#### 4.3 Start ngrok Tunnel

```bash
# Terminal 2: Start ngrok
ngrok http 8000
```

Copy the `https://` forwarding URL (e.g., `https://abc123.ngrok.io`)

#### 4.4 Update Slack Commands

Go back to Slack App settings and update all command URLs to use your ngrok URL:
- `https://abc123.ngrok.io/slack/commands`

#### 4.5 Test Commands

In your Slack channel:
```
/cex-help
/cex-report
/cex-buysell october
```

---

### Phase 5: Production Deployment (45 minutes)

#### Option A: Railway (Easiest)

1. **Create Railway Account**
   - Go to https://railway.app
   - Sign up with GitHub

2. **Create New Project**
   - Click "New Project"
   - Select "Deploy from GitHub repo"
   - Connect your repo

3. **Add Environment Variables**
   ```
   SLACK_WEBHOOK_URL=...
   SLACK_SIGNING_SECRET=...
   MEXC_MM2_API_KEY=...
   (etc - all your .env variables)
   ```

4. **Create Procfile**
   ```bash
   # Procfile
   web: uvicorn src.slack_server.server:app --host 0.0.0.0 --port $PORT
   ```

5. **Deploy**
   - Railway auto-deploys on push to main
   - Copy the generated URL

6. **Update Slack App**
   - Update all command URLs to Railway URL

#### Option B: Render

Similar process to Railway:
1. Create account at https://render.com
2. Create new Web Service
3. Connect GitHub repo
4. Add environment variables
5. Deploy

#### Option C: DigitalOcean App Platform

1. Create account
2. Deploy from GitHub
3. Configure environment
4. Much more control, slightly more complex

---

### Phase 6: Add Features (Optional)

#### 6.1 Command Parameters

Add support for:
```
/cex-report october      - Report for specific month
/cex-report last-7-days  - Last 7 days
/cex-trades 2025-11-01 2025-11-05  - Custom date range
```

#### 6.2 Interactive Buttons

Add buttons to reports:
```python
"blocks": [
    {
        "type": "actions",
        "elements": [
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Buy/Sell Analysis"},
                "action_id": "buysell_analysis"
            }
        ]
    }
]
```

#### 6.3 Status Updates

Send progress updates:
```python
# Send initial message
response = await slack_client.send_message({"text": "🔄 Starting report..."})

# Update message
await slack_client.update_message(
    response['ts'],
    {"text": "✅ Report complete!"}
)
```

---

## Troubleshooting

### Issue: "dispatch_failed" error

**Solution:** Check that:
- Server is running
- ngrok tunnel is active
- Slack command URL matches ngrok URL
- Signing secret is correct

### Issue: Timeout errors

**Solution:**
- Implement background job queue (see Phase 7)
- Return immediate response
- Send final report when ready

### Issue: Signature verification fails

**Solution:**
- Verify SLACK_SIGNING_SECRET in .env
- Check that you're using raw request body
- Ensure timestamp is recent

---

## Next Steps

1. ✅ Review design document
2. ⬜ Install dependencies
3. ⬜ Create server files
4. ⬜ Configure Slack app
5. ⬜ Test with ngrok
6. ⬜ Deploy to production
7. ⬜ Monitor and iterate

---

## Estimated Timeline

- **Setup & Development:** 2-3 hours
- **Testing:** 30 minutes
- **Deployment:** 45 minutes
- **Documentation:** 30 minutes

**Total: 4-5 hours**

---

## Cost Summary

- **Development:** Free (local testing)
- **ngrok:** Free (temporary testing) or $8/month (permanent URL)
- **Railway:** Free tier available, $5/month for production
- **Render:** Free tier available
- **Total Recurring Cost:** $0-13/month
