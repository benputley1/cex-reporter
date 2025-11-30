# ALKIMI Slack Bot - Quick Reference

## Architecture at a Glance

```
User → Slack → Socket Mode → AlkimiBot → Modules → Data Layer
```

## Key Files

| File | Purpose | Lines |
|------|---------|-------|
| `bot_main.py` | Entry point | 135 |
| `src/bot/slack_bot.py` | Main coordinator | 668 |
| `src/bot/formatters.py` | Slack formatting | 530 |
| `src/bot/data_provider.py` | Data access | 650 |
| `src/bot/query_router.py` | Intent routing | 520 |
| `src/bot/query_engine.py` | SQL execution | 580 |
| `src/bot/python_executor.py` | Python sandbox | 380 |
| `src/bot/function_store.py` | Function mgmt | 350 |
| `src/bot/pnl_config.py` | P&L calc | 1050 |
| `src/bot/prompts.py` | Claude LLM | 550 |

## Command Quick Reference

### Natural Language (any channel with @mention or DM)
```
@alkimi-bot What's our P&L this month?
@alkimi-bot Show trades over $5K yesterday
@alkimi-bot Current ALKIMI balance
```

### Slash Commands
```bash
/alkimi help                           # Show help
/alkimi pnl                            # P&L report
/alkimi sql SELECT * FROM trades       # SQL query
/alkimi run whale_detector             # Run function
/alkimi functions                      # List functions
/alkimi create find trades over $10K   # Create function
/alkimi history                        # Query history
/alkimi config                         # Show config
/alkimi config cost-basis FIFO         # Set config
/alkimi otc list                       # List OTC
/alkimi otc remove 1                   # Remove OTC
```

## Environment Variables

```bash
# Required
SLACK_BOT_TOKEN=xoxb-...              # Bot User OAuth Token
SLACK_APP_TOKEN=xapp-...              # App-Level Token
SLACK_SIGNING_SECRET=...              # Signing Secret
ANTHROPIC_API_KEY=sk-ant-...          # Claude API Key

# Optional
DB_PATH=data/trade_cache.db           # SQLite database
SNAPSHOTS_DIR=data/snapshots          # Snapshot directory
```

## Query Intents

| Intent | Example | Handler |
|--------|---------|---------|
| `PNL_QUERY` | "What's our P&L?" | `_handle_pnl_query()` |
| `TRADE_QUERY` | "Show trades over $5K" | `_handle_trade_query()` |
| `BALANCE_QUERY` | "Current balance?" | `_handle_balance_query()` |
| `PRICE_QUERY` | "ALKIMI price?" | `_handle_price_query()` |
| `SQL_QUERY` | "SELECT * FROM trades" | `_handle_sql()` |
| `PYTHON_FUNCTION` | "Create function..." | `_handle_create_function()` |
| `RUN_FUNCTION` | "Run whale_detector" | `_handle_run_function()` |
| `ANALYTICS_QUERY` | "Best performing venue?" | `_handle_analytics_query()` |

## Common Code Patterns

### Adding a New Command Handler

```python
async def _handle_new_command(self, args: str, user: str, say):
    """Handle new command."""
    logger.info(f"New command from {user}: {args}")

    try:
        # Process command
        result = await self.some_module.do_something(args)

        # Format response
        await say(blocks=self.formatter.format_something(result))

        # Log success
        await self.data_provider.save_query_history(
            user_id=user,
            query_text=args,
            query_type="new_command",
            success=True
        )

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        await say(blocks=self.formatter.format_error(
            str(e),
            "Helpful suggestion"
        ))
```

### Adding a New Formatter

```python
def format_new_thing(self, data: Dict) -> List[Dict]:
    """Format new thing for Slack."""
    blocks = []

    # Header
    blocks.append({
        "type": "header",
        "text": {
            "type": "plain_text",
            "text": "📊 Title",
            "emoji": True
        }
    })

    # Content
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn",
            "text": f"*Bold* and _italic_ with {data['value']}"
        }
    })

    return blocks
```

### Adding a New Intent

```python
# 1. Add to QueryIntent enum (query_router.py)
class QueryIntent(Enum):
    NEW_INTENT = "new_intent"

# 2. Add classification logic (query_router.py)
def classify(self, query: str) -> QueryIntent:
    if "new keyword" in query_lower:
        return QueryIntent.NEW_INTENT

# 3. Add to router (slack_bot.py)
async def _route_query(self, intent, params, user, say):
    if intent == QueryIntent.NEW_INTENT:
        await self._handle_new_intent(params, user, say)
```

## Slack Block Kit Basics

### Simple Text
```python
{
    "type": "section",
    "text": {
        "type": "mrkdwn",
        "text": "*Bold* _italic_ `code`"
    }
}
```

### Header
```python
{
    "type": "header",
    "text": {
        "type": "plain_text",
        "text": "Header Text",
        "emoji": True
    }
}
```

### Fields (2-column layout)
```python
{
    "type": "section",
    "fields": [
        {"type": "mrkdwn", "text": "*Left:*\nValue"},
        {"type": "mrkdwn", "text": "*Right:*\nValue"}
    ]
}
```

### Divider
```python
{"type": "divider"}
```

### Context (small text)
```python
{
    "type": "context",
    "elements": [
        {"type": "mrkdwn", "text": "Small contextual text"}
    ]
}
```

## Debugging

### Check Logs
```bash
# Bot logs to console
python3 bot_main.py

# Or redirect to file
python3 bot_main.py > bot.log 2>&1
```

### Test Components Individually
```python
# Test router
from src.bot.query_router import QueryRouter
router = QueryRouter()
intent = router.classify("What's our P&L?")
print(intent)

# Test formatter
from src.bot.formatters import SlackFormatter
formatter = SlackFormatter()
blocks = formatter.format_help()
print(blocks)

# Test data provider
from src.bot.data_provider import DataProvider
import asyncio
dp = DataProvider()
asyncio.run(dp.get_trades_df())
```

### Common Issues

| Issue | Solution |
|-------|----------|
| "Module not found" | `pip install -r requirements-bot.txt` |
| "No Slack tokens" | Set environment variables in `.env` |
| "Database not found" | Check `DB_PATH` points to valid SQLite file |
| "Bot not responding" | Check bot is running and tokens are valid |
| "Import errors" | Run from project root, check `PYTHONPATH` |

## Performance Tips

1. **Async everywhere** - All I/O operations are async
2. **Result truncation** - Limit table rows to 10 by default
3. **Connection pooling** - Reuse database connections
4. **Cache responses** - Cache frequently asked queries
5. **Batch operations** - Group multiple data fetches

## Security Checklist

- [x] Python execution sandboxed
- [x] SQL queries read-only
- [x] AST-based code validation
- [x] No file system access
- [x] No network access in Python
- [x] Input validation
- [x] User authentication via Slack
- [x] All operations logged

## File Structure

```
cex-reporter/
├── bot_main.py                    # Entry point
├── requirements-bot.txt           # Bot dependencies
├── .env                          # Environment variables (create this)
├── src/
│   └── bot/
│       ├── __init__.py
│       ├── slack_bot.py          # Main coordinator
│       ├── formatters.py         # Slack formatting
│       ├── data_provider.py      # Data access
│       ├── query_router.py       # Intent routing
│       ├── query_engine.py       # SQL execution
│       ├── python_executor.py    # Python sandbox
│       ├── function_store.py     # Function mgmt
│       ├── pnl_config.py         # P&L calc
│       └── prompts.py            # Claude LLM
├── data/
│   ├── trade_cache.db           # SQLite database
│   ├── snapshots/               # JSON snapshots
│   └── functions/               # Saved functions
└── docs/
    ├── SLACK_BOT_SETUP.md       # Setup guide
    ├── BOT_INTEGRATION_SUMMARY.md
    ├── BOT_ARCHITECTURE.txt
    └── BOT_QUICK_REFERENCE.md   # This file
```

## Testing Checklist

Before deploying:
- [ ] Install dependencies
- [ ] Set environment variables
- [ ] Configure Slack app
- [ ] Test database access
- [ ] Test Claude API
- [ ] Test each command
- [ ] Test error handling
- [ ] Review logs

## Quick Start (5 minutes)

```bash
# 1. Install
pip install -r requirements.txt -r requirements-bot.txt

# 2. Configure
cat > .env << EOF
SLACK_BOT_TOKEN=xoxb-your-token
SLACK_APP_TOKEN=xapp-your-token
SLACK_SIGNING_SECRET=your-secret
ANTHROPIC_API_KEY=sk-ant-your-key
EOF

# 3. Run
python3 bot_main.py

# 4. Test in Slack
# DM the bot: "What's our P&L this month?"
```

## Support

- **Setup Issues**: See `docs/SLACK_BOT_SETUP.md`
- **Architecture**: See `docs/BOT_ARCHITECTURE.txt`
- **Integration**: See `docs/BOT_INTEGRATION_SUMMARY.md`
- **This File**: Quick reference for developers

## Resources

- Slack Block Kit Builder: https://app.slack.com/block-kit-builder
- Slack API Docs: https://api.slack.com/docs
- Anthropic Docs: https://docs.anthropic.com
- Project Repository: (your repo URL)
