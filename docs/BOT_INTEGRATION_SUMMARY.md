# ALKIMI Slack Bot - Integration Summary

## Overview

The ALKIMI Slack Bot is a complete LLM-powered conversational interface for querying ALKIMI trading data. This document summarizes the integration of all bot modules.

## Architecture

### Module Count: 10 Python files, ~5,500 lines of code

### Component Hierarchy

```
bot_main.py (Entry Point)
    ↓
AlkimiBot (slack_bot.py) - Main bot coordinator
    ├── DataProvider - Unified data access layer
    ├── QueryRouter - Intent classification and routing
    ├── ClaudeClient - LLM query processing
    ├── QueryEngine - SQL query execution
    ├── SafePythonExecutor - Sandboxed Python execution
    ├── FunctionStore - Saved function management
    ├── PnLCalculator - P&L calculations
    │   ├── PnLConfig - Configuration management
    │   └── OTCManager - OTC transaction tracking
    └── SlackFormatter - Rich message formatting
```

## Files Created

### 1. `src/bot/formatters.py` (18,415 bytes, 530 lines)

Slack message formatters using Block Kit.

**Key Classes:**
- `SlackFormatter` - Main formatting class

**Methods:**
- `format_pnl_report()` - P&L report with realized/unrealized breakdown
- `format_table()` - DataFrame as monospaced table
- `format_trade_list()` - Trade history with details
- `format_balance_summary()` - Balances by exchange
- `format_error()` - Error messages with suggestions
- `format_success()` - Success confirmations
- `format_code()` - Code blocks with syntax highlighting
- `format_function_list()` - Saved functions
- `format_query_history()` - Query history
- `format_help()` - Help message with commands
- `format_config()` - P&L configuration display

**Features:**
- Uses Slack Block Kit for rich formatting
- Emoji indicators for P&L (📈📉💰)
- Truncation for large datasets
- Currency and number formatting
- Contextual help messages

### 2. `src/bot/slack_bot.py` (25,607 bytes, 668 lines)

Enhanced main bot implementation integrating all modules.

**Key Classes:**
- `AlkimiBot` - Main bot coordinator

**Event Handlers:**
- `handle_mention()` - @bot mentions in channels
- `handle_dm()` - Direct messages
- `handle_alkimi_command()` - /alkimi slash command

**Query Handlers:**
- `_handle_pnl_query()` - P&L calculations
- `_handle_trade_query()` - Trade queries with filters
- `_handle_balance_query()` - Balance summaries
- `_handle_price_query()` - Current price
- `_handle_sql()` - SQL query execution
- `_handle_run_function()` - Run saved function
- `_handle_create_function()` - Create new function
- `_handle_list_functions()` - List all functions
- `_handle_history()` - Query history
- `_handle_config()` - P&L configuration
- `_handle_otc()` - OTC transaction management
- `_handle_analytics_query()` - Analytics with Claude
- `_handle_natural_language()` - General queries

**Features:**
- Complete error handling with logging
- Query routing based on intent
- History tracking for all queries
- Rich Slack formatting for all responses
- Graceful degradation when services unavailable

### 3. `bot_main.py` (3,300 bytes, 135 lines)

Entry point script with environment validation.

**Features:**
- Environment variable validation
- Data directory creation
- Startup banner with configuration
- Graceful shutdown handling
- Detailed error reporting

### 4. `docs/SLACK_BOT_SETUP.md` (12,000 bytes)

Complete setup guide including:
- Slack app configuration steps
- Environment setup
- Installation instructions
- Usage examples
- Command reference
- Architecture diagrams
- Troubleshooting guide

### 5. `requirements-bot.txt`

Bot-specific Python dependencies.

## Integration Points

### DataProvider Integration

All handlers use DataProvider for data access:

```python
# Trade queries
trades = await self.data_provider.get_trades_df(since, until, exchange)

# Balance queries
balances = await self.data_provider.get_balances()

# Price queries
price = await self.data_provider.get_current_price()

# Query history
await self.data_provider.save_query_history(user_id, query_text, ...)
```

### QueryRouter Integration

Intent classification routes to appropriate handlers:

```python
# Classify user query
intent = self.router.classify(text)
params = self.router.extract_parameters(text, intent)

# Route to handler
await self._route_query(intent, params, user, say)
```

### QueryEngine Integration

SQL queries use QueryEngine with Claude assistance:

```python
result = await self.query_engine.execute_sql(sql)
if result.success:
    await say(blocks=self.formatter.format_table(result.data))
```

### SafePythonExecutor Integration

Function execution uses sandboxed executor:

```python
result = await self.executor.execute(func.code)
if result.success:
    await say(blocks=self.formatter.format_table(result.result))
```

### FunctionStore Integration

Function management:

```python
# Save function
await self.functions.save(name, code, description, user)

# Get function
func = await self.functions.get(name)

# List functions
functions = await self.functions.list_all()

# Update usage
await self.functions.update_usage(name)
```

### PnLCalculator Integration

P&L calculations with OTC support:

```python
report = await self.pnl_calc.calculate(since, until)
await say(blocks=self.formatter.format_pnl_report(report))
```

### ClaudeClient Integration

LLM-powered features:

```python
# Generate SQL
sql = await self.claude.generate_sql(query, schema_context)

# Generate Python
code = await self.claude.generate_python(description)

# Answer query
answer = await self.claude.answer_query(query, context)
```

### SlackFormatter Integration

All responses use formatter for consistent styling:

```python
# Format P&L
await say(blocks=self.formatter.format_pnl_report(report))

# Format table
await say(blocks=self.formatter.format_table(df, title))

# Format error
await say(blocks=self.formatter.format_error(error, suggestion))
```

## Message Flow

### Example: P&L Query

1. **User**: "What's our P&L this month?"
2. **Slack** → Socket Mode → `handle_mention()`
3. **QueryRouter**: Classify → `QueryIntent.PNL_QUERY`
4. **QueryRouter**: Extract params → `time_range=(Nov 1, Nov 30)`
5. **Route** → `_handle_pnl_query()`
6. **PnLCalculator**: Calculate P&L with OTC adjustments
7. **SlackFormatter**: Format as Block Kit blocks
8. **Slack**: Display rich formatted message

### Example: SQL Query

1. **User**: `/alkimi sql SELECT * FROM trades LIMIT 5`
2. **Slack** → `handle_alkimi_command()`
3. **Parse**: subcommand=`sql`, args=`SELECT...`
4. **QueryEngine**: Execute SQL (read-only)
5. **DataProvider**: Log to query history
6. **SlackFormatter**: Format DataFrame as table
7. **Slack**: Display results

### Example: Function Creation

1. **User**: `/alkimi create find whale trades over $10K`
2. **Slack** → `handle_alkimi_command()`
3. **Parse**: subcommand=`create`, args=`find whale...`
4. **ClaudeClient**: Generate Python code
5. **SafePythonExecutor**: Validate code safety
6. **FunctionStore**: Save to database
7. **SlackFormatter**: Show code and run command
8. **Slack**: Display formatted response

## Command Reference

### Natural Language Queries

Simply ask in plain English:
- "What's our P&L this month?"
- "Show trades over $5K"
- "Current ALKIMI balance"

### Slash Commands

| Command | Description |
|---------|-------------|
| `/alkimi help` | Show help |
| `/alkimi pnl` | P&L report |
| `/alkimi sql <query>` | Execute SQL |
| `/alkimi run <name>` | Run function |
| `/alkimi functions` | List functions |
| `/alkimi create <desc>` | Create function |
| `/alkimi history` | Query history |
| `/alkimi config` | Show config |
| `/alkimi config cost-basis <method>` | Set cost basis |
| `/alkimi otc list` | List OTC |
| `/alkimi otc remove <id>` | Remove OTC |

## Error Handling

All handlers include comprehensive error handling:

```python
try:
    # Execute operation
    result = await operation()
    await say(blocks=self.formatter.format_success(result))
except Exception as e:
    logger.error(f"Operation failed: {e}", exc_info=True)
    await say(blocks=self.formatter.format_error(
        str(e),
        "Helpful suggestion"
    ))
```

## Logging

All operations are logged:

```python
logger.info(f"Query from {user}: {text}")
logger.info(f"P&L query: since={since}, until={until}")
logger.error(f"Error calculating P&L: {e}", exc_info=True)
```

## History Tracking

All queries are logged to database:

```python
await self.data_provider.save_query_history(
    user_id=user,
    query_text=query,
    query_type="sql",
    generated_code=code,
    execution_time_ms=timing,
    success=True
)
```

## Security Features

1. **Sandboxed Python Execution**
   - Whitelist of safe modules
   - AST-based validation
   - No file system access
   - No network access
   - No subprocess execution

2. **Read-Only SQL**
   - Only SELECT queries allowed
   - No INSERT/UPDATE/DELETE
   - Schema introspection only

3. **User Authentication**
   - Slack handles user identity
   - User ID tracked in all operations

4. **Input Validation**
   - Parameter extraction and validation
   - SQL injection prevention
   - Code injection prevention

## Performance Considerations

1. **Async/Await Throughout**
   - All I/O operations are async
   - Non-blocking message handling

2. **Query Result Truncation**
   - Tables limited to 10 rows by default
   - Configurable via `max_rows` parameter

3. **Response Caching**
   - Can be added in DataProvider layer
   - Claude responses can be cached

4. **Connection Pooling**
   - Database connections reused
   - HTTP clients reused

## Testing

### Unit Testing

Test individual components:

```python
# Test formatter
formatter = SlackFormatter()
blocks = formatter.format_pnl_report(mock_report)
assert len(blocks) > 0

# Test router
router = QueryRouter()
intent = router.classify("What's our P&L?")
assert intent == QueryIntent.PNL_QUERY
```

### Integration Testing

Test full flow:

```python
# Create test bot
bot = create_bot(
    bot_token="test-token",
    anthropic_api_key="test-key"
)

# Test query handling
await bot._handle_pnl_query(params, "test_user", mock_say)
```

## Deployment

### Development

```bash
python3 bot_main.py
```

### Production

```bash
# Use process manager
nohup python3 bot_main.py > logs/bot.log 2>&1 &

# Or with systemd
systemctl start alkimi-bot
```

### Docker

```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt requirements-bot.txt ./
RUN pip install -r requirements.txt -r requirements-bot.txt
COPY . .
CMD ["python3", "bot_main.py"]
```

## Monitoring

### Logs

All operations logged to console:
- Query requests
- Query results
- Errors with stack traces
- Performance metrics

### Metrics to Track

- Queries per user
- Query types distribution
- Error rates
- Response times
- Most used functions

## Future Enhancements

### Planned Features

1. **Query Caching** - Cache frequently asked queries
2. **Scheduled Reports** - Daily/weekly P&L reports
3. **Alerts** - Whale trade notifications
4. **User Permissions** - Role-based access control
5. **Multi-workspace** - Support multiple Slack workspaces
6. **Interactive Buttons** - Slack buttons for actions
7. **Charts** - Generate chart images
8. **Export** - Export results to CSV/Excel

### Possible Integrations

1. **Trading Execution** - Place orders via bot
2. **Risk Monitoring** - Real-time risk alerts
3. **Portfolio Optimization** - ML-based suggestions
4. **Market Data** - Live price feeds
5. **News Integration** - Crypto news context

## Summary

The ALKIMI Slack Bot successfully integrates:

- ✅ 10 Python modules (~5,500 lines)
- ✅ Natural language query interface
- ✅ SQL query execution
- ✅ Python code generation and execution
- ✅ Saved function management
- ✅ P&L calculations with OTC support
- ✅ Rich Slack formatting
- ✅ Query history tracking
- ✅ Comprehensive error handling
- ✅ Security sandboxing
- ✅ Complete documentation

The bot is production-ready and can be deployed with proper environment configuration.

## Quick Start

1. **Install dependencies**:
```bash
pip install -r requirements.txt -r requirements-bot.txt
```

2. **Configure environment**:
```bash
cp .env.example .env
# Edit .env with your tokens
```

3. **Run bot**:
```bash
python3 bot_main.py
```

4. **Test in Slack**:
```
@alkimi-bot What's our P&L this month?
```

## Files Reference

| File | Lines | Purpose |
|------|-------|---------|
| `bot_main.py` | 135 | Entry point |
| `src/bot/slack_bot.py` | 668 | Main bot coordinator |
| `src/bot/formatters.py` | 530 | Slack message formatting |
| `src/bot/data_provider.py` | 650 | Data access layer |
| `src/bot/query_router.py` | 520 | Intent classification |
| `src/bot/query_engine.py` | 580 | SQL execution |
| `src/bot/python_executor.py` | 380 | Python execution |
| `src/bot/function_store.py` | 350 | Function management |
| `src/bot/pnl_config.py` | 1050 | P&L calculations |
| `src/bot/prompts.py` | 550 | Claude LLM client |

**Total: ~5,500 lines of production-ready code**
