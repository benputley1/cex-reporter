#!/usr/bin/env python3
"""
Backfill Kraken Trade History

Fetches all available Kraken trades from historical_start_date (August 15, 2025)
to present and caches them in the trade database.

Usage:
    python scripts/backfill_kraken_trades.py
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from config.settings import settings
from src.exchanges.kraken import KrakenClient
from src.data import TradeCache
from src.utils.logging import setup_from_config, get_logger

# Set up logging
setup_from_config()
logger = get_logger(__name__)


async def backfill_kraken_account(account_config: dict, account_name: str, cache: TradeCache):
    """Backfill trades for a single Kraken account"""

    logger.info(f"=" * 60)
    logger.info(f"Processing Kraken account: {account_name}")
    logger.info(f"=" * 60)

    kraken = None
    try:
        # Initialize Kraken client
        kraken = KrakenClient(config=account_config, account_name=account_name)
        await kraken.initialize()
        logger.info(f"✓ Kraken ({account_name}) client initialized")

        # Fetch trades from historical start date
        since = datetime.fromisoformat(settings.historical_start_date)
        logger.info(f"Fetching trades since {since}...")

        trades = await kraken.get_trades(since=since)
        logger.info(f"✓ Fetched {len(trades)} trades from API")

        if not trades:
            logger.warning(f"No trades found for {account_name}")
            return 0

        # Display trade date range
        trades_sorted = sorted(trades, key=lambda t: t.timestamp)
        first_trade = trades_sorted[0]
        last_trade = trades_sorted[-1]
        logger.info(f"Trade date range: {first_trade.timestamp} to {last_trade.timestamp}")

        # Cache trades
        new_count = cache.save_trades(trades, 'kraken', account_name)
        logger.info(f"✓ Cached {new_count} new trades (duplicates filtered)")

        return new_count

    except Exception as e:
        logger.error(f"✗ Error processing {account_name}: {e}", exc_info=True)
        return 0

    finally:
        if kraken:
            await kraken.close()
            logger.info(f"✓ {account_name} client closed")


async def main():
    """Main backfill process"""

    logger.info("=" * 60)
    logger.info("KRAKEN TRADE HISTORY BACKFILL")
    logger.info("=" * 60)
    logger.info(f"Historical start date: {settings.historical_start_date}")
    logger.info(f"Target: Fetch all Kraken trades and cache in database")
    logger.info("")

    # Initialize trade cache
    cache = TradeCache()

    # Get all configured Kraken accounts
    accounts = settings.get_exchange_accounts('kraken')

    if not accounts:
        logger.error("No Kraken accounts configured in settings!")
        return

    logger.info(f"Found {len(accounts)} Kraken account(s) configured")
    logger.info("")

    # Process each account
    total_new_trades = 0
    for account_config in accounts:
        account_name = account_config['account_name']
        new_trades = await backfill_kraken_account(account_config, account_name, cache)
        total_new_trades += new_trades
        logger.info("")

    # Summary
    logger.info("=" * 60)
    logger.info("BACKFILL COMPLETE")
    logger.info("=" * 60)

    # Query database for final stats
    all_kraken_trades = cache.get_trades(exchange='kraken')

    logger.info(f"Total new trades cached: {total_new_trades}")
    logger.info(f"Total Kraken trades in database: {len(all_kraken_trades)}")

    if all_kraken_trades:
        # Sort by timestamp
        all_kraken_trades_sorted = sorted(all_kraken_trades, key=lambda t: t.timestamp)
        first = all_kraken_trades_sorted[0]
        last = all_kraken_trades_sorted[-1]

        logger.info(f"Date range: {first.timestamp} to {last.timestamp}")
        logger.info("")

        # Breakdown by account
        logger.info("Breakdown by account:")
        accounts_in_db = {}
        for trade in all_kraken_trades:
            acc = trade.account_name or 'UNKNOWN'
            accounts_in_db[acc] = accounts_in_db.get(acc, 0) + 1

        for account_name, count in sorted(accounts_in_db.items()):
            logger.info(f"  {account_name}: {count} trades")

        logger.info("")

        # Breakdown by side (buy/sell)
        buys = sum(1 for t in all_kraken_trades if t.side.value == 'BUY')
        sells = sum(1 for t in all_kraken_trades if t.side.value == 'SELL')
        logger.info(f"Buy/Sell distribution:")
        logger.info(f"  Buys:  {buys} ({buys/len(all_kraken_trades)*100:.1f}%)")
        logger.info(f"  Sells: {sells} ({sells/len(all_kraken_trades)*100:.1f}%)")

    else:
        logger.warning("No Kraken trades found in database after backfill!")
        logger.warning("This could mean:")
        logger.warning("  1. No trades were executed on Kraken accounts")
        logger.warning("  2. API credentials are not configured")
        logger.warning("  3. Trades are outside the API retention period")

    logger.info("=" * 60)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\nBackfill interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)
