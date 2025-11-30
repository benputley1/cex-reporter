"""
Configuration management for CEX Reporter
Loads environment variables and validates configuration
"""
import os
from typing import Dict, Any, Optional, List
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables"""

    def __init__(self):
        # Skip validation in mock mode
        if not self.mock_mode:
            self._validate_required_vars()

    # Exchange API Keys - Multi-Account Support
    @property
    def mexc_accounts(self) -> list[Dict[str, str]]:
        """Get all MEXC account configurations"""
        accounts = []
        account_names = ['MM1', 'MM2', 'TM1']

        for account_name in account_names:
            key = os.getenv(f'MEXC_{account_name}_API_KEY', '')
            secret = os.getenv(f'MEXC_{account_name}_API_SECRET', '')

            # Only add if credentials exist
            if key and secret:
                accounts.append({
                    'account_name': account_name,
                    'apiKey': key,
                    'secret': secret,
                })

        # In mock mode, provide default accounts if none configured
        if not accounts and self.mock_mode:
            for account_name in account_names:
                accounts.append({
                    'account_name': account_name,
                    'apiKey': f'mock_{account_name.lower()}_key',
                    'secret': f'mock_{account_name.lower()}_secret',
                })

        return accounts

    @property
    def mexc_config(self) -> Dict[str, str]:
        """Legacy single-account config (uses first account)"""
        accounts = self.mexc_accounts
        if accounts:
            return {
                'apiKey': accounts[0]['apiKey'],
                'secret': accounts[0]['secret'],
            }
        return {
            'apiKey': os.getenv('MEXC_API_KEY', ''),
            'secret': os.getenv('MEXC_API_SECRET', ''),
        }

    @property
    def kraken_accounts(self) -> list[Dict[str, str]]:
        """Get all Kraken account configurations"""
        accounts = []

        # Support multiple accounts with naming pattern: KRAKEN_{ACCOUNT}_API_KEY
        account_names = ['MAIN', 'MM1', 'MM2', 'TM']

        for account_name in account_names:
            key = os.getenv(f'KRAKEN_{account_name}_API_KEY', '')
            secret = os.getenv(f'KRAKEN_{account_name}_SECRET', '')

            if key and secret:
                accounts.append({
                    'account_name': account_name,
                    'apiKey': key,
                    'secret': secret,
                })

        # Fallback to legacy single account format
        if not accounts:
            key = os.getenv('KRAKEN_API_KEY', '')
            secret = os.getenv('KRAKEN_API_SECRET', '')

            if key and secret:
                accounts.append({
                    'account_name': 'MAIN',
                    'apiKey': key,
                    'secret': secret,
                })

        # In mock mode, provide default account if none configured
        if not accounts and self.mock_mode:
            accounts.append({
                'account_name': 'MAIN',
                'apiKey': 'mock_kraken_key',
                'secret': 'mock_kraken_secret',
            })

        return accounts

    @property
    def kraken_config(self) -> Dict[str, str]:
        """Legacy single-account config"""
        return {
            'apiKey': os.getenv('KRAKEN_API_KEY', ''),
            'secret': os.getenv('KRAKEN_API_SECRET', ''),
        }

    @property
    def kucoin_accounts(self) -> list[Dict[str, str]]:
        """Get all KuCoin account configurations"""
        accounts = []
        account_names = ['MM1', 'MM2']

        # Check for multiple accounts (MM1, MM2)
        for account_name in account_names:
            key = os.getenv(f'KUCOIN_{account_name}_API_KEY', '')
            secret = os.getenv(f'KUCOIN_{account_name}_API_SECRET', '')
            password = os.getenv(f'KUCOIN_{account_name}_API_PASSPHRASE', '')

            # Only add if credentials exist
            if key and secret and password:
                accounts.append({
                    'account_name': account_name,
                    'apiKey': key,
                    'secret': secret,
                    'password': password,
                })

        # Fallback: Check for standard single account (MAIN)
        if not accounts:
            key = os.getenv('KUCOIN_API_KEY', '')
            secret = os.getenv('KUCOIN_API_SECRET', '')
            password = os.getenv('KUCOIN_API_PASSPHRASE', '')

            if key and secret and password:
                accounts.append({
                    'account_name': 'MAIN',
                    'apiKey': key,
                    'secret': secret,
                    'password': password,
                })

        # In mock mode, provide default accounts if none configured
        if not accounts and self.mock_mode:
            for account_name in account_names:
                accounts.append({
                    'account_name': account_name,
                    'apiKey': f'mock_{account_name.lower()}_key',
                    'secret': f'mock_{account_name.lower()}_secret',
                    'password': f'mock_{account_name.lower()}_pass',
                })

        return accounts

    @property
    def kucoin_config(self) -> Dict[str, str]:
        """Legacy single-account config"""
        return {
            'apiKey': os.getenv('KUCOIN_API_KEY', ''),
            'secret': os.getenv('KUCOIN_API_SECRET', ''),
            'password': os.getenv('KUCOIN_API_PASSPHRASE', ''),
        }

    @property
    def gateio_accounts(self) -> list[Dict[str, str]]:
        """Get all Gate.io account configurations"""
        accounts = []
        account_names = ['MM1', 'MM2', 'TM']

        for account_name in account_names:
            key = os.getenv(f'GATEIO_{account_name}_API_KEY', '')
            secret = os.getenv(f'GATEIO_{account_name}_API_SECRET', '')

            # Only add if credentials exist
            if key and secret:
                accounts.append({
                    'account_name': account_name,
                    'apiKey': key,
                    'secret': secret,
                })

        # In mock mode, provide default accounts if none configured
        if not accounts and self.mock_mode:
            for account_name in account_names:
                accounts.append({
                    'account_name': account_name,
                    'apiKey': f'mock_{account_name.lower()}_key',
                    'secret': f'mock_{account_name.lower()}_secret',
                })

        return accounts

    @property
    def gateio_config(self) -> Dict[str, str]:
        """Legacy single-account config (uses first account)"""
        accounts = self.gateio_accounts
        if accounts:
            return {
                'apiKey': accounts[0]['apiKey'],
                'secret': accounts[0]['secret'],
            }
        return {
            'apiKey': os.getenv('GATEIO_API_KEY', ''),
            'secret': os.getenv('GATEIO_API_SECRET', ''),
        }

    # Cetus Protocol Configuration (DeFi)
    @property
    def cetus_enabled(self) -> bool:
        """Enable Cetus protocol tracking"""
        return os.getenv('CETUS_ENABLED', 'false').lower() in ('true', '1', 'yes')

    @property
    def cetus_wallet_address(self) -> str:
        """Sui wallet address for Cetus positions"""
        return os.getenv('CETUS_WALLET_ADDRESS', '')

    @property
    def cetus_config(self) -> Dict[str, str]:
        """Cetus configuration"""
        return {
            'wallet_address': self.cetus_wallet_address,
        }

    # Slack Configuration
    @property
    def slack_webhook_url(self) -> str:
        return os.getenv('SLACK_WEBHOOK_URL', '')

    # Application Settings
    @property
    def mock_mode(self) -> bool:
        """Enable mock mode for testing without API keys"""
        return os.getenv('MOCK_MODE', 'true').lower() in ('true', '1', 'yes')

    @property
    def log_level(self) -> str:
        return os.getenv('LOG_LEVEL', 'INFO').upper()

    @property
    def cache_ttl(self) -> int:
        """Cache TTL in seconds"""
        return int(os.getenv('CACHE_TTL', '60'))

    @property
    def report_interval(self) -> int:
        """Report interval in seconds (default: 4 hours)"""
        return int(os.getenv('REPORT_INTERVAL', '14400'))

    @property
    def alert_threshold_percent(self) -> float:
        """Alert threshold as percentage"""
        return float(os.getenv('ALERT_THRESHOLD_PERCENT', '5.0'))

    @property
    def base_currency(self) -> str:
        """Base currency for reporting (e.g., USD)"""
        return os.getenv('BASE_CURRENCY', 'USD')

    @property
    def coingecko_api_key(self) -> Optional[str]:
        """Optional CoinGecko API key for higher rate limits"""
        return os.getenv('COINGECKO_API_KEY')

    @property
    def tracked_assets(self) -> list:
        """List of assets to track across exchanges"""
        assets_str = os.getenv('TRACKED_ASSETS', 'USDT,ALKIMI')
        return [asset.strip().upper() for asset in assets_str.split(',')]

    @property
    def historical_start_date(self) -> str:
        """Start date for historical trade data (YYYY-MM-DD)"""
        return os.getenv('HISTORICAL_START_DATE', '2025-08-19')

    # Path Configuration (for deployment flexibility)
    @property
    def trade_cache_db(self) -> str:
        """Path to trade cache SQLite database"""
        return os.getenv('TRADE_CACHE_DB', 'data/trade_cache.db')

    @property
    def log_dir(self) -> str:
        """Directory for log files"""
        return os.getenv('LOG_DIR', 'logs')

    @property
    def data_dir(self) -> str:
        """Directory for data files"""
        return os.getenv('DATA_DIR', 'data')

    @property
    def deposits_file(self) -> str:
        """Path to deposits & withdrawals Excel file"""
        return os.getenv('DEPOSITS_FILE', 'deposits & withdrawals.xlsx')

    # Sui Blockchain Configuration
    @property
    def sui_config(self) -> Dict[str, Any]:
        """Get Sui blockchain configuration for DEX monitoring"""
        return {
            'rpc_url': os.getenv('SUI_RPC_URL', 'https://fullnode.mainnet.sui.io'),
            'token_contract': os.getenv('ALKIMI_TOKEN_CONTRACT', ''),
            'wallets': self._parse_sui_wallets()
        }

    def _parse_sui_wallets(self) -> List[Dict[str, str]]:
        """Parse SUI_WALLET_* environment variables into wallet list"""
        wallets = []
        for key, value in os.environ.items():
            if key.startswith('SUI_WALLET_') and value:
                name = key.replace('SUI_WALLET_', '')
                wallets.append({'address': value, 'name': name})
        return wallets

    # Claude AI Configuration
    @property
    def claude_config(self) -> Dict[str, Any]:
        """Get Claude AI analysis configuration"""
        return {
            'api_key': os.getenv('ANTHROPIC_API_KEY', ''),
            'model': os.getenv('CLAUDE_MODEL', 'claude-sonnet-4-20250514'),
            'enabled': os.getenv('CLAUDE_ANALYSIS_ENABLED', 'false').lower() == 'true',
            'interval': int(os.getenv('CLAUDE_ANALYSIS_INTERVAL', '3600'))
        }

    # Slack Bot Configuration
    @property
    def slack_bot_config(self) -> Dict[str, str]:
        """Get Slack bot configuration"""
        return {
            'bot_token': os.getenv('SLACK_BOT_TOKEN', ''),
            'app_token': os.getenv('SLACK_APP_TOKEN', ''),
            'signing_secret': os.getenv('SLACK_SIGNING_SECRET', '')
        }

    @property
    def asset_mapping(self) -> Dict[str, Dict[str, str]]:
        """
        Exchange-specific asset mappings.
        Maps standard asset names to exchange-specific symbols.

        Example: Kraken uses 'USD' instead of 'USDT'
        """
        return {
            'kraken': {
                'USDT': 'USD',  # Kraken lists USD (fiat) not USDT
            }
        }

    def get_exchange_asset(self, exchange: str, asset: str) -> str:
        """
        Get the exchange-specific asset symbol.

        Args:
            exchange: Exchange name (lowercase)
            asset: Standard asset symbol (e.g., 'USDT')

        Returns:
            Exchange-specific symbol (e.g., 'USD' for Kraken)
        """
        exchange_lower = exchange.lower()
        if exchange_lower in self.asset_mapping:
            return self.asset_mapping[exchange_lower].get(asset, asset)
        return asset

    def _validate_required_vars(self):
        """Validate that at least one exchange account is configured"""

        # Check if at least one exchange has accounts configured
        exchanges_with_accounts = []

        if self.mexc_accounts:
            exchanges_with_accounts.append('MEXC')
        if self.kraken_accounts:
            exchanges_with_accounts.append('Kraken')
        if self.kucoin_accounts:
            exchanges_with_accounts.append('KuCoin')
        if self.gateio_accounts:
            exchanges_with_accounts.append('Gate.io')

        if not exchanges_with_accounts:
            raise ValueError(
                "No exchange accounts configured. Please add API credentials for at least one exchange.\n"
                "Expected format in .env:\n"
                "  MEXC: MEXC_MM1_API_KEY, MEXC_MM1_API_SECRET (or MM2, TM1)\n"
                "  Gate.io: GATEIO_MM1_API_KEY, GATEIO_MM1_API_SECRET (or MM2, TM)\n"
                "  Kraken: KRAKEN_API_KEY, KRAKEN_API_SECRET\n"
                "  KuCoin: KUCOIN_API_KEY, KUCOIN_API_SECRET, KUCOIN_API_PASSPHRASE"
            )

        # Validate Slack webhook
        if not self.slack_webhook_url or 'YOUR/WEBHOOK/URL' in self.slack_webhook_url:
            print("⚠️  Warning: Slack webhook not configured. Notifications will not be sent.")

        print(f"✓ Validated: {', '.join(exchanges_with_accounts)} configured")

    def get_exchange_config(self, exchange_name: str) -> Dict[str, str]:
        """Get configuration for a specific exchange (legacy single-account)"""
        exchange_configs = {
            'mexc': self.mexc_config,
            'kraken': self.kraken_config,
            'kucoin': self.kucoin_config,
            'gateio': self.gateio_config,
        }

        config = exchange_configs.get(exchange_name.lower())
        if not config:
            raise ValueError(f"Unknown exchange: {exchange_name}")

        return config

    def get_exchange_accounts(self, exchange_name: str) -> list[Dict[str, str]]:
        """Get all account configurations for a specific exchange"""
        exchange_accounts = {
            'mexc': self.mexc_accounts,
            'kraken': self.kraken_accounts,
            'kucoin': self.kucoin_accounts,
            'gateio': self.gateio_accounts,
        }

        accounts = exchange_accounts.get(exchange_name.lower())
        if accounts is None:
            raise ValueError(f"Unknown exchange: {exchange_name}")

        return accounts

    def to_dict(self) -> Dict[str, Any]:
        """Export settings as dictionary (excluding sensitive data)"""
        exchanges = ['mexc', 'kraken', 'kucoin', 'gateio']
        if self.cetus_enabled:
            exchanges.append('cetus')

        return {
            'mock_mode': self.mock_mode,
            'log_level': self.log_level,
            'cache_ttl': self.cache_ttl,
            'report_interval': self.report_interval,
            'alert_threshold_percent': self.alert_threshold_percent,
            'base_currency': self.base_currency,
            'exchanges': exchanges,
            'tracked_assets': self.tracked_assets,
            'historical_start_date': self.historical_start_date,
            'cetus_enabled': self.cetus_enabled,
        }


# Global settings instance
settings = Settings()
