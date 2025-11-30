# Slack Commands for Manual Report Triggering

## Problem Statement

Currently, the CEX Reporter only sends automated reports via incoming webhooks. We need the ability to trigger reports manually on-demand via Slack commands.

## Solution Options

### Option 1: Slash Commands with Web Server ⭐ RECOMMENDED

**How it works:**
- User types `/cex-report` or `/cex-buysell october` in Slack
- Slack sends HTTP POST to your server endpoint
- Server processes command and generates report
- Report sent back to Slack channel

**Requirements:**
- Web server with public endpoint (Flask/FastAPI)
- Slack App configuration with slash commands
- Request verification from Slack
- Background job processing for long-running reports

**Pros:**
- Native Slack experience
- Multiple commands possible (`/cex-report`, `/cex-buysell`, etc.)
- Can pass parameters (e.g., time ranges, specific accounts)
- Industry standard approach

**Cons:**
- Requires public endpoint (can use ngrok for testing, need production hosting)
- More complex setup than webhooks
- Need to handle Slack's 3-second response timeout

**Commands to Implement:**
```
/cex-report               - Full position report (same as scheduled)
/cex-report-october       - Position report for October
/cex-buysell              - Buy/sell split for last 14 days
/cex-buysell october      - Buy/sell split for October
/cex-buysell [YYYY-MM]    - Buy/sell split for any month
/cex-trades [date-range]  - Pull trades for specific date range
```

---

### Option 2: Interactive Buttons/Menus

**How it works:**
- Bot sends a "control panel" message with buttons
- User clicks button to trigger report
- Server receives interaction payload
- Report generated and sent

**Requirements:**
- Similar to Option 1 (web server, public endpoint)
- Interactive components configuration in Slack app
- Request verification

**Pros:**
- Visual interface
- No need to remember command syntax
- Can group related commands

**Cons:**
- Still requires public endpoint
- Less flexible than slash commands
- Takes up space in channel with control panel message

---

### Option 3: Bot Mentions with Event Subscriptions

**How it works:**
- User mentions bot: `@CEX-Reporter run october report`
- Bot receives event via webhook
- Parses message and generates report

**Requirements:**
- Bot user in Slack app
- Event subscriptions configured
- Public endpoint for events
- Message parsing logic

**Pros:**
- Natural language feel
- Can implement simple AI/parsing for flexibility

**Cons:**
- Most complex to implement
- Requires event subscriptions (more Slack permissions)
- Message parsing can be error-prone

---

### Option 4: Email-to-Slack Bridge (Alternative)

**How it works:**
- Send email with command to special address
- Email service parses and triggers report
- Report sent to Slack

**Pros:**
- No public endpoint needed
- Can use services like Zapier/Make

**Cons:**
- Not a native Slack experience
- Requires third-party service
- Additional cost

---

## Recommended Implementation: Option 1 (Slash Commands)

### Architecture

```
┌─────────────┐
│   Slack     │
│   Channel   │
└──────┬──────┘
       │ User types: /cex-report
       ↓
┌─────────────────┐
│  Slack API      │
│  (Slash Cmd)    │
└──────┬──────────┘
       │ HTTP POST to endpoint
       ↓
┌──────────────────────────────┐
│  Your Server                 │
│  (Flask/FastAPI)             │
│  ├─ Verify Slack signature   │
│  ├─ Parse command            │
│  ├─ Queue background job     │
│  └─ Return immediate ACK     │
└──────┬───────────────────────┘
       │
       ↓
┌──────────────────────────────┐
│  Background Worker           │
│  ├─ Initialize exchanges     │
│  ├─ Fetch data               │
│  ├─ Generate report          │
│  └─ Send to Slack webhook    │
└──────────────────────────────┘
```

### Technical Components

#### 1. Web Server (FastAPI)
- Endpoint: `POST /slack/commands`
- Handles slash command requests
- Verifies Slack signature
- Queues background jobs
- Returns immediate acknowledgment

#### 2. Background Job Queue (Python RQ or Celery)
- Prevents timeout issues
- Runs report generation asynchronously
- Can handle multiple simultaneous requests

#### 3. Command Router
- Parses slash command and parameters
- Routes to appropriate report generator
- Validates parameters

#### 4. Report Generators
- Reuse existing position_tracker and analytics
- Format for Slack
- Send via existing webhook

### Security Considerations

1. **Slack Signature Verification**
   - Verify all requests come from Slack
   - Use signing secret to validate

2. **Rate Limiting**
   - Prevent abuse of report commands
   - Limit to X requests per user per hour

3. **Authentication**
   - Only workspace members can trigger
   - Optional: Restrict to specific users/channels

### Deployment Options

#### Development/Testing:
- **ngrok**: Tunnel localhost to public URL
  - Free tier available
  - Perfect for testing

#### Production:
- **Railway/Render/Fly.io**: Simple deployment
  - Free/cheap tiers available
  - Easy to setup

- **AWS Lambda + API Gateway**: Serverless
  - Pay per use
  - Auto-scaling

- **Your own VPS**: Full control
  - DigitalOcean, Linode, etc.
  - Need to manage yourself

### Development Phases

**Phase 1: Basic Setup** (1-2 hours)
- Create Flask/FastAPI server
- Implement `/cex-report` command
- Test with ngrok locally

**Phase 2: Command Expansion** (1-2 hours)
- Add `/cex-buysell` command
- Add parameter parsing for dates
- Implement command help

**Phase 3: Background Processing** (2-3 hours)
- Add job queue (Python RQ)
- Handle long-running reports
- Implement status updates

**Phase 4: Production Deploy** (1-2 hours)
- Choose hosting platform
- Deploy server
- Configure Slack app with production URL

**Total Estimate: 5-9 hours**

### Cost Estimate

- **Slack**: Free (slash commands included)
- **Hosting**:
  - Railway/Render: $5-10/month (free tier possible)
  - AWS Lambda: ~$0-5/month (likely free tier)
  - ngrok: Free for dev, $8/month for production
- **Total: $0-15/month**

---

## Alternative Quick Solution: Scheduled Commands

If you need something simpler while the full solution is being built:

**Manual Trigger via Git Commit**
1. Create a GitHub repo
2. GitHub Actions workflow watches for commits
3. Commit file with command name triggers report
4. No server needed, uses GitHub's infrastructure

**Example workflow:**
```yaml
# .github/workflows/manual-report.yml
on:
  repository_dispatch:
    types: [run-report]

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - run: python main.py --mode once
```

Trigger via:
```bash
gh workflow run manual-report.yml
```

---

## Implementation Recommendation

**Start with:** Option 1 (Slash Commands) with ngrok for development

**Reason:**
- Most flexible and user-friendly
- Industry standard
- Scales to more complex use cases
- Can start simple and add features incrementally

**Quick Start Path:**
1. Deploy basic Flask server with `/cex-report` only
2. Test locally with ngrok
3. Expand to other commands
4. Move to production hosting when stable
