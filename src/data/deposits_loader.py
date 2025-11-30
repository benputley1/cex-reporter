"""
Deposits & Withdrawals Loader Module
Loads initial ALKIMI deposit data from Excel to establish cost basis,
and stablecoin withdrawal data for accurate P&L calculation.
"""

import os
from typing import Dict, List, Optional
from datetime import datetime
import pandas as pd

from src.utils import get_logger

logger = get_logger(__name__)


class DepositsLoader:
    """Loads and manages initial deposit data for cost basis calculation."""

    def __init__(self, excel_path: Optional[str] = None):
        """
        Initialize the deposits loader.

        Args:
            excel_path: Path to the deposits Excel file.
                       Defaults to DEPOSITS_FILE env var or 'deposits & withdrawals.xlsx'
        """
        if excel_path is None:
            # Use environment variable or default
            excel_path = os.getenv('DEPOSITS_FILE', 'deposits & withdrawals.xlsx')
            # If it's a relative path, resolve from project root
            if not os.path.isabs(excel_path):
                project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
                excel_path = os.path.join(project_root, excel_path)

        self.excel_path = excel_path
        self._deposits_cache = None
        self._withdrawals_cache = None

        logger.info(f"DepositsLoader initialized with path: {self.excel_path}")

    def load_initial_deposits(self) -> Dict[str, Dict]:
        """
        Load initial ALKIMI deposits from Excel file.

        Returns:
            Dictionary structured as:
            {
                'ALKIMI': {
                    'total_amount': 19002000.0,
                    'total_cost': 1988036.37,
                    'avg_price': 0.104622,
                    'deposits': [
                        {
                            'date': datetime(...),
                            'destination': 'MEXC Artis MM',
                            'amount': 5001000.0,
                            'cost': 414294.09,
                            'price': 0.082842
                        },
                        ...
                    ]
                }
            }

        Raises:
            FileNotFoundError: If Excel file doesn't exist
            ValueError: If Excel file is malformed
        """
        if self._deposits_cache is not None:
            return self._deposits_cache

        if not os.path.exists(self.excel_path):
            logger.error(f"Deposits Excel file not found: {self.excel_path}")
            raise FileNotFoundError(f"Deposits Excel file not found: {self.excel_path}")

        try:
            logger.info("Loading deposits from Excel file")
            df = pd.read_excel(self.excel_path, sheet_name='Deposits od ALKIMI to exchanges')

            deposits_by_asset = {}

            # Process ALKIMI deposits
            alkimi_deposits = []
            total_amount = 0.0
            total_cost = 0.0

            for _, row in df.iterrows():
                amount = float(row['Amount'])
                cost = float(row['USD Amount'])
                price = cost / amount if amount > 0 else 0

                deposit = {
                    'date': pd.to_datetime(row['Date']),
                    'destination': row['Destination'],
                    'amount': amount,
                    'cost': cost,
                    'price': price,
                    'fireblocks_txid': row['Fireblocks TxId']
                }

                alkimi_deposits.append(deposit)
                total_amount += amount
                total_cost += cost

            avg_price = total_cost / total_amount if total_amount > 0 else 0

            deposits_by_asset['ALKIMI'] = {
                'total_amount': total_amount,
                'total_cost': total_cost,
                'avg_price': avg_price,
                'deposits': alkimi_deposits
            }

            logger.info(
                f"Loaded {len(alkimi_deposits)} ALKIMI deposits: "
                f"{total_amount:,.0f} ALKIMI worth ${total_cost:,.2f} "
                f"(avg ${avg_price:.6f}/ALKIMI)"
            )

            self._deposits_cache = deposits_by_asset
            return deposits_by_asset

        except Exception as e:
            logger.error(f"Error loading deposits from Excel: {str(e)}")
            raise ValueError(f"Failed to load deposits from Excel: {str(e)}")

    def get_deposit_summary(self) -> Dict:
        """
        Get a summary of deposits by exchange.

        Returns:
            Dictionary with deposit amounts by destination exchange
        """
        deposits = self.load_initial_deposits()

        summary = {}
        for asset, data in deposits.items():
            by_exchange = {}
            for deposit in data['deposits']:
                dest = deposit['destination']
                if dest not in by_exchange:
                    by_exchange[dest] = {
                        'amount': 0.0,
                        'cost': 0.0
                    }
                by_exchange[dest]['amount'] += deposit['amount']
                by_exchange[dest]['cost'] += deposit['cost']

            summary[asset] = by_exchange

        return summary

    def get_total_deposit_cost_basis(self, asset: str) -> tuple[float, float]:
        """
        Get total deposit amount and cost basis for an asset.

        Args:
            asset: Asset symbol (e.g., 'ALKIMI')

        Returns:
            Tuple of (total_amount, total_cost)
        """
        deposits = self.load_initial_deposits()

        if asset not in deposits:
            logger.warning(f"No deposits found for asset: {asset}")
            return (0.0, 0.0)

        data = deposits[asset]
        return (data['total_amount'], data['total_cost'])

    def load_withdrawals(self) -> Dict[str, Dict]:
        """
        Load stablecoin withdrawals from Excel file.

        Returns:
            Dictionary structured as:
            {
                'USDT': {
                    'total_amount': 602922.20,
                    'withdrawals': [
                        {
                            'date': datetime(...),
                            'source': 'Kraken Main',
                            'amount': 50000.0,
                            'blockchain_txid': '0x...'
                        },
                        ...
                    ]
                }
            }

        Raises:
            FileNotFoundError: If Excel file doesn't exist
            ValueError: If Excel file is malformed
        """
        if self._withdrawals_cache is not None:
            return self._withdrawals_cache

        if not os.path.exists(self.excel_path):
            logger.error(f"Withdrawals Excel file not found: {self.excel_path}")
            raise FileNotFoundError(f"Withdrawals Excel file not found: {self.excel_path}")

        try:
            logger.info("Loading withdrawals from Excel file")
            df = pd.read_excel(self.excel_path, sheet_name='Stablecoin Withdrawals from Exc')

            # Filter out duplicate entries - only keep rows with a From_Nametag (actual source)
            # Each withdrawal appears twice: once with N/A and once with the source exchange
            df = df[pd.notna(df['From_Nametag'])]
            logger.debug(f"Filtered to {len(df)} unique withdrawals (removed N/A duplicates)")

            withdrawals_by_asset = {}

            # Extract asset name from Token column (e.g., "Tether USD(USDT)" -> "USDT")
            # Parse token names and group by asset
            for _, row in df.iterrows():
                # Extract asset from token name (e.g., "Tether USD(USDT)" -> "USDT")
                token_str = str(row['Token'])
                if '(' in token_str and ')' in token_str:
                    asset = token_str[token_str.find('(')+1:token_str.find(')')]
                else:
                    asset = token_str.strip()

                # Parse the amount from Value (USD) column
                # Remove dollar sign and commas from formatted strings like "$55,057.45"
                value_str = str(row['Value (USD)'])
                if pd.notna(row['Value (USD)']):
                    # Remove '$' and ',' characters
                    value_str = value_str.replace('$', '').replace(',', '').strip()
                    amount = float(value_str)
                else:
                    amount = 0.0

                withdrawal = {
                    'date': pd.to_datetime(row['DateTime (UTC)']),
                    'source': row['From_Nametag'] if pd.notna(row['From_Nametag']) else row['From'],
                    'amount': amount,
                    'blockchain_txid': row['Transaction Hash']
                }

                # Initialize asset if not seen before
                if asset not in withdrawals_by_asset:
                    withdrawals_by_asset[asset] = {
                        'total_amount': 0.0,
                        'withdrawals': []
                    }

                withdrawals_by_asset[asset]['withdrawals'].append(withdrawal)
                withdrawals_by_asset[asset]['total_amount'] += amount

            # Log summary for each asset
            for asset, data in withdrawals_by_asset.items():
                logger.info(
                    f"Loaded {len(data['withdrawals'])} {asset} withdrawals: "
                    f"${data['total_amount']:,.2f} total"
                )

            self._withdrawals_cache = withdrawals_by_asset
            return withdrawals_by_asset

        except Exception as e:
            logger.error(f"Error loading withdrawals from Excel: {str(e)}")
            raise ValueError(f"Failed to load withdrawals from Excel: {str(e)}")

    def get_total_withdrawals(self) -> float:
        """
        Get total USD value of all stablecoin withdrawals.

        Returns:
            Total withdrawal amount in USD
        """
        withdrawals = self.load_withdrawals()

        total = 0.0
        for asset, data in withdrawals.items():
            # For stablecoins, amount = USD value
            total += data['total_amount']

        return total

    def get_withdrawal_summary(self) -> Dict:
        """
        Get a summary of withdrawals by exchange.

        Returns:
            Dictionary with withdrawal amounts by source exchange
        """
        withdrawals = self.load_withdrawals()

        summary = {}
        for asset, data in withdrawals.items():
            by_exchange = {}
            for withdrawal in data['withdrawals']:
                source = withdrawal['source']
                if source not in by_exchange:
                    by_exchange[source] = {
                        'amount': 0.0
                    }
                by_exchange[source]['amount'] += withdrawal['amount']

            summary[asset] = by_exchange

        return summary

    def clear_cache(self):
        """Clear the cached deposits and withdrawals data."""
        self._deposits_cache = None
        self._withdrawals_cache = None
        logger.debug("Deposits and withdrawals cache cleared")
