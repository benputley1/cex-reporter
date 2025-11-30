#!/usr/bin/env python3
"""
Backtest: Last 7 Days - Theoretical Spread Compression vs Actual Trading

Analyzes the last 7 days of hourly market data to compare theoretical profits
from spread compression strategy against actual trading results.

Focuses on identifying liquidation impact on trading performance.

Usage:
    python scripts/backtest_last_7_days.py
"""
import sys
from pathlib import Path
from datetime import datetime
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
POSITION_SIZE_PCT = 0.125  # 12.5% of hourly volume
CAPITAL_PER_EXCHANGE = 10000  # $10,000 per exchange
CAPITAL_TOTAL = 40000  # $40,000 total capital (across all 4 exchanges)
FILL_RATE = 0.80  # 80% of theoretical depth
INTRADAY_SPIKE_MULTIPLIER = 2.5  # Capture 2.5x spread during volatile periods
SPIKE_TIME_PCT = 0.30  # Spikes occur 30% of the time
EXECUTIONS_PER_HOUR_BASE = 0.208  # ~5 executions per day / 24 hours


def load_last_7_days_data() -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load the last 7 days hourly market data with per-exchange spreads"""
    logger.info("Loading last 7 days hourly market data...")

    try:
        # Load per-exchange spread data (wide format)
        spread_wide = pd.read_csv('chart_duration_last_7_days_bidAskSpreadRatioByExchange (1).csv')
        spread_wide['Timestamp'] = pd.to_datetime(spread_wide['Timestamp'])

        # Melt to long format
        spread_df = spread_wide.melt(
            id_vars=['Timestamp'],
            var_name='exchange',
            value_name='spread_ratio'
        )
        spread_df = spread_df.rename(columns={'Timestamp': 'timestamp'})
        # Spread is already in decimal format (0.046 = 4.6%), no need to divide by 100

        logger.info(f"✓ Loaded spread data: {len(spread_df)} records ({len(spread_wide)} hours x 4 exchanges)")
        logger.info(f"  Date range: {spread_df['timestamp'].min()} to {spread_df['timestamp'].max()}")
        logger.info(f"  Exchanges: {spread_df['exchange'].unique().tolist()}")
        logger.info(f"  Spread range: {spread_df['spread_ratio'].min():.4f} to {spread_df['spread_ratio'].max():.4f}")

        # Load total volume and distribute across exchanges
        # Assumption: Divide equally across 4 exchanges (simplification)
        volume_df_total = pd.read_csv('chart_duration_last_7_days_totalVolume.csv')
        volume_df_total['Timestamp'] = pd.to_datetime(volume_df_total['Timestamp'])
        volume_df_total = volume_df_total.rename(columns={
            'Timestamp': 'timestamp',
            'Total Volume': 'volume_total'
        })

        # Create per-exchange volume records
        exchanges = ['Kraken', 'Kucoin', 'MEXC', 'Gate.io']
        volume_records = []
        for _, row in volume_df_total.iterrows():
            for exchange in exchanges:
                volume_records.append({
                    'timestamp': row['timestamp'],
                    'exchange': exchange,
                    'volume': row['volume_total'] / 4  # Equal distribution
                })
        volume_df = pd.DataFrame(volume_records)
        logger.info(f"✓ Loaded volume data: {len(volume_df)} records")
        logger.info(f"  Per-exchange volume range: ${volume_df['volume'].min():,.2f} to ${volume_df['volume'].max():,.2f}")

        # Load total depth and distribute across exchanges
        depth_df_total = pd.read_csv('chart_duration_last_7_days_volumeWeightedDepth.csv')
        depth_df_total['Timestamp'] = pd.to_datetime(depth_df_total['Timestamp'])
        depth_df_total = depth_df_total.rename(columns={
            'Timestamp': 'timestamp',
            'Depth': 'depth_total'
        })

        # Create per-exchange depth records
        depth_records = []
        for _, row in depth_df_total.iterrows():
            for exchange in exchanges:
                depth_records.append({
                    'timestamp': row['timestamp'],
                    'exchange': exchange,
                    'depth': row['depth_total'] / 4  # Equal distribution
                })
        depth_df = pd.DataFrame(depth_records)
        logger.info(f"✓ Loaded depth data: {len(depth_df)} records")
        logger.info(f"  Per-exchange depth range: ${depth_df['depth'].min():,.2f} to ${depth_df['depth'].max():,.2f}")

        return spread_df, depth_df, volume_df

    except Exception as e:
        logger.error(f"Error loading data: {e}", exc_info=True)
        raise


def load_actual_trades_7days(start_time: datetime, end_time: datetime) -> pd.DataFrame:
    """Load actual trades from database for the 7-day period"""
    logger.info(f"Loading actual trades from {start_time} to {end_time}...")

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
                fee,
                fee_currency
            FROM trades
            WHERE timestamp >= ? AND timestamp <= ?
            ORDER BY timestamp
        """

        df = pd.read_sql_query(
            query,
            conn,
            params=(start_time.isoformat(), end_time.isoformat())
        )
        conn.close()

        if df.empty:
            logger.warning("No trades found in database for this period")
            return df

        df['timestamp'] = pd.to_datetime(df['timestamp'], format='mixed')

        logger.info(f"✓ Loaded {len(df)} actual trades")
        logger.info(f"  Exchanges: {df['exchange'].unique().tolist()}")
        logger.info(f"  Accounts: {df['account_name'].nunique()} unique accounts")
        logger.info(f"  Time range: {df['timestamp'].min()} to {df['timestamp'].max()}")

        # Show trade distribution by side
        side_counts = df['side'].value_counts()
        logger.info(f"  Trade sides: {side_counts.to_dict()}")

        return df

    except Exception as e:
        logger.error(f"Error loading trades: {e}", exc_info=True)
        raise


def calculate_theoretical_profits_hourly(
    spread_df: pd.DataFrame,
    depth_df: pd.DataFrame,
    volume_df: pd.DataFrame
) -> pd.DataFrame:
    """Calculate theoretical profits using hourly per-exchange market data"""
    logger.info("=" * 70)
    logger.info("Calculating Theoretical Spread Compression Profits (Hourly)")
    logger.info("=" * 70)

    # Merge all data on timestamp AND exchange
    merged = spread_df.merge(depth_df, on=['timestamp', 'exchange'], how='inner') \
                      .merge(volume_df, on=['timestamp', 'exchange'], how='inner')

    logger.info(f"Processing {len(merged)} exchange-hour records ({len(merged)//4} hours x 4 exchanges)...")

    # Track capital per exchange
    capital_by_exchange = {
        'Kraken': CAPITAL_PER_EXCHANGE,
        'Kucoin': CAPITAL_PER_EXCHANGE,
        'MEXC': CAPITAL_PER_EXCHANGE,
        'Gate.io': CAPITAL_PER_EXCHANGE
    }

    results = []
    total_opportunities = 0
    total_hours_traded = 0

    for _, row in merged.iterrows():
        timestamp = row['timestamp']
        exchange = row['exchange']
        spread_ratio = row['spread_ratio']
        depth = row['depth']
        volume = row['volume']

        # Get current capital for this exchange
        cumulative_capital = capital_by_exchange[exchange]

        # Skip if missing data
        if pd.isna(spread_ratio) or pd.isna(depth) or pd.isna(volume):
            continue

        # Check if spread exceeds intervention threshold
        if spread_ratio < INTERVENTION_THRESHOLD:
            results.append({
                'timestamp': timestamp,
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
            results.append({
                'timestamp': timestamp,
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
        avg_profit_per_execution = (
            profit_per_execution * (1 - SPIKE_TIME_PCT) +
            profit_per_execution * INTRADAY_SPIKE_MULTIPLIER * SPIKE_TIME_PCT
        )

        # Scale executions based on spread width
        spread_factor = spread_ratio / INTERVENTION_THRESHOLD
        executions = EXECUTIONS_PER_HOUR_BASE * min(spread_factor, 2)

        hourly_profit = avg_profit_per_execution * executions

        # Update capital for this exchange (compound profits)
        cumulative_capital += hourly_profit
        capital_by_exchange[exchange] = cumulative_capital

        total_opportunities += 1
        if hourly_profit > 0:
            total_hours_traded += 1

        results.append({
            'timestamp': timestamp,
            'exchange': exchange,
            'spread': spread_ratio,
            'depth': depth,
            'volume': volume,
            'opportunity': True,
            'position_size': position_size,
            'executions': executions,
            'profit': hourly_profit,
            'capital': cumulative_capital
        })

    results_df = pd.DataFrame(results)

    if not results_df.empty:
        total_profit = results_df['profit'].sum()
        initial_capital = CAPITAL_TOTAL
        final_capital = sum(capital_by_exchange.values())
        roi = (total_profit / initial_capital * 100) if initial_capital > 0 else 0

        logger.info(f"\n✓ Theoretical Analysis Complete:")
        logger.info(f"  Initial Capital:     ${initial_capital:>12,.2f}")
        logger.info(f"  Total Profit:        ${total_profit:>12,.2f}")
        logger.info(f"  Final Capital:       ${final_capital:>12,.2f}")
        logger.info(f"  ROI:                 {roi:>12.1f}%")
        logger.info(f"  Total Exchange-Hours:{len(results_df):>12}")
        logger.info(f"  Opportunities:       {total_opportunities:>12}")
        logger.info(f"  Hours Traded:        {total_hours_traded:>12}")
        logger.info(f"  Utilization:         {(total_hours_traded/len(results_df)*100):>12.1f}%")

    return results_df


def calculate_actual_performance_hourly(trades_df: pd.DataFrame) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Calculate actual P&L from real trades with liquidation analysis"""
    logger.info("=" * 70)
    logger.info("Calculating Actual Trading Performance")
    logger.info("=" * 70)

    if trades_df.empty:
        logger.warning("No trades to analyze")
        return pd.DataFrame(), pd.DataFrame()

    # Add hour grouping
    trades_df['hour'] = trades_df['timestamp'].dt.floor('H')

    # Overall statistics
    total_trades = len(trades_df)
    buy_trades = len(trades_df[trades_df['side'] == 'BUY'])
    sell_trades = len(trades_df[trades_df['side'] == 'SELL'])

    logger.info(f"\n✓ Trade Summary:")
    logger.info(f"  Total Trades:        {total_trades:>12}")
    logger.info(f"  Buy Trades:          {buy_trades:>12} ({buy_trades/total_trades*100:.1f}%)")
    logger.info(f"  Sell Trades:         {sell_trades:>12} ({sell_trades/total_trades*100:.1f}%)")
    logger.info(f"  Buy/Sell Ratio:      {buy_trades/sell_trades if sell_trades > 0 else 0:>12.2f}")

    # Hourly P&L calculation
    hourly_results = []

    for hour, group in trades_df.groupby('hour'):
        buys = group[group['side'] == 'BUY']
        sells = group[group['side'] == 'SELL']

        buy_volume = buys['amount'].sum() if not buys.empty else 0
        sell_volume = sells['amount'].sum() if not sells.empty else 0
        buy_value = (buys['amount'] * buys['price']).sum() if not buys.empty else 0
        sell_value = (sells['amount'] * sells['price']).sum() if not sells.empty else 0
        total_fees = group['fee'].sum()

        # Realized P&L (sell value minus buy value minus fees)
        realized_pnl = sell_value - buy_value - total_fees

        avg_buy_price = (buys['price'] * buys['amount']).sum() / buy_volume if buy_volume > 0 else 0
        avg_sell_price = (sells['price'] * sells['amount']).sum() / sell_volume if sell_volume > 0 else 0

        # Liquidation indicators
        net_position_change = buy_volume - sell_volume
        is_net_seller = sell_volume > buy_volume * 1.2  # 20% more selling than buying

        hourly_results.append({
            'hour': hour,
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
            'avg_sell_price': avg_sell_price,
            'net_position_change': net_position_change,
            'is_net_seller': is_net_seller
        })

    hourly_df = pd.DataFrame(hourly_results)

    # Overall P&L
    total_pnl = hourly_df['realized_pnl'].sum()
    total_fees = hourly_df['fees'].sum()

    # Liquidation analysis
    net_seller_hours = hourly_df['is_net_seller'].sum()
    total_net_position_change = hourly_df['net_position_change'].sum()

    logger.info(f"\n✓ Performance Metrics:")
    logger.info(f"  Total Realized P&L:  ${total_pnl:>12,.2f}")
    logger.info(f"  Total Fees Paid:     ${total_fees:>12,.2f}")
    logger.info(f"  Net Position Change: {total_net_position_change:>12,.0f} ALKIMI")
    logger.info(f"  Net Seller Hours:    {net_seller_hours:>12} / {len(hourly_df)}")
    logger.info(f"  Liquidation %:       {net_seller_hours/len(hourly_df)*100:>12.1f}%")

    # Exchange breakdown
    exchange_summary = []
    for exchange in trades_df['exchange'].unique():
        ex_trades = trades_df[trades_df['exchange'] == exchange]
        ex_buys = ex_trades[ex_trades['side'] == 'BUY']
        ex_sells = ex_trades[ex_trades['side'] == 'SELL']

        buy_val = (ex_buys['amount'] * ex_buys['price']).sum() if not ex_buys.empty else 0
        sell_val = (ex_sells['amount'] * ex_sells['price']).sum() if not ex_sells.empty else 0
        ex_fees = ex_trades['fee'].sum()
        ex_pnl = sell_val - buy_val - ex_fees

        exchange_summary.append({
            'exchange': exchange,
            'trades': len(ex_trades),
            'buys': len(ex_buys),
            'sells': len(ex_sells),
            'realized_pnl': ex_pnl
        })

    exchange_df = pd.DataFrame(exchange_summary)

    logger.info(f"\n✓ Performance by Exchange:")
    for _, row in exchange_df.iterrows():
        logger.info(f"  {row['exchange']:<10} Trades: {row['trades']:>4}  " +
                   f"Buys: {row['buys']:>4}  Sells: {row['sells']:>4}  " +
                   f"P&L: ${row['realized_pnl']:>10,.2f}")

    return hourly_df, exchange_df


def generate_comparison_report(theoretical_df: pd.DataFrame, actual_df: pd.DataFrame):
    """Generate comprehensive comparison report"""
    logger.info("=" * 70)
    logger.info("THEORETICAL vs ACTUAL COMPARISON - LAST 7 DAYS")
    logger.info("=" * 70)

    # Calculate totals
    theoretical_total = theoretical_df['profit'].sum() if not theoretical_df.empty else 0
    actual_total = actual_df['realized_pnl'].sum() if not actual_df.empty else 0
    missed_profit = theoretical_total - actual_total

    # ROI calculations
    initial_capital = CAPITAL_TOTAL
    theo_roi = (theoretical_total / initial_capital * 100) if initial_capital > 0 else 0
    actual_roi = (actual_total / initial_capital * 100) if initial_capital > 0 else 0

    # Annualized projections (7 days * 52.14 weeks)
    days_in_period = 7
    annualization_factor = 365 / days_in_period
    theo_annual = theoretical_total * annualization_factor
    actual_annual = actual_total * annualization_factor
    theo_annual_roi = theo_roi * annualization_factor
    actual_annual_roi = actual_roi * annualization_factor

    logger.info(f"\n{'METRIC':<30} {'THEORETICAL':>15} {'ACTUAL':>15} {'DELTA':>15}")
    logger.info("=" * 76)

    logger.info(f"{'Initial Capital':<30} ${initial_capital:>13,.2f} ${initial_capital:>13,.2f} {'—':>15}")
    logger.info(f"{'7-Day Profit':<30} ${theoretical_total:>13,.2f} ${actual_total:>13,.2f} ${missed_profit:>13,.2f}")
    logger.info(f"{'7-Day ROI':<30} {theo_roi:>13.2f}% {actual_roi:>13.2f}% {theo_roi-actual_roi:>13.2f}%")
    logger.info(f"{'Capture Rate':<30} {'100.0%':>15} {(actual_total/theoretical_total*100) if theoretical_total != 0 else 0:>14.1f}% {'—':>15}")

    logger.info("\n" + "─" * 76)
    logger.info("ANNUALIZED PROJECTIONS (365-day extrapolation)")
    logger.info("─" * 76)

    logger.info(f"{'Annual Profit':<30} ${theo_annual:>13,.2f} ${actual_annual:>13,.2f} ${theo_annual-actual_annual:>13,.2f}")
    logger.info(f"{'Annual ROI':<30} {theo_annual_roi:>13.1f}% {actual_annual_roi:>13.1f}% {theo_annual_roi-actual_annual_roi:>13.1f}%")

    # Date range
    if not theoretical_df.empty:
        logger.info(f"\n{'DATE RANGE':<30}")
        logger.info(f"  Start: {theoretical_df['timestamp'].min()}")
        logger.info(f"  End:   {theoretical_df['timestamp'].max()}")
        logger.info(f"  Hours: {len(theoretical_df)}")

    # Liquidation impact analysis
    if not actual_df.empty and 'is_net_seller' in actual_df.columns:
        net_seller_hours = actual_df['is_net_seller'].sum()
        liquidation_pct = net_seller_hours / len(actual_df) * 100

        logger.info(f"\n{'LIQUIDATION ANALYSIS':<30}")
        logger.info(f"  Hours with Net Selling:  {net_seller_hours} / {len(actual_df)} ({liquidation_pct:.1f}%)")

        if liquidation_pct > 50:
            logger.info(f"  ⚠️  HEAVY LIQUIDATION DETECTED - {liquidation_pct:.0f}% of hours were net selling")
            logger.info(f"      This likely suppressed profits significantly vs theoretical strategy")


def main():
    """Main analysis"""
    logger.info("=" * 70)
    logger.info("7-DAY BACKTEST: THEORETICAL vs ACTUAL PERFORMANCE")
    logger.info("=" * 70)

    try:
        # Step 1: Load hourly market data
        spread_df, depth_df, volume_df = load_last_7_days_data()

        # Get date range from data
        start_time = spread_df['timestamp'].min()
        end_time = spread_df['timestamp'].max()

        # Step 2: Load actual trades
        trades_df = load_actual_trades_7days(start_time, end_time)

        # Step 3: Calculate theoretical profits
        theoretical_df = calculate_theoretical_profits_hourly(
            spread_df, depth_df, volume_df
        )

        # Step 4: Calculate actual performance
        actual_hourly_df, actual_exchange_df = calculate_actual_performance_hourly(trades_df)

        # Step 5: Generate comparison
        generate_comparison_report(theoretical_df, actual_hourly_df)

        # Step 6: Export results
        logger.info("\n" + "=" * 70)
        logger.info("Exporting results...")

        theoretical_df.to_csv('last_7_days_theoretical_profits.csv', index=False)
        logger.info("✓ Saved: last_7_days_theoretical_profits.csv")

        if not actual_hourly_df.empty:
            actual_hourly_df.to_csv('last_7_days_actual_performance.csv', index=False)
            logger.info("✓ Saved: last_7_days_actual_performance.csv")

        if not actual_exchange_df.empty:
            actual_exchange_df.to_csv('last_7_days_exchange_summary.csv', index=False)
            logger.info("✓ Saved: last_7_days_exchange_summary.csv")

        logger.info("=" * 70)
        logger.info("ANALYSIS COMPLETE")
        logger.info("=" * 70)

    except Exception as e:
        logger.error(f"Analysis failed: {e}", exc_info=True)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
