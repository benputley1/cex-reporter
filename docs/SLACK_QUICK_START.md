# Slack Integration - Quick Start Guide

## Setup (5 minutes)

### 1. Create Slack Webhook
1. Go to https://api.slack.com/apps
2. Create new app → "From scratch"
3. Enable "Incoming Webhooks"
4. Add webhook to workspace
5. Copy the webhook URL

### 2. Configure
Add to `.env`:
```bash
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL
MOCK_MODE=false
```

### 3. Use It
```python
from src.reporting import get_slack_client

# Initialize client
slack = get_slack_client()

# Send portfolio update
await slack.send_portfolio_update(portfolio_data, pnl_data)

# Send alert
await slack.send_alert('price_change', 'Price increased 15%', data)

# Send error notification
await slack.send_error(error, context)

# Send daily summary
await slack.send_daily_summary(portfolio_data, pnl_data, stats)
```

## Data Structures

### Portfolio Data
```python
portfolio_data = {
    'total_value_usd': 125430.50,
    'assets': [
        {'symbol': 'USDT', 'amount': 45230.50, 'usd_value': 45230.50},
        {'symbol': 'ALKIMI', 'amount': 2500000.00, 'usd_value': 80200.00}
    ],
    'exchanges': [
        {'name': 'MEXC', 'total_usd': 45230.50},
        {'name': 'Kraken', 'total_usd': 30150.00}
    ]
}
```

### P&L Data
```python
pnl_data = {
    '24h': {'value': 1250.50, 'percentage': 1.01},
    '7d': {'value': -450.25, 'percentage': -0.36},
    'total': {'value': 15430.50, 'percentage': 14.02}
}
```

### Stats Data (for Daily Summary)
```python
stats = {
    'trading_volume': 45000.00,
    'total_trades': 23,
    'top_movers': [
        {'symbol': 'ALKIMI', 'change_pct': 15.5},
        {'symbol': 'USDT', 'change_pct': 0.01}
    ]
}
```

### Alert Data
```python
# Price change alert
data = {
    'symbol': 'ALKIMI',
    'change_percent': 15.5,
    'current_price_usd': 0.0345,
    'volume_24h': 125000.00,
    'exchange': 'MEXC'
}
```

### Error Context
```python
context = {
    'component': 'Exchange API',
    'operation': 'fetch_balance',
    'timestamp': '2025-11-04 12:00:00 UTC',
    'additional_info': {
        'exchange': 'MEXC',
        'retry_count': 3,
        'api_endpoint': '/api/v3/balance'
    }
}
```

## Complete Example

```python
import asyncio
from src.reporting import get_slack_client

async def main():
    # Initialize client
    slack = get_slack_client()

    # Prepare data
    portfolio_data = {
        'total_value_usd': 125430.50,
        'assets': [
            {'symbol': 'USDT', 'amount': 45230.50, 'usd_value': 45230.50},
            {'symbol': 'ALKIMI', 'amount': 2500000.00, 'usd_value': 80200.00}
        ],
        'exchanges': [
            {'name': 'MEXC', 'total_usd': 45230.50}
        ]
    }

    pnl_data = {
        '24h': {'value': 1250.50, 'percentage': 1.01},
        '7d': {'value': -450.25, 'percentage': -0.36},
        'total': {'value': 15430.50, 'percentage': 14.02}
    }

    # Send portfolio update
    success = await slack.send_portfolio_update(portfolio_data, pnl_data)
    print(f"Sent: {success}")

# Run
asyncio.run(main())
```

## Testing

Test without sending (mock mode):
```bash
# In .env
MOCK_MODE=true

# Run your code - messages will be logged, not sent
```

## Common Use Cases

### Regular Portfolio Updates
```python
async def send_regular_update():
    slack = get_slack_client()
    portfolio = await fetch_portfolio()
    pnl = await calculate_pnl()
    await slack.send_portfolio_update(portfolio, pnl)
```

### Error Monitoring
```python
async def monitored_operation():
    slack = get_slack_client()
    try:
        result = await risky_operation()
    except Exception as e:
        await slack.send_error(e, {
            'component': 'Portfolio Monitor',
            'operation': 'fetch_data'
        })
```

### Price Alerts
```python
async def check_price_changes():
    slack = get_slack_client()
    change = await get_price_change()

    if abs(change) > 5.0:  # 5% threshold
        await slack.send_alert(
            'price_change',
            f'Price changed by {change}%',
            {'symbol': 'ALKIMI', 'change_percent': change}
        )
```

### Daily Summary Report
```python
async def send_daily_report():
    slack = get_slack_client()
    portfolio = await fetch_portfolio()
    pnl = await calculate_daily_pnl()
    stats = await get_trading_stats()

    await slack.send_daily_summary(portfolio, pnl, stats)
```

## Troubleshooting

### Messages not appearing?
1. Check `MOCK_MODE=false` in .env
2. Verify webhook URL is correct
3. Check logs: `tail -f logs/cex_reporter.log`

### Rate limit errors?
```python
# Wait between messages (automatic, but check your code)
await slack.send_message(msg1)
# Client enforces 1 second delay automatically
await slack.send_message(msg2)
```

### Format errors?
- Ensure all required fields are present in data structures
- Check that numeric values are numbers, not strings
- Verify dictionary structure matches examples

## Advanced Features

### Custom Webhook
```python
# Use different webhook for different channels
slack_alerts = get_slack_client('https://hooks.slack.com/alerts')
slack_reports = get_slack_client('https://hooks.slack.com/reports')
```

### Custom Formatting
```python
from src.reporting import SlackFormatter

formatter = SlackFormatter()
blocks = formatter.format_portfolio_update(portfolio_data, pnl_data)

# Modify blocks as needed
blocks['blocks'].append({
    'type': 'section',
    'text': {'type': 'mrkdwn', 'text': 'Custom section'}
})

# Send manually
await slack.send_message(blocks)
```

## Resources

- Full Documentation: `docs/SLACK_INTEGRATION.md`
- Examples: `examples/slack_integration_example.py`
- Tests: `tests/test_slack_integration.py`
- Summary: `SLACK_INTEGRATION_SUMMARY.md`

## Support

Check logs for detailed error messages:
```bash
tail -f logs/cex_reporter.log
```

All methods return `bool`:
- `True` = message sent successfully
- `False` = message failed (check logs)

---

**That's it! You're ready to use Slack integration.**

Run the example:
```bash
PYTHONPATH=/Users/ben/Desktop/cex-reporter python3 examples/slack_integration_example.py
```
