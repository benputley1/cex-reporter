"""
Example usage of Slack integration for CEX Reporter.

This script demonstrates how to use the SlackClient and SlackFormatter
to send various types of messages to Slack.
"""

import asyncio
from src.reporting import SlackClient, SlackFormatter, get_slack_client


async def example_portfolio_update():
    """Example: Send portfolio update to Slack"""
    print("\n=== Portfolio Update Example ===")

    # Sample portfolio data
    portfolio_data = {
        'total_value_usd': 125430.50,
        'assets': [
            {
                'symbol': 'USDT',
                'amount': 45230.50,
                'usd_value': 45230.50
            },
            {
                'symbol': 'ALKIMI',
                'amount': 2500000.00,
                'usd_value': 80200.00
            }
        ],
        'exchanges': [
            {
                'name': 'MEXC',
                'total_usd': 45230.50,
            },
            {
                'name': 'Kraken',
                'total_usd': 30150.00,
            },
            {
                'name': 'KuCoin',
                'total_usd': 35050.00,
            },
            {
                'name': 'Gate.io',
                'total_usd': 15000.00,
            }
        ]
    }

    # Sample P&L data
    pnl_data = {
        '24h': {
            'value': 1250.50,
            'percentage': 1.01
        },
        '7d': {
            'value': -450.25,
            'percentage': -0.36
        },
        'total': {
            'value': 15430.50,
            'percentage': 14.02
        }
    }

    # Send portfolio update
    client = get_slack_client()
    success = await client.send_portfolio_update(portfolio_data, pnl_data)

    print(f"Portfolio update sent: {success}")


async def example_alert():
    """Example: Send alert to Slack"""
    print("\n=== Alert Example ===")

    # Create alert
    client = get_slack_client()
    success = await client.send_alert(
        alert_type='significant_movement',
        message='ALKIMI price has increased by 15% in the last hour',
        data={
            'symbol': 'ALKIMI',
            'change_percent': 15.5,
            'current_price_usd': 0.0345,
            'volume_24h': 125000.00,
            'exchange': 'MEXC'
        }
    )

    print(f"Alert sent: {success}")


async def example_daily_summary():
    """Example: Send daily summary to Slack"""
    print("\n=== Daily Summary Example ===")

    # Sample data
    portfolio_data = {
        'total_value_usd': 125430.50,
    }

    pnl_data = {
        '24h': {
            'value': 2340.50,
            'percentage': 1.90
        }
    }

    stats = {
        'trading_volume': 45000.00,
        'total_trades': 23,
        'top_movers': [
            {'symbol': 'ALKIMI', 'change_pct': 15.5},
            {'symbol': 'USDT', 'change_pct': 0.01},
        ]
    }

    # Send daily summary
    client = get_slack_client()
    success = await client.send_daily_summary(portfolio_data, pnl_data, stats)

    print(f"Daily summary sent: {success}")


async def example_error_notification():
    """Example: Send error notification to Slack"""
    print("\n=== Error Notification Example ===")

    # Simulate an error
    try:
        # This will raise an exception
        result = 1 / 0
    except Exception as error:
        # Send error notification
        client = get_slack_client()
        success = await client.send_error(
            error=error,
            context={
                'component': 'Exchange API',
                'operation': 'fetch_balance',
                'timestamp': '2025-11-04 12:00:00 UTC',
                'additional_info': {
                    'exchange': 'MEXC',
                    'retry_count': 3,
                    'api_endpoint': '/api/v3/balance'
                }
            }
        )

        print(f"Error notification sent: {success}")


async def example_formatter_only():
    """Example: Use formatter without sending"""
    print("\n=== Formatter Only Example ===")

    formatter = SlackFormatter()

    # Format portfolio update
    portfolio_data = {
        'total_value_usd': 125430.50,
        'assets': [
            {'symbol': 'USDT', 'amount': 45230.50, 'usd_value': 45230.50},
        ],
        'exchanges': [
            {'name': 'MEXC', 'total_usd': 45230.50},
        ]
    }

    pnl_data = {
        '24h': {'value': 1250.50, 'percentage': 1.01},
        '7d': {'value': -450.25, 'percentage': -0.36},
        'total': {'value': 15430.50, 'percentage': 14.02}
    }

    blocks = formatter.format_portfolio_update(portfolio_data, pnl_data)
    print(f"Formatted blocks: {blocks}")


async def main():
    """Run all examples"""
    print("="*60)
    print("CEX Reporter - Slack Integration Examples")
    print("="*60)
    print("\nNote: In MOCK_MODE=true, messages are logged instead of sent.")
    print("Set MOCK_MODE=false and SLACK_WEBHOOK_URL in .env to send real messages.")

    # Run examples
    await example_portfolio_update()
    await example_alert()
    await example_daily_summary()
    await example_error_notification()
    await example_formatter_only()

    print("\n" + "="*60)
    print("All examples completed!")
    print("="*60)


if __name__ == "__main__":
    # Initialize logging
    from src.utils import setup_from_config
    setup_from_config()

    # Run examples
    asyncio.run(main())
