# ALKIMI Slack Bot Setup Guide

## Overview

The ALKIMI Slack Bot provides a natural language interface to query your ALKIMI trading data. It integrates all the bot modules we've built:

- **DataProvider** - Unified data access to trades, balances, prices
- **QueryRouter** - Intent classification for routing queries
- **QueryEngine** - SQL query execution with LLM assistance
- **SafePythonExecutor** - Sandboxed Python code execution
- **FunctionStore** - Save and reuse Python functions
- **PnLCalculator** - P&L reporting with OTC support
- **ClaudeClient** - LLM-powered query responses
- **SlackFormatter** - Rich Slack Block Kit messages

## Prerequisites

1. **Slack Workspace** - Admin access to create apps
2. **Python 3.9+** - With required packages installed
3. **Anthropic API Key** - For Claude LLM features
4. **Trade Data** - SQLite database with trades

## Slack App Setup

### Step 1: Create Slack App

1. Go to https://api.slack.com/apps
2. Click "Create New App"
3. Choose "From scratch"
4. Name: "ALKIMI Bot"
5. Select your workspace

### Step 2: Enable Socket Mode

1. Navigate to **Settings > Socket Mode**
2. Toggle "Enable Socket Mode" to ON
3. Give it a name: "Socket Mode Token"
4. Copy the **App-Level Token** (starts with `xapp-`)
5. Save as `SLACK_APP_TOKEN`

### Step 3: Add Bot Scopes

1. Navigate to **OAuth & Permissions**
2. Under "Bot Token Scopes", add:
   - `app_mentions:read` - Read messages that mention the bot
   - `chat:write` - Send messages as the bot
   - `commands` - Add slash commands
   - `im:history` - View messages in DMs
   - `im:read` - View basic DM info
   - `im:write` - Start DMs with users

### Step 4: Create Slash Command

1. Navigate to **Slash Commands**
2. Click "Create New Command"
3. Command: `/alkimi`
4. Request URL: Not needed for Socket Mode (leave placeholder)
5. Short Description: "Query ALKIMI trading data"
6. Usage Hint: `pnl | sql <query> | run <function>`
7. Save

### Step 5: Enable Event Subscriptions

1. Navigate to **Event Subscriptions**
2. Toggle "Enable Events" to ON
3. Under "Subscribe to bot events", add:
   - `app_mention` - When bot is @mentioned
   - `message.im` - Direct messages to bot

### Step 6: Install App to Workspace

1. Navigate to **OAuth & Permissions**
2. Click "Install to Workspace"
3. Authorize the app
4. Copy the **Bot User OAuth Token** (starts with `xoxb-`)
5. Save as `SLACK_BOT_TOKEN`

### Step 7: Get Signing Secret

1. Navigate to **Basic Information**
2. Under "App Credentials", find "Signing Secret"
3. Click "Show"
4. Copy the secret
5. Save as `SLACK_SIGNING_SECRET`

## Environment Configuration

Create a `.env` file in the project root:

```bash
# Slack Configuration
SLACK_BOT_TOKEN=xoxb-your-bot-user-oauth-token
SLACK_APP_TOKEN=xapp-your-app-level-token
SLACK_SIGNING_SECRET=your-signing-secret

# Anthropic API Key
ANTHROPIC_API_KEY=sk-ant-your-api-key

# Database Paths (optional, defaults shown)
DB_PATH=data/trade_cache.db
SNAPSHOTS_DIR=data/snapshots
```

## Installation

1. **Install Python dependencies**:
```bash
pip install slack-bolt anthropic pandas
```

2. **Verify data files exist**:
```bash
ls -la data/
# Should show:
# - trade_cache.db (SQLite database)
# - snapshots/ (directory with JSON files)
```

3. **Test configuration**:
```bash
python3 -c "from dotenv import load_dotenv; import os; load_dotenv(); print('Bot token:', os.getenv('SLACK_BOT_TOKEN')[:20] + '...')"
```

## Running the Bot

Start the bot:

```bash
python3 bot_main.py
```

You should see:

```
============================================================
ALKIMI SLACK BOT
============================================================
Configuration:
  Database: data/trade_cache.db
  Snapshots: data/snapshots
  Bot Token: xoxb-123456789012-...
  Anthropic API: Configured
============================================================

Features enabled:
  ✓ Natural language queries
  ✓ SQL query execution
  ✓ Python code generation
  ✓ Saved functions
  ✓ P&L calculations
  ✓ Query history
  ✓ OTC transaction management
============================================================

Starting bot with Socket Mode...
Bot will be available in Slack once connected.
```

## Using the Bot

### Direct Message

Open a DM with the bot and type:
```
What's our P&L this month?
```

### Channel Mention

In any channel where the bot is invited:
```
@alkimi-bot Show trades over $5K yesterday
```

### Slash Commands

```
/alkimi help
/alkimi pnl
/alkimi sql SELECT * FROM trades LIMIT 10
/alkimi run whale_detector
/alkimi functions
/alkimi create find trades over $10K with price above average
/alkimi history
/alkimi config
/alkimi otc list
```

## Example Queries

### Natural Language

- "What's our P&L this month?"
- "Show trades over $5K"
- "Current ALKIMI balance"
- "Best performing exchange yesterday"
- "Arbitrage opportunities"
- "Price on MEXC vs Gate.io"

### SQL Queries

```
/alkimi sql SELECT exchange, COUNT(*), SUM(amount) FROM trades GROUP BY exchange
/alkimi sql SELECT * FROM trades WHERE amount * price > 5000 ORDER BY timestamp DESC LIMIT 10
```

### Function Creation

```
/alkimi create find all whale trades over $10K in the last 24 hours
```

This will:
1. Generate Python code using Claude
2. Validate the code for safety
3. Save the function
4. Return the generated code

### Running Functions

```
/alkimi run whale_detector
/alkimi functions  # List all saved functions
```

## Commands Reference

| Command | Description | Example |
|---------|-------------|---------|
| `/alkimi help` | Show help message | `/alkimi help` |
| `/alkimi pnl` | P&L report | `/alkimi pnl` |
| `/alkimi sql <query>` | Execute SQL query | `/alkimi sql SELECT * FROM trades LIMIT 5` |
| `/alkimi run <name>` | Run saved function | `/alkimi run whale_detector` |
| `/alkimi functions` | List saved functions | `/alkimi functions` |
| `/alkimi create <desc>` | Create new function | `/alkimi create detect unusual volume` |
| `/alkimi history` | Show query history | `/alkimi history` |
| `/alkimi config` | Show P&L config | `/alkimi config` |
| `/alkimi config cost-basis <method>` | Set cost basis method | `/alkimi config cost-basis FIFO` |
| `/alkimi otc list` | List OTC transactions | `/alkimi otc list` |
| `/alkimi otc remove <id>` | Remove OTC transaction | `/alkimi otc remove 1` |

## Architecture

```
bot_main.py
    ↓
AlkimiBot (slack_bot.py)
    ├── DataProvider (data_provider.py)
    │   ├── TradeCache
    │   ├── DailySnapshot
    │   ├── SuiTokenMonitor
    │   └── CoinGeckoClient
    │
    ├── QueryRouter (query_router.py)
    │   └── Intent Classification
    │
    ├── ClaudeClient (prompts.py)
    │   ├── SQL Generation
    │   ├── Python Generation
    │   └── Query Answering
    │
    ├── QueryEngine (query_engine.py)
    │   └── SQL Execution
    │
    ├── SafePythonExecutor (python_executor.py)
    │   └── Sandboxed Python Execution
    │
    ├── FunctionStore (function_store.py)
    │   └── SQLite Storage
    │
    ├── PnLCalculator (pnl_config.py)
    │   ├── PnLConfig
    │   ├── OTCManager
    │   └── Cost Basis Calculation
    │
    └── SlackFormatter (formatters.py)
        └── Block Kit Messages
```

## Message Flow

1. **User sends message** → Slack
2. **Slack forwards** → Socket Mode → AlkimiBot
3. **QueryRouter classifies intent** → Determines handler
4. **Handler executes**:
   - PNL: PnLCalculator → PnLReport
   - SQL: ClaudeClient → QueryEngine → DataFrame
   - Python: ClaudeClient → SafePythonExecutor → Result
   - Function: FunctionStore → SafePythonExecutor → Result
   - Natural Language: ClaudeClient → Answer
5. **SlackFormatter formats** → Slack Blocks
6. **Bot responds** → Slack

## Troubleshooting

### Bot not responding

1. Check bot is running: `ps aux | grep bot_main`
2. Check logs for errors
3. Verify tokens in `.env` are correct
4. Check Slack app is installed to workspace

### "Missing environment variables"

Ensure `.env` file exists and contains all required variables:
```bash
cat .env
```

### Import errors

Install missing packages:
```bash
pip install -r requirements.txt
```

### Database errors

Check database exists and has correct schema:
```bash
sqlite3 data/trade_cache.db ".schema"
```

### Claude API errors

1. Check API key is valid
2. Check quota/rate limits
3. Check network connectivity

## Security Notes

1. **Never commit `.env` file** - Contains sensitive tokens
2. **Python execution is sandboxed** - Restricted to safe operations
3. **SQL queries are read-only** - No INSERT/UPDATE/DELETE allowed
4. **User authentication** - Slack handles user identity
5. **Rate limiting** - Consider adding if needed

## Development

### Testing locally

```bash
# Start bot in development mode
python3 bot_main.py

# In another terminal, test components
python3 -c "
from src.bot.query_router import QueryRouter
router = QueryRouter()
print(router.classify('What is our P&L?'))
"
```

### Adding new commands

1. Add handler method to `AlkimiBot` class
2. Register in `_handle_slash_command`
3. Add formatter method in `SlackFormatter`
4. Update help text

### Extending formatters

Edit `src/bot/formatters.py` to add new Block Kit layouts.

See: https://api.slack.com/block-kit/building

## Support

For issues or questions:
1. Check logs: `tail -f logs/bot.log`
2. Review error messages in Slack
3. Test individual components separately

## Next Steps

- Add more saved functions
- Implement OTC add functionality
- Add query caching
- Implement user permissions
- Add scheduled reports
- Add alerting for whale trades
- Integrate with trading execution
