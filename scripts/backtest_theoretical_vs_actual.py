#!/usr/bin/env python3
"""
Backtest: Theoretical Spread Compression vs Actual Trading Performance

Compares what profits COULD have been made using spread compression strategy
against actual trading results for the same time period.

Usage:
    python scripts/backtest_theoretical_vs_actual.py
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Tuple
import pandas as pd
import sqlite3

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.logging import setup_from_config, get_logger

# Set up logging
setup_from_config()
logger = get_logger(__name__)


# Spread compression methodology parameters
INTERVENTION_THRESHOLD = 0.0015  # 0.15% - only trade when spread exceeds this
TARGET_SPREAD = 0.0012  # 0.12% - compress to this level
POSITION_SIZE_PCT = 0.125  # 12.5% of daily volume
CAPITAL_PER_EXCHANGE = 10000  # $10,000 per exchange
FILL_RATE = 0.80  # 80% of theoretical depth
INTRADAY_SPIKE_MULTIPLIER = 2.5  # Capture 2.5x spread during volatile periods
SPIKE_TIME_PCT = 0.30  # Spikes occur 30% of the time
EXECUTIONS_PER_DAY_BASE = 5  # Base executions per day


def load_chart_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the three chart duration CSV files"""
    logger.info("Loading market data from chart_duration CSV files...")

    try:
        # Load spread data (wide format with exchanges as columns)
        spread_wide = pd.read_csv('chart_duration_all_bidAskSpreadRatioByExchange.csv')
        spread_wide['Timestamp'] = pd.to_datetime(spread_wide['Timestamp'])
        # Melt to long format
        spread_df = spread_wide.melt(
            id_vars=['Timestamp'],
            var_name='exchange',
            value_name='bidAskSpreadRatio'
        )
        spread_df = spread_df.rename(columns={'Timestamp': 'date'})
        # Convert from percentage to decimal (e.g., 0.199 -> 0.00199)
        spread_df['bidAskSpreadRatio'] = spread_df['bidAskSpreadRatio'] / 100
        logger.info(f"✓ Loaded spread data: {len(spread_df)} rows")

        # Load depth data (has separate bid and ask columns per exchange)
        depth_wide = pd.read_csv('chart_duration_all_twoSidedDepthByExchange.csv')
        depth_wide['Timestamp'] = pd.to_datetime(depth_wide['Timestamp'])

        # Calculate twoSidedDepth for each exchange by adding bid + ask
        exchanges = ['Kraken', 'Kucoin', 'MEXC', 'Gate.io']
        depth_rows = []
        for _, row in depth_wide.iterrows():
            date = row['Timestamp']
            for exchange in exchanges:
                bid_col = f"{exchange} Bid Depth"
                ask_col = f"{exchange} Ask Depth"

                if bid_col in depth_wide.columns and ask_col in depth_wide.columns:
                    bid = row[bid_col] if pd.notna(row[bid_col]) else 0
                    ask = row[ask_col] if pd.notna(row[ask_col]) else 0
                    # Two-sided depth is the sum of absolute values of bid and ask
                    two_sided = abs(bid) + abs(ask)

                    depth_rows.append({
                        'date': date,
                        'exchange': exchange,
                        'twoSidedDepth': two_sided
                    })

        depth_df = pd.DataFrame(depth_rows)
        logger.info(f"✓ Loaded depth data: {len(depth_df)} rows")

        # Load volume data
        volume_wide = pd.read_csv('chart_duration_all_volumeByExchange.csv')
        volume_wide['Timestamp'] = pd.to_datetime(volume_wide['Timestamp'])
        volume_df = volume_wide.melt(
            id_vars=['Timestamp'],
            var_name='exchange',
            value_name='volume'
        )
        volume_df = volume_df.rename(columns={'Timestamp': 'date'})
        logger.info(f"✓ Loaded volume data: {len(volume_df)} rows")

        return spread_df, depth_df, volume_df

    except Exception as e:
        logger.error(f"Error loading chart data: {e}", exc_info=True)
        raise


def get_actual_trades_date_range() -> Tuple[datetime, datetime]:
    """Query trade_cache.db to get the date range of actual trades"""
    logger.info("Querying trade_cache.db for actual trade date range...")

    try:
        conn = sqlite3.connect('data/trade_cache.db')
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                MIN(timestamp) as first_trade,
                MAX(timestamp) as last_trade,
                COUNT(*) as total_trades
            FROM trades
        """)

        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            first_date = datetime.fromisoformat(row[0])
            last_date = datetime.fromisoformat(row[1])
            total_trades = row[2]

            logger.info(f"✓ Date range: {first_date.date()} to {last_date.date()}")
            logger.info(f"✓ Total trades in database: {total_trades}")

            return first_date, last_date
        else:
            raise ValueError("No trades found in database")

    except Exception as e:
        logger.error(f"Error querying database: {e}")
        raise


def load_actual_trades(start_date: datetime, end_date: datetime) -> pd.DataFrame:
    """Load actual trades from database for the date range"""
    logger.info(f"Loading actual trades from {start_date.date()} to {end_date.date()}...")

    try:
        conn = sqlite3.connect('data/trade_cache.db')

        query = """
            SELECT
                timestamp,
                exchange,
                account_name,
                symbol,
                side,
                amount,
                price,
                fee
            FROM trades
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp
        """

        df = pd.read_sql_query(
            query,
            conn,
            params=(start_date.isoformat(), end_date.isoformat())
        )
        conn.close()

        df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')
        df['date'] = df['timestamp'].dt.date

        logger.info(f"✓ Loaded {len(df)} actual trades")
        logger.info(f"  Exchanges: {df['exchange'].unique().tolist()}")
        logger.info(f"  Date range: {df['date'].min()} to {df['date'].max()}")

        return df

    except Exception as e:
        logger.error(f"Error loading trades: {e}")
        raise


def calculate_theoretical_profits(
    spread_df: pd.DataFrame,
    depth_df: pd.DataFrame,
    volume_df: pd.DataFrame,
    start_date: datetime,
    end_date: datetime
) -> pd.DataFrame:
    """Calculate theoretical profits using spread compression methodology"""
    logger.info("=" * 60)
    logger.info("Calculating Theoretical Spread Compression Profits")
    logger.info("=" * 60)

    # Focus on CEX exchanges
    cex_exchanges = ['Kraken', 'Kucoin', 'MEXC', 'Gate.io']

    # Filter date range
    start_date_only = start_date.date()
    end_date_only = end_date.date()

    results = []

    for exchange in cex_exchanges:
        logger.info(f"\nProcessing {exchange}...")

        # Get data for this exchange
        exchange_spread = spread_df[spread_df['exchange'] == exchange].copy()
        exchange_depth = depth_df[depth_df['exchange'] == exchange].copy()
        exchange_volume = volume_df[volume_df['exchange'] == exchange].copy()

        if exchange_spread.empty:
            logger.warning(f"  No spread data for {exchange}")
            continue

        # Merge datasets
        merged = exchange_spread.merge(
            exchange_depth[['date', 'twoSidedDepth']],
            on='date',
            how='left'
        ).merge(
            exchange_volume[['date', 'volume']],
            on='date',
            how='left'
        )

        # Filter to date range
        merged = merged[
            (merged['date'].dt.date >= start_date_only) &
            (merged['date'].dt.date <= end_date_only)
        ]

        daily_profits = []
        cumulative_capital = CAPITAL_PER_EXCHANGE

        for _, row in merged.iterrows():
            date = row['date']
            spread_ratio = row['bidAskSpreadRatio']
            depth = row['twoSidedDepth']
            volume = row['volume']

            # Skip if missing data
            if pd.isna(spread_ratio) or pd.isna(depth) or pd.isna(volume):
                continue

            # Check if spread exceeds intervention threshold
            if spread_ratio < INTERVENTION_THRESHOLD:
                # No opportunity
                daily_profits.append({
                    'date': date,
                    'exchange': exchange,
                    'spread': spread_ratio,
                    'depth': depth,
                    'volume': volume,
                    'opportunity': False,
                    'profit': 0,
                    'capital': cumulative_capital
                })
                continue

            # Calculate theoretical position size
            # Limited by: (1) % of volume, (2) available capital, (3) order book depth
            volume_limit = volume * POSITION_SIZE_PCT
            capital_limit = cumulative_capital
            depth_limit = depth * FILL_RATE

            position_size = min(volume_limit, capital_limit, depth_limit)

            if position_size <= 0:
                daily_profits.append({
                    'date': date,
                    'exchange': exchange,
                    'spread': spread_ratio,
                    'depth': depth,
                    'volume': volume,
                    'opportunity': True,
                    'profit': 0,
                    'capital': cumulative_capital,
                    'constraint': 'insufficient_capital_or_depth'
                })
                continue

            # Calculate profit from spread capture
            # Profit = (actual_spread - target_spread) * position_size
            profit_per_execution = (spread_ratio - TARGET_SPREAD) * position_size

            # Apply intraday spike multiplier
            # 30% of time has 2.5x spread
            avg_profit_per_execution = (
                profit_per_execution * (1 - SPIKE_TIME_PCT) +
                profit_per_execution * INTRADAY_SPIKE_MULTIPLIER * SPIKE_TIME_PCT
            )

            # Scale executions based on spread width
            spread_factor = spread_ratio / INTERVENTION_THRESHOLD
            executions = EXECUTIONS_PER_DAY_BASE * min(spread_factor, 2)

            daily_profit = avg_profit_per_execution * executions

            # Update capital (compound profits)
            cumulative_capital += daily_profit

            daily_profits.append({
                'date': date,
                'exchange': exchange,
                'spread': spread_ratio,
                'depth': depth,
                'volume': volume,
                'opportunity': True,
                'position_size': position_size,
                'executions': executions,
                'profit': daily_profit,
                'capital': cumulative_capital
            })

        if daily_profits:
            total_profit = sum(d['profit'] for d in daily_profits)
            opportunities = sum(1 for d in daily_profits if d['opportunity'])
            logger.info(f"  Theoretical profit: ${total_profit:,.2f}")
            logger.info(f"  Trading opportunities: {opportunities} days")
            logger.info(f"  Final capital: ${cumulative_capital:,.2f}")

            results.extend(daily_profits)

    return pd.DataFrame(results)


def calculate_actual_performance(trades_df: pd.DataFrame) -> pd.DataFrame:
    """Calculate actual P&L from real trades"""
    logger.info("=" * 60)
    logger.info("Calculating Actual Trading Performance")
    logger.info("=" * 60)

    # Group by date and exchange
    daily_results = []

    for (date, exchange), group in trades_df.groupby(['date', 'exchange']):
        buys = group[group['side'] == 'BUY']
        sells = group[group['side'] == 'SELL']

        buy_volume = buys['amount'].sum() if not buys.empty else 0
        sell_volume = sells['amount'].sum() if not sells.empty else 0
        buy_value = (buys['amount'] * buys['price']).sum() if not buys.empty else 0
        sell_value = (sells['amount'] * sells['price']).sum() if not sells.empty else 0
        total_fees = group['fee'].sum()

        # Calculate realized P&L (simplistic - sell value minus buy value minus fees)
        realized_pnl = sell_value - buy_value - total_fees

        avg_buy_price = (buys['price'] * buys['amount']).sum() / buy_volume if buy_volume > 0 else 0
        avg_sell_price = (sells['price'] * sells['amount']).sum() / sell_volume if sell_volume > 0 else 0

        daily_results.append({
            'date': pd.Timestamp(date),
            'exchange': exchange,
            'num_trades': len(group),
            'buy_count': len(buys),
            'sell_count': len(sells),
            'buy_volume': buy_volume,
            'sell_volume': sell_volume,
            'buy_value': buy_value,
            'sell_value': sell_value,
            'fees': total_fees,
            'realized_pnl': realized_pnl,
            'avg_buy_price': avg_buy_price,
            'avg_sell_price': avg_sell_price
        })

    actual_df = pd.DataFrame(daily_results)

    # Summary by exchange
    logger.info("\nActual Performance by Exchange:")
    for exchange in actual_df['exchange'].unique():
        exchange_data = actual_df[actual_df['exchange'] == exchange]
        total_pnl = exchange_data['realized_pnl'].sum()
        total_trades = exchange_data['num_trades'].sum()
        trading_days = len(exchange_data)

        logger.info(f"\n  {exchange}:")
        logger.info(f"    Total P&L: ${total_pnl:,.2f}")
        logger.info(f"    Total trades: {total_trades}")
        logger.info(f"    Trading days: {trading_days}")

    total_actual_pnl = actual_df['realized_pnl'].sum()
    logger.info(f"\n  TOTAL ACTUAL P&L: ${total_actual_pnl:,.2f}")

    return actual_df


def generate_comparison_report(theoretical_df: pd.DataFrame, actual_df: pd.DataFrame):
    """Generate side-by-side comparison report"""
    logger.info("=" * 60)
    logger.info("THEORETICAL vs ACTUAL COMPARISON")
    logger.info("=" * 60)

    # Overall totals
    theoretical_total = theoretical_df['profit'].sum()
    actual_total = actual_df['realized_pnl'].sum()
    missed_profit = theoretical_total - actual_total

    logger.info(f"\nOVERALL RESULTS:")
    logger.info(f"  Theoretical Profit:  ${theoretical_total:>12,.2f}")
    logger.info(f"  Actual P&L:          ${actual_total:>12,.2f}")
    logger.info(f"  Missed Opportunity:  ${missed_profit:>12,.2f}")
    logger.info(f"  Capture Rate:        {(actual_total/theoretical_total*100) if theoretical_total != 0 else 0:>12.1f}%")

    # By exchange
    logger.info(f"\nBY EXCHANGE:")
    logger.info(f"{'Exchange':<15} {'Theoretical':>15} {'Actual':>15} {'Missed':>15}")
    logger.info("-" * 62)

    for exchange in ['MEXC', 'Kucoin', 'Gate.io', 'Kraken']:
        theo_exchange = theoretical_df[theoretical_df['exchange'] == exchange]
        actual_exchange = actual_df[actual_df['exchange'].str.lower() == exchange.lower()]

        theo_profit = theo_exchange['profit'].sum() if not theo_exchange.empty else 0
        actual_profit = actual_exchange['realized_pnl'].sum() if not actual_exchange.empty else 0
        missed = theo_profit - actual_profit

        logger.info(f"{exchange:<15} ${theo_profit:>13,.2f} ${actual_profit:>13,.2f} ${missed:>13,.2f}")

    # ROI comparison
    logger.info(f"\nROI ANALYSIS:")
    initial_capital = CAPITAL_PER_EXCHANGE * 4  # 4 exchanges
    theo_roi = (theoretical_total / initial_capital * 100) if initial_capital > 0 else 0
    actual_roi = (actual_total / initial_capital * 100) if initial_capital > 0 else 0

    logger.info(f"  Initial Capital:     ${initial_capital:>12,.2f}")
    logger.info(f"  Theoretical ROI:     {theo_roi:>12.1f}%")
    logger.info(f"  Actual ROI:          {actual_roi:>12.1f}%")

    # Date range
    if not theoretical_df.empty:
        logger.info(f"\nDATE RANGE:")
        logger.info(f"  Start: {theoretical_df['date'].min().date()}")
        logger.info(f"  End:   {theoretical_df['date'].max().date()}")
        logger.info(f"  Days:  {(theoretical_df['date'].max() - theoretical_df['date'].min()).days + 1}")


def main():
    """Main analysis"""
    logger.info("=" * 60)
    logger.info("BACKTEST: THEORETICAL vs ACTUAL PERFORMANCE")
    logger.info("=" * 60)

    try:
        # Step 1: Get actual trade date range
        start_date, end_date = get_actual_trades_date_range()

        # Step 2: Load market data
        spread_df, depth_df, volume_df = load_chart_data()

        # Step 3: Load actual trades
        trades_df = load_actual_trades(start_date, end_date)

        # Step 4: Calculate theoretical profits
        theoretical_df = calculate_theoretical_profits(
            spread_df, depth_df, volume_df, start_date, end_date
        )

        # Step 5: Calculate actual performance
        actual_df = calculate_actual_performance(trades_df)

        # Step 6: Generate comparison
        generate_comparison_report(theoretical_df, actual_df)

        logger.info("=" * 60)
        logger.info("ANALYSIS COMPLETE")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
