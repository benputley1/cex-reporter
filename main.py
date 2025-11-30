#!/usr/bin/env python3
"""
CEX Reporter - Main Orchestrator
Coordinates portfolio tracking, P&L calculation, and Slack reporting
"""
import asyncio
import sys
from datetime import datetime, timezone
from typing import List

from config.settings import settings
from src.utils.logging import setup_from_config, get_logger
from src.exchanges import ExchangeInterface
from src.exchanges.mexc import MEXCClient
from src.exchanges.kraken import KrakenClient
from src.exchanges.kucoin import KuCoinClient
from src.exchanges.gateio import GateioClient
from src.exchanges.cetus import CetusClient
from src.exchanges.sui_monitor import SuiTokenMonitor
from src.analytics.portfolio import PortfolioAggregator
from src.analytics.pnl import PnLCalculator
from src.analytics.position_tracker import PositionTracker
from src.analytics.simple_tracker import SimpleTracker
from src.reporting import get_slack_client
from src.reporting.position_formatter import PositionFormatter
from src.reporting.simple_formatter import SimpleFormatter

# Set up logging
setup_from_config()
logger = get_logger(__name__)


class CEXReporter:
    """Main orchestrator for CEX portfolio reporting"""

    def __init__(self):
        """Initialize the reporter with all components"""
        self.exchanges: List[ExchangeInterface] = []
        self.portfolio_aggregator = PortfolioAggregator()
        self.pnl_calculator = PnLCalculator()
        # Old tracker (keeping for now)
        self.position_tracker = PositionTracker()
        self.position_formatter = PositionFormatter()
        # New simplified tracker and formatter
        self.simple_tracker = SimpleTracker()
        self.simple_formatter = SimpleFormatter()
        self.slack_client = get_slack_client()
        self.running = False

        logger.info("CEX Reporter initialized", extra={
            'mock_mode': settings.mock_mode,
            'tracked_assets': settings.tracked_assets,
            'report_interval': settings.report_interval,
        })

    async def initialize_exchanges(self):
        """Initialize all exchange clients (with multi-account support)"""
        logger.info("Initializing exchange clients...")

        try:
            # Create exchange instances with multi-account support
            exchange_classes = [
                ('mexc', 'MEXC', MEXCClient),
                ('kraken', 'Kraken', KrakenClient),
                ('kucoin', 'KuCoin', KuCoinClient),
                ('gateio', 'Gate.io', GateioClient),
            ]

            account_count = 0
            for exchange_key, display_name, exchange_class in exchange_classes:
                try:
                    # Get all accounts for this exchange
                    accounts = settings.get_exchange_accounts(exchange_key)

                    if not accounts:
                        logger.warning(f"No accounts configured for {display_name}, skipping...")
                        continue

                    # Create an instance for each account
                    for account_config in accounts:
                        account_name = account_config['account_name']
                        try:
                            logger.debug(f"Initializing {display_name} ({account_name}) client...")

                            # Create exchange instance with account-specific config
                            exchange = exchange_class(
                                config=account_config,
                                account_name=account_name
                            )
                            await exchange.initialize()
                            self.exchanges.append(exchange)

                            logger.info(f"✓ {display_name} ({account_name}) initialized successfully")
                            account_count += 1

                        except Exception as e:
                            logger.error(f"✗ Failed to initialize {display_name} ({account_name}): {e}")
                            # Continue with other accounts

                except Exception as e:
                    logger.error(f"✗ Failed to initialize {display_name} exchange: {e}")
                    # Continue with other exchanges even if one fails

            # Initialize Cetus (DeFi protocol) if enabled
            if settings.cetus_enabled and settings.cetus_wallet_address:
                try:
                    logger.debug("Initializing Cetus protocol client...")
                    cetus = CetusClient(
                        config=settings.cetus_config,
                        account_name='MAIN'
                    )
                    await cetus.initialize()
                    self.exchanges.append(cetus)
                    logger.info("✓ Cetus protocol initialized successfully")
                    account_count += 1
                except Exception as e:
                    logger.error(f"✗ Failed to initialize Cetus protocol: {e}")
                    # Continue with other exchanges even if Cetus fails

            # Initialize Sui DEX Monitor (for all DEX activity via token contract)
            sui_config = settings.sui_config
            if sui_config.get('token_contract'):
                try:
                    logger.debug("Initializing Sui DEX Monitor...")
                    sui_monitor = SuiTokenMonitor(
                        config=sui_config,
                        account_name='DEX_MONITOR'
                    )
                    await sui_monitor.initialize()
                    self.exchanges.append(sui_monitor)
                    logger.info("✓ Sui DEX Monitor initialized successfully")
                    account_count += 1
                except Exception as e:
                    logger.error(f"✗ Failed to initialize Sui DEX Monitor: {e}")
                    # Continue even if DEX monitor fails

            if not self.exchanges:
                raise RuntimeError("No exchange accounts initialized successfully")

            logger.info(f"Successfully initialized {account_count} account(s) across {len(set(ex.exchange_name for ex in self.exchanges))} exchange(s)")

        except Exception as e:
            logger.error(f"Failed to initialize exchanges: {e}")
            raise

    async def generate_report(self) -> bool:
        """Generate and send portfolio report"""
        try:
            logger.info("=" * 60)
            logger.info("Generating simplified position report...")

            # Generate simplified report (new 25-day rolling window)
            logger.info("Fetching balances, trades, and calculating 25-day metrics...")
            report_data = await self.simple_tracker.get_report(self.exchanges)

            # Send to Slack
            logger.info("Sending report to Slack...")

            # Format the simplified report
            slack_message = self.simple_formatter.format_report(report_data)
            success = await self.slack_client.send_message(slack_message)

            if success:
                logger.info("✓ Simplified report sent successfully")
            else:
                logger.warning("✗ Failed to send simplified report")

            return success

        except Exception as e:
            logger.error(f"Error generating report: {e}", exc_info=True)

            # Send error notification
            try:
                await self.slack_client.send_error(e, {
                    'component': 'report_generation',
                    'timestamp': datetime.now(timezone.utc).isoformat(),
                })
            except Exception as slack_error:
                logger.error(f"Failed to send error notification: {slack_error}")

            return False

    async def _check_alerts_position(self, position_data: dict):
        """Check if any alerts should be triggered based on position changes"""
        try:
            # Check for significant ALKIMI price changes
            alkimi_pos = position_data.get('alkimi_position', {})
            price_change_percent = alkimi_pos.get('price_change_percent', 0)

            threshold = settings.alert_threshold_percent

            if abs(price_change_percent) >= threshold:
                logger.warning(
                    f"Alert: ALKIMI price changed {price_change_percent:+.2f}% (threshold: {threshold}%)"
                )

                alert_message = (
                    f"ALKIMI price changed by {price_change_percent:+.2f}% "
                    f"from ${alkimi_pos.get('starting_price', 0):.4f} to ${alkimi_pos.get('current_price', 0):.4f}"
                )

                await self.slack_client.send_alert(
                    alert_type='price_change',
                    message=alert_message,
                    data={
                        'price_change_percent': price_change_percent,
                        'starting_price': alkimi_pos.get('starting_price', 0),
                        'current_price': alkimi_pos.get('current_price', 0),
                        'threshold': threshold,
                    }
                )

        except Exception as e:
            logger.error(f"Error checking alerts: {e}")

    async def run_once(self):
        """Run a single report generation cycle"""
        try:
            await self.initialize_exchanges()
            await self.generate_report()

        finally:
            # Cleanup
            await self.cleanup()

    async def run_refresh(self):
        """Run data refresh only - no Slack reporting"""
        try:
            logger.info("=" * 60)
            logger.info("DATA REFRESH MODE - No Slack reporting")
            logger.info("=" * 60)

            await self.initialize_exchanges()

            # Fetch current balances and trades (updates trade_cache.db)
            logger.info("Fetching balances and trades...")
            current_balances, holdings_by_exchange = await self.simple_tracker._get_holdings_by_exchange(self.exchanges)

            # Save today's snapshot
            logger.info("Saving daily snapshot...")
            self.simple_tracker.daily_snapshot.save_snapshot(current_balances)

            # Fetch and cache trades
            logger.info("Fetching and caching trades...")
            all_trades, complete_window_start = await self.simple_tracker._fetch_and_cache_trades(self.exchanges)

            # Log summary
            logger.info("=" * 60)
            logger.info("DATA REFRESH SUMMARY")
            logger.info("=" * 60)
            logger.info(f"Total trades cached: {len(all_trades)}")
            logger.info(f"Complete data window starts: {complete_window_start}")
            logger.info(f"Current USDT balance: ${current_balances.get('USDT', 0):,.2f}")
            logger.info(f"Current ALKIMI balance: {current_balances.get('ALKIMI', 0):,.0f}")
            logger.info("=" * 60)
            logger.info("Data refresh complete (no Slack report sent)")
            logger.info("=" * 60)

        finally:
            # Cleanup
            await self.cleanup()

    async def run_continuous(self):
        """Run continuous reporting loop"""
        self.running = True

        try:
            await self.initialize_exchanges()

            logger.info(f"Starting continuous reporting (interval: {settings.report_interval}s)")

            # Generate initial report
            await self.generate_report()

            # Continuous loop
            while self.running:
                logger.info(f"Waiting {settings.report_interval}s until next report...")
                await asyncio.sleep(settings.report_interval)

                if self.running:
                    await self.generate_report()

        except KeyboardInterrupt:
            logger.info("Received interrupt signal, shutting down...")
        except Exception as e:
            logger.error(f"Error in continuous loop: {e}", exc_info=True)
        finally:
            await self.cleanup()

    async def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up resources...")

        for exchange in self.exchanges:
            try:
                await exchange.close()
            except Exception as e:
                logger.error(f"Error closing exchange: {e}")

        logger.info("Cleanup complete")

    def stop(self):
        """Stop the continuous reporting loop"""
        logger.info("Stopping reporter...")
        self.running = False


async def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description='CEX Portfolio Reporter')
    parser.add_argument(
        '--mode',
        choices=['once', 'continuous', 'refresh'],
        default='once',
        help='Run mode: once (single report), continuous (scheduled reports), or refresh (data collection only, no Slack)'
    )
    parser.add_argument(
        '--mock',
        action='store_true',
        help='Force mock mode (overrides environment variable)'
    )

    args = parser.parse_args()

    # Override mock mode if specified
    if args.mock:
        import os
        os.environ['MOCK_MODE'] = 'true'
        logger.info("Mock mode enabled via command line")

    # Display configuration
    logger.info("=" * 60)
    logger.info("CEX REPORTER CONFIGURATION")
    logger.info("=" * 60)
    config = settings.to_dict()
    for key, value in config.items():
        logger.info(f"  {key}: {value}")
    logger.info("=" * 60)

    # Create and run reporter
    reporter = CEXReporter()

    try:
        if args.mode == 'once':
            logger.info("Running in ONCE mode (single report)")
            await reporter.run_once()
        elif args.mode == 'continuous':
            logger.info("Running in CONTINUOUS mode (scheduled reports)")
            await reporter.run_continuous()
        elif args.mode == 'refresh':
            logger.info("Running in REFRESH mode (data collection only, no Slack)")
            await reporter.run_refresh()
        else:
            logger.error(f"Unknown mode: {args.mode}")
            return 1

    except KeyboardInterrupt:
        logger.info("\nShutdown requested by user")
        reporter.stop()
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        return 1

    logger.info("CEX Reporter terminated")
    return 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
