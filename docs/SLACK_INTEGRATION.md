# Slack Integration

The CEX Reporter includes a comprehensive Slack integration that allows you to receive portfolio updates, alerts, and error notifications directly in your Slack workspace.

## Features

- **Portfolio Updates**: Regular reports showing total value, asset breakdown, and exchange distribution
- **P&L Tracking**: 24h, 7d, and total profit/loss with percentages
- **Alerts**: Price changes, significant movements, and custom alerts
- **Error Notifications**: Detailed error reports with stack traces
- **Daily Summaries**: Comprehensive daily reports with trading statistics
- **Rate Limiting**: Automatic rate limiting (1 message/second)
- **Retry Logic**: Exponential backoff with 3 retries
- **Mock Mode**: Test without sending actual messages

## Setup

### 1. Create Slack Webhook

1. Go to https://api.slack.com/apps
2. Create a new app or select an existing one
3. Navigate to "Incoming Webhooks" and activate it
4. Click "Add New Webhook to Workspace"
5. Select the channel where you want to receive notifications
6. Copy the webhook URL (looks like `https://hooks.slack.com/services/...`)

### 2. Configure Environment

Add the webhook URL to your `.env` file:

```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
MOCK_MODE=false  # Set to true for testing
```

## Usage

### Basic Example

```python
import asyncio
from src.reporting import SlackClient

async def send_portfolio_update():
    client = SlackClient()

    portfolio_data = {
        'total_value_usd': 125430.50,
        'assets': [
            {'symbol': 'USDT', 'amount': 45230.50, 'usd_value': 45230.50},
            {'symbol': 'ALKIMI', 'amount': 2500000.00, 'usd_value': 80200.00}
        ],
        'exchanges': [
            {'name': 'MEXC', 'total_usd': 45230.50},
            {'name': 'Kraken', 'total_usd': 30150.00},
        ]
    }

    pnl_data = {
        '24h': {'value': 1250.50, 'percentage': 1.01},
        '7d': {'value': -450.25, 'percentage': -0.36},
        'total': {'value': 15430.50, 'percentage': 14.02}
    }

    success = await client.send_portfolio_update(portfolio_data, pnl_data)
    print(f"Sent: {success}")

asyncio.run(send_portfolio_update())
```

### Sending Alerts

```python
async def send_price_alert():
    client = SlackClient()

    await client.send_alert(
        alert_type='price_change',
        message='ALKIMI price has increased by 15%',
        data={
            'symbol': 'ALKIMI',
            'change_percent': 15.5,
            'current_price_usd': 0.0345,
            'volume_24h': 125000.00
        }
    )
```

### Error Notifications

```python
async def send_error():
    client = SlackClient()

    try:
        # Your code here
        result = risky_operation()
    except Exception as error:
        await client.send_error(
            error=error,
            context={
                'component': 'Exchange API',
                'operation': 'fetch_balance',
                'additional_info': {
                    'exchange': 'MEXC',
                    'retry_count': 3
                }
            }
        )
```

### Daily Summary

```python
async def send_daily_summary():
    client = SlackClient()

    stats = {
        'trading_volume': 45000.00,
        'total_trades': 23,
        'top_movers': [
            {'symbol': 'ALKIMI', 'change_pct': 15.5},
            {'symbol': 'USDT', 'change_pct': 0.01},
        ]
    }

    await client.send_daily_summary(portfolio_data, pnl_data, stats)
```

## Formatter Module

The `SlackFormatter` class provides low-level formatting methods if you need custom control:

```python
from src.reporting import SlackFormatter

formatter = SlackFormatter()

# Format portfolio update
blocks = formatter.format_portfolio_update(portfolio_data, pnl_data)

# Format alert
blocks = formatter.format_alert('price_change', 'Price increased', data)

# Format error
blocks = formatter.format_error_notification(error, context)

# Format daily summary
blocks = formatter.format_daily_summary(portfolio_data, pnl_data, stats)

# Send manually
import aiohttp
async with aiohttp.ClientSession() as session:
    await session.post(webhook_url, json=blocks)
```

## Mock Mode

For testing without sending actual messages, enable mock mode:

```bash
MOCK_MODE=true
```

In mock mode:
- Messages are logged instead of sent to Slack
- All methods return `True` to indicate success
- Full message structure is logged for verification
- No network calls are made

This is useful for:
- Development and testing
- CI/CD pipelines
- Debugging message formatting

## Message Types

### Portfolio Update

Shows:
- Header: "📊 Alkimi Treasury Report"
- Total portfolio value in USD
- Asset breakdown with amounts and USD values
- Exchange distribution with percentages
- P&L summary (24h, 7d, total) with emoji indicators
- Timestamp

### Alert

Shows:
- Alert type-specific emoji (📉 🚨 ⚠️)
- Alert message
- Detailed data fields
- Timestamp

Alert types:
- `price_change`: Price movements
- `significant_movement`: Large portfolio changes
- `error`: System errors requiring attention

### Daily Summary

Shows:
- Daily summary header
- Total portfolio value
- 24h performance
- Trading statistics (volume, trades)
- Top movers with percentage changes

### Error Notification

Shows:
- Error header (⚠️)
- Component and operation details
- Error type and message
- Full stack trace in code block
- Additional context information
- Timestamp

## Rate Limiting

The SlackClient automatically enforces rate limiting:
- Maximum 1 message per second
- Automatic delay between messages
- Handles Slack's rate limit responses
- Exponential backoff on errors

## Retry Logic

Failed messages are automatically retried:
- 3 retry attempts
- Exponential backoff (1s, 2s, 4s)
- Handles timeouts and network errors
- Logs all retry attempts

## Error Handling

The integration includes comprehensive error handling:
- Validates webhook URL before sending
- Catches and logs all exceptions
- Returns boolean success/failure
- Never crashes the main application
- Detailed error logging for debugging

## Best Practices

1. **Use Mock Mode for Testing**: Always test with `MOCK_MODE=true` first
2. **Rate Limiting**: Don't send more than 1 message per second
3. **Error Context**: Include detailed context in error notifications
4. **Message Size**: Keep messages under Slack's size limits
5. **Webhook Security**: Keep your webhook URL secret (use environment variables)
6. **Logging**: Check logs for failed message attempts

## Troubleshooting

### Messages Not Appearing

1. Check `MOCK_MODE` is set to `false`
2. Verify `SLACK_WEBHOOK_URL` is correct
3. Check logs for error messages
4. Ensure webhook has correct permissions
5. Verify channel exists and is accessible

### Rate Limiting Issues

If you see "rate limit" errors:
- Reduce message frequency
- Check for message loops
- Review your sending logic
- Ensure only one instance is sending

### Formatting Issues

If messages look broken:
- Check data structure matches expected format
- Verify all required fields are present
- Review Slack Block Kit documentation
- Check logs for formatting errors

## Advanced Usage

### Custom Webhook URL

```python
from src.reporting import SlackClient

# Use custom webhook
client = SlackClient(webhook_url='https://custom.webhook.url')
await client.send_message(custom_blocks)
```

### Custom Formatting

```python
from src.reporting import SlackFormatter

class CustomFormatter(SlackFormatter):
    @staticmethod
    def format_custom_message(data):
        return {
            "blocks": [
                {
                    "type": "section",
                    "text": {"type": "mrkdwn", "text": "Custom message"}
                }
            ]
        }
```

## Examples

See `examples/slack_integration_example.py` for complete working examples of all message types.

Run the examples:
```bash
PYTHONPATH=. python3 examples/slack_integration_example.py
```

## API Reference

### SlackClient

#### `__init__(webhook_url: Optional[str] = None)`
Initialize Slack client with optional custom webhook URL.

#### `async send_message(blocks: Dict) -> bool`
Send raw Slack Block Kit message.

#### `async send_portfolio_update(portfolio_data: Dict, pnl_data: Dict) -> bool`
Send formatted portfolio update.

#### `async send_alert(alert_type: str, message: str, data: Dict) -> bool`
Send formatted alert message.

#### `async send_error(error: Exception, context: Dict) -> bool`
Send formatted error notification.

#### `async send_daily_summary(portfolio_data: Dict, pnl_data: Dict, stats: Dict) -> bool`
Send formatted daily summary.

### SlackFormatter

#### `format_portfolio_update(portfolio_data: Dict, pnl_data: Dict) -> Dict`
Format portfolio update as Slack blocks.

#### `format_alert(alert_type: str, message: str, data: Dict) -> Dict`
Format alert as Slack blocks.

#### `format_daily_summary(portfolio_data: Dict, pnl_data: Dict, stats: Dict) -> Dict`
Format daily summary as Slack blocks.

#### `format_error_notification(error: Exception, context: Dict) -> Dict`
Format error notification as Slack blocks.

## Integration with Main Application

The Slack integration is designed to be used throughout the application:

```python
from src.reporting import get_slack_client

# In your exchange monitoring code
async def monitor_portfolio():
    slack = get_slack_client()

    try:
        portfolio = await fetch_portfolio()
        pnl = await calculate_pnl()

        # Send update
        await slack.send_portfolio_update(portfolio, pnl)

    except Exception as e:
        # Notify on error
        await slack.send_error(e, {
            'component': 'Portfolio Monitor',
            'operation': 'monitor_portfolio'
        })
```

## License

Part of the CEX Reporter project.
