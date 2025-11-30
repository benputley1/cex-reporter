# Python Executor Integration Guide

How to integrate the Python executor into the ALKIMI Slack bot.

## Prerequisites

Install required dependencies:

```bash
pip install pandas numpy aiosqlite
```

## 1. Initialize Components

Add to your bot initialization (e.g., `src/bot/bot.py`):

```python
from src.bot.python_executor import SafePythonExecutor
from src.bot.function_store import FunctionStore
from src.data.data_provider import DataProvider

# Initialize data provider
data_provider = DataProvider(
    db_path="data/trade_cache.db",
    exchanges=exchanges
)

# Initialize Python executor
python_executor = SafePythonExecutor(data_provider)

# Initialize function store
function_store = FunctionStore(db_path="data/trade_cache.db")
```

## 2. Add Slash Commands

### /analyze - Execute Python Code

Execute arbitrary Python code for analysis:

```python
@app.command("/analyze")
async def handle_analyze_command(ack, command, say, client):
    """Execute Python code for data analysis."""
    await ack()

    code = command['text'].strip()
    user_id = command['user_id']
    channel_id = command['channel_id']

    if not code:
        await say(
            text="Usage: `/analyze <python_code>`",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Usage:* `/analyze <python_code>`\n\n"
                                "*Example:*\n"
                                "```\n/analyze\n"
                                "df = load_trades(days=7)\n"
                                "result = df.groupby('exchange')['amount'].sum()\n```"
                    }
                }
            ]
        )
        return

    # Show "analyzing..." message
    response = await say(":hourglass_flowing_sand: Analyzing...")

    try:
        # Execute code
        result = await python_executor.execute(code)

        if result.success:
            # Format result
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": "Analysis Result"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"```\n{result.result}\n```"
                    }
                }
            ]

            # Add output if any
            if result.output:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Output:*\n```\n{result.output}\n```"
                    }
                })

            # Add execution time
            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f"Executed in {result.execution_time_ms}ms by <@{user_id}>"
                }]
            })

            # Update message
            await client.chat_update(
                channel=channel_id,
                ts=response['ts'],
                text=f"Analysis complete: {result.result}",
                blocks=blocks
            )

        else:
            # Show error
            await client.chat_update(
                channel=channel_id,
                ts=response['ts'],
                text=f"Analysis failed: {result.error}",
                blocks=[
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f":x: *Error*\n```\n{result.error}\n```"
                        }
                    }
                ]
            )

    except Exception as e:
        await client.chat_update(
            channel=channel_id,
            ts=response['ts'],
            text=f"Error: {str(e)}",
            blocks=[{
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f":x: *Unexpected Error*\n```\n{str(e)}\n```"
                }
            }]
        )
```

### /savefunc - Save Reusable Function

Save Python code as a named function:

```python
@app.command("/savefunc")
async def handle_savefunc_command(ack, command, say):
    """Save a Python function for reuse."""
    await ack()

    text = command['text'].strip()
    user_id = command['user_id']

    if not text:
        await say(
            text="Usage: `/savefunc name | description | code`",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": "*Usage:* `/savefunc name | description | code`\n\n"
                                "*Example:*\n"
                                "```\n/savefunc volume_by_exchange | "
                                "Calculate volume by exchange | "
                                "df = load_trades(); result = df.groupby('exchange')['amount'].sum()\n```"
                    }
                }
            ]
        )
        return

    # Parse input
    parts = text.split('|', 2)
    if len(parts) != 3:
        await say(":x: Invalid format. Use: `/savefunc name | description | code`")
        return

    name = parts[0].strip()
    description = parts[1].strip()
    code = parts[2].strip()

    # Validate name
    if not name.replace('_', '').isalnum():
        await say(":x: Function name must be alphanumeric (underscores allowed)")
        return

    # Validate code
    from src.bot.python_executor import CodeValidator
    validator = CodeValidator()
    is_valid, error = validator.validate(code)

    if not is_valid:
        await say(f":x: Code validation failed: {error}")
        return

    # Save function
    success = await function_store.save(
        name=name,
        code=code,
        description=description,
        created_by=user_id
    )

    if success:
        await say(
            text=f"Saved function: {name}",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":white_check_mark: *Saved Function*\n"
                                f"*Name:* `{name}`\n"
                                f"*Description:* {description}\n"
                                f"*Creator:* <@{user_id}>"
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Code:*\n```python\n{code}\n```"
                    }
                },
                {
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": f"Use `/runfunc {name}` to execute"
                    }]
                }
            ]
        )
    else:
        await say(":x: Failed to save function")
```

### /runfunc - Execute Saved Function

Execute a previously saved function:

```python
@app.command("/runfunc")
async def handle_runfunc_command(ack, command, say, client):
    """Execute a saved function."""
    await ack()

    func_name = command['text'].strip()
    user_id = command['user_id']
    channel_id = command['channel_id']

    if not func_name:
        # List available functions
        functions = await function_store.list_all()

        if not functions:
            await say("No saved functions. Use `/savefunc` to create one.")
            return

        func_list = "\n".join([
            f"• `{f.name}` - {f.description} (used {f.use_count}x)"
            for f in functions[:10]
        ])

        await say(
            text="Available functions",
            blocks=[
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Available Functions*\n{func_list}"
                    }
                },
                {
                    "type": "context",
                    "elements": [{
                        "type": "mrkdwn",
                        "text": "Use `/runfunc <name>` to execute"
                    }]
                }
            ]
        )
        return

    # Load function
    func = await function_store.get(func_name)

    if not func:
        await say(f":x: Function `{func_name}` not found. Use `/runfunc` to see available functions.")
        return

    # Show "executing..." message
    response = await say(f":hourglass_flowing_sand: Executing `{func_name}`...")

    try:
        # Execute
        result = await python_executor.execute(func.code)

        # Update usage stats
        await function_store.update_usage(func_name)

        if result.success:
            blocks = [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": func.name
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": func.description
                    }
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Result:*\n```\n{result.result}\n```"
                    }
                }
            ]

            if result.output:
                blocks.append({
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Output:*\n```\n{result.output}\n```"
                    }
                })

            blocks.append({
                "type": "context",
                "elements": [{
                    "type": "mrkdwn",
                    "text": f"Executed in {result.execution_time_ms}ms by <@{user_id}> • "
                            f"Created by <@{func.created_by}> • "
                            f"Used {func.use_count + 1}x"
                }]
            })

            await client.chat_update(
                channel=channel_id,
                ts=response['ts'],
                text=f"{func_name}: {result.result}",
                blocks=blocks
            )

        else:
            await client.chat_update(
                channel=channel_id,
                ts=response['ts'],
                text=f"Error: {result.error}",
                blocks=[{
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f":x: *Error*\n```\n{result.error}\n```"
                    }
                }]
            )

    except Exception as e:
        await client.chat_update(
            channel=channel_id,
            ts=response['ts'],
            text=f"Error: {str(e)}"
        )
```

### /listfuncs - List Saved Functions

```python
@app.command("/listfuncs")
async def handle_listfuncs_command(ack, command, say):
    """List all saved functions."""
    await ack()

    query = command['text'].strip()

    if query:
        # Search functions
        functions = await function_store.search(query)
        header = f"Functions matching '{query}'"
    else:
        # List all
        functions = await function_store.list_all()
        header = "All Saved Functions"

    if not functions:
        await say(f"No functions found." if query else "No saved functions.")
        return

    # Build function list
    func_blocks = []

    for func in functions[:20]:  # Limit to 20
        func_blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*`{func.name}`*\n{func.description}"
            },
            "accessory": {
                "type": "button",
                "text": {
                    "type": "plain_text",
                    "text": "Run"
                },
                "action_id": f"run_func_{func.name}",
                "value": func.name
            }
        })

        func_blocks.append({
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"Created by <@{func.created_by}> • Used {func.use_count}x"
            }]
        })

    # Get stats
    stats = await function_store.get_stats()

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": header
            }
        },
        *func_blocks,
        {
            "type": "divider"
        },
        {
            "type": "context",
            "elements": [{
                "type": "mrkdwn",
                "text": f"Total: {stats['total_functions']} functions • "
                        f"{stats['total_uses']} total executions"
            }]
        }
    ]

    await say(blocks=blocks)
```

### /delfunc - Delete Function

```python
@app.command("/delfunc")
async def handle_delfunc_command(ack, command, say):
    """Delete a saved function."""
    await ack()

    func_name = command['text'].strip()
    user_id = command['user_id']

    if not func_name:
        await say("Usage: `/delfunc <function_name>`")
        return

    # Check if function exists and user is creator
    func = await function_store.get(func_name)

    if not func:
        await say(f":x: Function `{func_name}` not found")
        return

    # Only allow creator to delete (or admins)
    if func.created_by != user_id:
        # Check if user is admin (implement your admin check)
        # is_admin = await check_admin(user_id)
        # if not is_admin:
        await say(f":x: Only the creator (<@{func.created_by}>) can delete this function")
        return

    # Delete
    success = await function_store.delete(func_name)

    if success:
        await say(f":white_check_mark: Deleted function `{func_name}`")
    else:
        await say(f":x: Failed to delete function `{func_name}`")
```

## 3. Add Interactive Button Handlers

Handle "Run" button clicks from function lists:

```python
@app.action("run_func_*")
async def handle_run_func_button(ack, action, say, client, body):
    """Handle Run button click on function list."""
    await ack()

    func_name = action['value']
    user_id = body['user']['id']
    channel_id = body['channel']['id']

    # Load and execute function (same as /runfunc)
    func = await function_store.get(func_name)

    if not func:
        await say(f":x: Function `{func_name}` not found")
        return

    response = await say(f":hourglass_flowing_sand: Executing `{func_name}`...")

    result = await python_executor.execute(func.code)
    await function_store.update_usage(func_name)

    # Update message with result (same formatting as /runfunc)
    # ...
```

## 4. Add Rate Limiting

Prevent abuse by rate limiting executions:

```python
from collections import defaultdict
from datetime import datetime, timedelta

# Track executions per user
execution_history = defaultdict(list)

RATE_LIMIT = 10  # Max 10 executions
RATE_WINDOW = 60  # Per 60 seconds

def check_rate_limit(user_id: str) -> bool:
    """Check if user has exceeded rate limit."""
    now = datetime.now()
    cutoff = now - timedelta(seconds=RATE_WINDOW)

    # Remove old executions
    execution_history[user_id] = [
        ts for ts in execution_history[user_id]
        if ts > cutoff
    ]

    # Check limit
    if len(execution_history[user_id]) >= RATE_LIMIT:
        return False

    # Record execution
    execution_history[user_id].append(now)
    return True

# Use in handlers:
@app.command("/analyze")
async def handle_analyze_command(ack, command, say):
    await ack()

    user_id = command['user_id']

    if not check_rate_limit(user_id):
        await say(f":x: Rate limit exceeded. Max {RATE_LIMIT} executions per {RATE_WINDOW}s.")
        return

    # ... rest of handler
```

## 5. Add Logging

Log all executions for audit trail:

```python
import logging

logger = logging.getLogger(__name__)

@app.command("/analyze")
async def handle_analyze_command(ack, command, say):
    await ack()

    user_id = command['user_id']
    code = command['text']

    logger.info(f"User {user_id} executing code: {code[:100]}...")

    result = await python_executor.execute(code)

    if result.success:
        logger.info(f"Execution succeeded in {result.execution_time_ms}ms")
    else:
        logger.error(f"Execution failed: {result.error}")

    # ... rest of handler
```

## 6. Error Handling Best Practices

```python
@app.command("/analyze")
async def handle_analyze_command(ack, command, say, client):
    await ack()

    try:
        # Execute code
        result = await python_executor.execute(code)

        if result.success:
            # Handle success
            pass
        else:
            # Handle execution error
            await say(f":x: {result.error}")
            logger.error(f"Execution error: {result.error}")

    except asyncio.TimeoutError:
        await say(":x: Execution timed out")
        logger.error("Execution timeout")

    except Exception as e:
        await say(f":x: Unexpected error: {str(e)}")
        logger.exception("Unexpected error in /analyze")
```

## 7. Testing

Test the integration:

```python
# test_bot_integration.py
import pytest
from unittest.mock import Mock, AsyncMock

@pytest.mark.asyncio
async def test_analyze_command():
    """Test /analyze command."""
    ack = AsyncMock()
    say = AsyncMock()

    command = {
        'text': 'result = 1 + 1',
        'user_id': 'U123',
        'channel_id': 'C123'
    }

    await handle_analyze_command(ack, command, say, None)

    ack.assert_called_once()
    say.assert_called()
```

## Complete Integration Example

See `examples/bot_integration_example.py` for a complete working example.

## Security Checklist

- [ ] Code validation enabled
- [ ] Timeout configured (30s)
- [ ] Rate limiting implemented
- [ ] Logging configured
- [ ] Error handling in place
- [ ] User permissions checked
- [ ] Audit trail enabled
- [ ] Module whitelist reviewed
- [ ] Test suite passing
