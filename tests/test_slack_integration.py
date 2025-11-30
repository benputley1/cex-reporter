"""
Tests for Slack integration modules.

Tests SlackFormatter and SlackClient functionality.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime

from src.reporting import SlackFormatter, SlackClient, get_slack_client


class TestSlackFormatter:
    """Tests for SlackFormatter class"""

    def setup_method(self):
        """Setup test fixtures"""
        self.formatter = SlackFormatter()

        self.portfolio_data = {
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

        self.pnl_data = {
            '24h': {'value': 1250.50, 'percentage': 1.01},
            '7d': {'value': -450.25, 'percentage': -0.36},
            'total': {'value': 15430.50, 'percentage': 14.02}
        }

    def test_format_portfolio_update(self):
        """Test portfolio update formatting"""
        result = self.formatter.format_portfolio_update(
            self.portfolio_data,
            self.pnl_data
        )

        # Check structure
        assert 'blocks' in result
        assert isinstance(result['blocks'], list)
        assert len(result['blocks']) > 0

        # Check header exists
        header = result['blocks'][0]
        assert header['type'] == 'header'
        assert '📊' in header['text']['text']
        assert 'Treasury Report' in header['text']['text']

        # Check contains portfolio value
        blocks_text = str(result['blocks'])
        assert '$125,430.50' in blocks_text
        assert 'USDT' in blocks_text
        assert 'ALKIMI' in blocks_text

    def test_format_portfolio_update_with_positive_pnl(self):
        """Test portfolio formatting with positive P&L"""
        result = self.formatter.format_portfolio_update(
            self.portfolio_data,
            self.pnl_data
        )

        blocks_text = str(result['blocks'])
        # Should contain positive indicators
        assert '🟢' in blocks_text
        assert '+$1,250.50' in blocks_text

    def test_format_portfolio_update_with_negative_pnl(self):
        """Test portfolio formatting with negative P&L"""
        result = self.formatter.format_portfolio_update(
            self.portfolio_data,
            self.pnl_data
        )

        blocks_text = str(result['blocks'])
        # Should contain negative indicators
        assert '🔴' in blocks_text
        assert '$-450.25' in blocks_text

    def test_format_alert_price_change(self):
        """Test alert formatting for price change"""
        result = self.formatter.format_alert(
            alert_type='price_change',
            message='Price increased significantly',
            data={
                'symbol': 'ALKIMI',
                'change_percent': 15.5,
                'current_price_usd': 0.0345
            }
        )

        assert 'blocks' in result
        blocks_text = str(result['blocks'])
        assert 'Alert' in blocks_text
        assert 'Price increased significantly' in blocks_text
        assert 'ALKIMI' in blocks_text
        assert '15.5' in blocks_text

    def test_format_alert_error(self):
        """Test alert formatting for error"""
        result = self.formatter.format_alert(
            alert_type='error',
            message='System error occurred',
            data={'component': 'Exchange API'}
        )

        assert 'blocks' in result
        blocks_text = str(result['blocks'])
        assert 'error' in blocks_text.lower()
        assert 'System error occurred' in blocks_text

    def test_format_alert_significant_movement(self):
        """Test alert formatting for significant movement"""
        result = self.formatter.format_alert(
            alert_type='significant_movement',
            message='Large portfolio movement detected',
            data={'change_usd': 5000.00}
        )

        assert 'blocks' in result
        blocks_text = str(result['blocks'])
        assert '🚨' in blocks_text
        assert 'Large portfolio movement detected' in blocks_text

    def test_format_daily_summary(self):
        """Test daily summary formatting"""
        stats = {
            'trading_volume': 45000.00,
            'total_trades': 23,
            'top_movers': [
                {'symbol': 'ALKIMI', 'change_pct': 15.5},
                {'symbol': 'USDT', 'change_pct': 0.01},
            ]
        }

        result = self.formatter.format_daily_summary(
            self.portfolio_data,
            self.pnl_data,
            stats
        )

        assert 'blocks' in result
        blocks_text = str(result['blocks'])
        assert 'Daily' in blocks_text
        assert '$125,430.50' in blocks_text
        assert 'ALKIMI' in blocks_text
        assert '23' in blocks_text  # total trades
        assert '$45,000.00' in blocks_text  # trading volume

    def test_format_error_notification(self):
        """Test error notification formatting"""
        try:
            # Raise an error to capture
            raise ValueError("Test error message")
        except Exception as error:
            result = self.formatter.format_error_notification(
                error=error,
                context={
                    'component': 'Test Component',
                    'operation': 'test_operation',
                    'timestamp': '2025-11-04 12:00:00 UTC',
                    'additional_info': {
                        'exchange': 'MEXC',
                        'retry_count': 3
                    }
                }
            )

            assert 'blocks' in result
            blocks_text = str(result['blocks'])
            assert '⚠️' in blocks_text
            assert 'ValueError' in blocks_text
            assert 'Test error message' in blocks_text
            assert 'Test Component' in blocks_text
            assert 'test_operation' in blocks_text
            assert 'Stack Trace' in blocks_text


class TestSlackClient:
    """Tests for SlackClient class"""

    @pytest.fixture
    def mock_settings(self):
        """Mock settings for testing"""
        with patch('src.reporting.slack.settings') as mock:
            mock.mock_mode = True
            mock.slack_webhook_url = 'https://hooks.slack.com/test'
            yield mock

    def test_client_initialization(self, mock_settings):
        """Test client initialization"""
        client = SlackClient()
        assert client.webhook_url == 'https://hooks.slack.com/test'
        assert client.formatter is not None
        assert client.max_retries == 3

    def test_client_with_custom_webhook(self, mock_settings):
        """Test client with custom webhook URL"""
        custom_url = 'https://custom.webhook.url'
        client = SlackClient(webhook_url=custom_url)
        assert client.webhook_url == custom_url

    @pytest.mark.asyncio
    async def test_send_message_mock_mode(self, mock_settings):
        """Test sending message in mock mode"""
        client = SlackClient()
        blocks = {'blocks': [{'type': 'section', 'text': {'type': 'mrkdwn', 'text': 'Test'}}]}

        result = await client.send_message(blocks)
        assert result is True

    @pytest.mark.asyncio
    async def test_send_portfolio_update(self, mock_settings):
        """Test sending portfolio update"""
        client = SlackClient()

        portfolio_data = {
            'total_value_usd': 125430.50,
            'assets': [{'symbol': 'USDT', 'amount': 45230.50, 'usd_value': 45230.50}],
            'exchanges': [{'name': 'MEXC', 'total_usd': 45230.50}]
        }

        pnl_data = {
            '24h': {'value': 1250.50, 'percentage': 1.01},
            '7d': {'value': -450.25, 'percentage': -0.36},
            'total': {'value': 15430.50, 'percentage': 14.02}
        }

        result = await client.send_portfolio_update(portfolio_data, pnl_data)
        assert result is True

    @pytest.mark.asyncio
    async def test_send_alert(self, mock_settings):
        """Test sending alert"""
        client = SlackClient()

        result = await client.send_alert(
            alert_type='price_change',
            message='Test alert',
            data={'symbol': 'ALKIMI', 'change_percent': 15.5}
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_send_error(self, mock_settings):
        """Test sending error notification"""
        client = SlackClient()

        try:
            raise ValueError("Test error")
        except Exception as error:
            result = await client.send_error(
                error=error,
                context={
                    'component': 'Test',
                    'operation': 'test_operation'
                }
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_send_daily_summary(self, mock_settings):
        """Test sending daily summary"""
        client = SlackClient()

        portfolio_data = {'total_value_usd': 125430.50}
        pnl_data = {'24h': {'value': 1250.50, 'percentage': 1.01}}
        stats = {
            'trading_volume': 45000.00,
            'total_trades': 23,
            'top_movers': [{'symbol': 'ALKIMI', 'change_pct': 15.5}]
        }

        result = await client.send_daily_summary(portfolio_data, pnl_data, stats)
        assert result is True

    def test_get_slack_client(self, mock_settings):
        """Test get_slack_client convenience function"""
        client = get_slack_client()
        assert isinstance(client, SlackClient)
        assert client.webhook_url == 'https://hooks.slack.com/test'

    def test_get_slack_client_with_custom_webhook(self, mock_settings):
        """Test get_slack_client with custom webhook"""
        custom_url = 'https://custom.webhook.url'
        client = get_slack_client(webhook_url=custom_url)
        assert client.webhook_url == custom_url

    @pytest.mark.asyncio
    async def test_send_message_no_webhook(self):
        """Test sending message without webhook URL"""
        with patch('src.reporting.slack.settings') as mock_settings:
            mock_settings.mock_mode = False
            mock_settings.slack_webhook_url = ''

            client = SlackClient()
            blocks = {'blocks': []}

            result = await client.send_message(blocks)
            assert result is False

    @pytest.mark.asyncio
    async def test_rate_limiting(self, mock_settings):
        """Test rate limiting between messages"""
        import time

        client = SlackClient()
        blocks = {'blocks': [{'type': 'section', 'text': {'type': 'mrkdwn', 'text': 'Test'}}]}

        # Send first message
        start_time = time.time()
        await client.send_message(blocks)

        # Send second message (should be rate limited)
        await client.send_message(blocks)
        elapsed = time.time() - start_time

        # In mock mode, rate limiting still applies
        # Should take at least 1 second for two messages
        assert elapsed >= 0.9  # Allow small margin

    @pytest.mark.asyncio
    async def test_format_error_in_send_portfolio(self, mock_settings):
        """Test error handling in send_portfolio_update"""
        client = SlackClient()

        # Pass invalid data to trigger formatting error
        result = await client.send_portfolio_update(None, None)
        assert result is False

    @pytest.mark.asyncio
    async def test_format_error_in_send_alert(self, mock_settings):
        """Test error handling in send_alert"""
        client = SlackClient()

        # Pass None to trigger error
        with patch.object(client.formatter, 'format_alert', side_effect=Exception("Test error")):
            result = await client.send_alert('test', 'message', {})
            assert result is False


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
