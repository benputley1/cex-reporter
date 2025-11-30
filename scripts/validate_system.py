#!/usr/bin/env python3
"""
System Validation Script

Validates the entire CEX + DEX reporter system including:
- Configuration completeness
- Exchange connectivity
- Data integrity
- Slack connectivity
- Claude AI integration (if enabled)

Usage:
    python scripts/validate_system.py
    python scripts/validate_system.py --verbose
    python scripts/validate_system.py --skip-slack
"""

import asyncio
import sys
import os
import argparse
from datetime import datetime, timedelta

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from config.settings import settings
from src.utils import get_logger

logger = get_logger(__name__)


class SystemValidator:
    """Validates the CEX + DEX reporter system."""

    def __init__(self, verbose: bool = False, skip_slack: bool = False):
        self.verbose = verbose
        self.skip_slack = skip_slack
        self.results = {
            'passed': [],
            'failed': [],
            'warnings': []
        }

    def log(self, message: str, level: str = 'info'):
        """Log with optional verbosity."""
        if level == 'info':
            print(f"  {message}")
        elif level == 'success':
            print(f"  \033[92m✓\033[0m {message}")
        elif level == 'fail':
            print(f"  \033[91m✗\033[0m {message}")
        elif level == 'warn':
            print(f"  \033[93m!\033[0m {message}")
        elif level == 'verbose' and self.verbose:
            print(f"    {message}")

    def pass_check(self, name: str, detail: str = ''):
        """Record a passed check."""
        self.results['passed'].append({'name': name, 'detail': detail})
        self.log(f"{name}: {detail}" if detail else name, 'success')

    def fail_check(self, name: str, detail: str = ''):
        """Record a failed check."""
        self.results['failed'].append({'name': name, 'detail': detail})
        self.log(f"{name}: {detail}" if detail else name, 'fail')

    def warn_check(self, name: str, detail: str = ''):
        """Record a warning."""
        self.results['warnings'].append({'name': name, 'detail': detail})
        self.log(f"{name}: {detail}" if detail else name, 'warn')

    async def run_all_checks(self):
        """Run all validation checks."""
        print("\n" + "=" * 60)
        print("ALKIMI CEX + DEX REPORTER - SYSTEM VALIDATION")
        print("=" * 60)

        # 1. Configuration checks
        print("\n[1] CONFIGURATION")
        print("-" * 40)
        self.check_configuration()

        # 2. Exchange connectivity
        print("\n[2] EXCHANGE CONNECTIVITY")
        print("-" * 40)
        await self.check_exchanges()

        # 3. DEX/Sui configuration
        print("\n[3] SUI DEX CONFIGURATION")
        print("-" * 40)
        self.check_sui_config()

        # 4. Trade cache
        print("\n[4] TRADE CACHE")
        print("-" * 40)
        await self.check_trade_cache()

        # 5. Slack connectivity
        print("\n[5] SLACK INTEGRATION")
        print("-" * 40)
        if self.skip_slack:
            self.warn_check("Slack", "Skipped (--skip-slack flag)")
        else:
            await self.check_slack()

        # 6. Claude AI (optional)
        print("\n[6] CLAUDE AI INTEGRATION")
        print("-" * 40)
        await self.check_claude()

        # Summary
        self.print_summary()

        return len(self.results['failed']) == 0

    def check_configuration(self):
        """Check configuration completeness."""
        # Check required env vars
        required_vars = ['SLACK_WEBHOOK_URL']
        for var in required_vars:
            if os.getenv(var):
                self.pass_check(var, "Configured")
            else:
                self.fail_check(var, "Missing")

        # Check exchange configs
        exchanges = ['mexc', 'kraken', 'kucoin', 'gateio']
        for exchange in exchanges:
            accounts = settings.get_exchange_accounts(exchange)
            if accounts:
                self.pass_check(f"{exchange.upper()}", f"{len(accounts)} account(s)")
            else:
                self.warn_check(f"{exchange.upper()}", "No accounts configured")

        # Check paths
        trade_cache_path = settings.trade_cache_db
        self.log(f"Trade cache path: {trade_cache_path}", 'verbose')
        if os.path.exists(os.path.dirname(trade_cache_path)) or trade_cache_path.startswith('data/'):
            self.pass_check("Trade cache path", "Valid")
        else:
            self.warn_check("Trade cache path", f"Directory may not exist: {trade_cache_path}")

    async def check_exchanges(self):
        """Test connectivity to each configured exchange."""
        from src.exchanges.mexc import MEXCClient
        from src.exchanges.kraken import KrakenClient
        from src.exchanges.kucoin import KuCoinClient
        from src.exchanges.gateio import GateioClient

        exchange_classes = [
            ('mexc', 'MEXC', MEXCClient),
            ('kraken', 'Kraken', KrakenClient),
            ('kucoin', 'KuCoin', KuCoinClient),
            ('gateio', 'Gate.io', GateioClient),
        ]

        for exchange_key, display_name, exchange_class in exchange_classes:
            accounts = settings.get_exchange_accounts(exchange_key)
            if not accounts:
                self.log(f"{display_name}: Skipped (not configured)", 'verbose')
                continue

            # Test first account only to avoid rate limits
            account_config = accounts[0]
            account_name = account_config['account_name']

            try:
                exchange = exchange_class(
                    config=account_config,
                    account_name=account_name
                )
                await exchange.initialize()

                # Try to fetch balances
                balances = await exchange.get_balances()
                await exchange.close()

                alkimi_balance = balances.get('ALKIMI', {}).get('total', 0)
                usdt_balance = balances.get('USDT', {}).get('total', 0)

                self.pass_check(
                    f"{display_name} ({account_name})",
                    f"ALKIMI: {alkimi_balance:,.0f}, USDT: ${usdt_balance:,.2f}"
                )

            except Exception as e:
                self.fail_check(f"{display_name} ({account_name})", str(e)[:50])

    def check_sui_config(self):
        """Check Sui DEX configuration."""
        sui_config = settings.sui_config

        rpc_url = sui_config.get('rpc_url')
        if rpc_url:
            self.pass_check("Sui RPC URL", rpc_url[:50])
        else:
            self.warn_check("Sui RPC URL", "Not configured (DEX monitoring disabled)")

        token_contract = sui_config.get('token_contract')
        if token_contract:
            self.pass_check("ALKIMI Token Contract", token_contract[:20] + "...")
        else:
            self.warn_check("ALKIMI Token Contract", "Not configured (DEX monitoring disabled)")

        wallets = sui_config.get('wallets', [])
        if wallets:
            self.pass_check("Treasury Wallets", f"{len(wallets)} wallet(s)")
        else:
            self.warn_check("Treasury Wallets", "Not configured")

    async def check_trade_cache(self):
        """Check trade cache health."""
        from src.data import TradeCache

        try:
            cache = TradeCache()

            # Get cache stats
            since = datetime.now() - timedelta(days=30)
            trades = cache.get_trades(since=since)

            if trades:
                oldest = min(t.timestamp for t in trades)
                newest = max(t.timestamp for t in trades)
                self.pass_check(
                    "Trade cache",
                    f"{len(trades)} trades from {oldest.date()} to {newest.date()}"
                )
            else:
                self.warn_check("Trade cache", "Empty (no trades in last 30 days)")

            # Check unique exchanges
            exchanges = set(t.exchange for t in trades)
            self.log(f"Exchanges in cache: {', '.join(exchanges)}", 'verbose')

        except Exception as e:
            self.fail_check("Trade cache", str(e))

    async def check_slack(self):
        """Check Slack connectivity."""
        from src.reporting import get_slack_client

        try:
            slack = get_slack_client()

            # Don't actually send a message, just verify config
            if slack.webhook_url:
                self.pass_check("Slack webhook", "Configured")
            else:
                self.fail_check("Slack webhook", "Missing SLACK_WEBHOOK_URL")

        except Exception as e:
            self.fail_check("Slack", str(e))

    async def check_claude(self):
        """Check Claude AI integration."""
        from src.analytics.claude_analyst import ClaudeAnalyst

        claude_config = settings.claude_config

        if not claude_config.get('api_key'):
            self.warn_check("Claude API", "Not configured (AI analysis disabled)")
            return

        if not claude_config.get('enabled'):
            self.warn_check("Claude API", "API key present but disabled")
            return

        try:
            analyst = ClaudeAnalyst()
            success = await analyst.initialize()

            if success:
                self.pass_check("Claude API", f"Model: {claude_config.get('model')}")
            else:
                self.fail_check("Claude API", "Failed to initialize")

            await analyst.close()

        except Exception as e:
            self.fail_check("Claude API", str(e))

    def print_summary(self):
        """Print validation summary."""
        print("\n" + "=" * 60)
        print("VALIDATION SUMMARY")
        print("=" * 60)

        passed = len(self.results['passed'])
        failed = len(self.results['failed'])
        warnings = len(self.results['warnings'])

        print(f"\n  \033[92mPassed:\033[0m   {passed}")
        print(f"  \033[91mFailed:\033[0m   {failed}")
        print(f"  \033[93mWarnings:\033[0m {warnings}")

        if failed > 0:
            print(f"\n\033[91mVALIDATION FAILED\033[0m - {failed} check(s) failed")
            print("\nFailed checks:")
            for item in self.results['failed']:
                print(f"  - {item['name']}: {item['detail']}")
        elif warnings > 0:
            print(f"\n\033[93mVALIDATION PASSED WITH WARNINGS\033[0m")
        else:
            print(f"\n\033[92mVALIDATION PASSED\033[0m - All checks successful")

        print()


async def main():
    parser = argparse.ArgumentParser(description='Validate CEX + DEX Reporter System')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--skip-slack', action='store_true', help='Skip Slack connectivity test')
    args = parser.parse_args()

    validator = SystemValidator(verbose=args.verbose, skip_slack=args.skip_slack)
    success = await validator.run_all_checks()

    return 0 if success else 1


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
