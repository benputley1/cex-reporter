"""
Unit tests for mock data module
"""
import unittest
from datetime import datetime, timedelta
from src.utils.mock_data import (
    get_mock_balances,
    get_mock_prices,
    get_mock_trades,
    get_all_mock_trades,
    get_mock_trade_summary,
    get_portfolio_summary,
    get_cached_trades,
    generate_random_trades,
    initialize_mock_trades,
    MOCK_BALANCES,
    MOCK_PRICES,
)
from src.exchanges.base import Trade, TradeSide


class TestMockBalances(unittest.TestCase):
    """Test mock balance generation"""

    def test_get_mock_balances_mexc(self):
        """Test MEXC balances"""
        balances = get_mock_balances('mexc')
        self.assertEqual(balances['USDT'], 50000.00)
        self.assertEqual(balances['ALKIMI'], 1500000.00)

    def test_get_mock_balances_kraken(self):
        """Test Kraken balances (ALKIMI not listed)"""
        balances = get_mock_balances('kraken')
        self.assertEqual(balances['USDT'], 75000.00)
        self.assertEqual(balances['ALKIMI'], 0.00)

    def test_get_mock_balances_kucoin(self):
        """Test KuCoin balances"""
        balances = get_mock_balances('kucoin')
        self.assertEqual(balances['USDT'], 30000.00)
        self.assertEqual(balances['ALKIMI'], 800000.00)

    def test_get_mock_balances_gateio(self):
        """Test Gate.io balances"""
        balances = get_mock_balances('gateio')
        self.assertEqual(balances['USDT'], 45000.00)
        self.assertEqual(balances['ALKIMI'], 1200000.00)

    def test_get_mock_balances_invalid_exchange(self):
        """Test invalid exchange raises error"""
        with self.assertRaises(ValueError):
            get_mock_balances('invalid_exchange')

    def test_total_balances(self):
        """Test total portfolio balances"""
        total_usdt = sum(b.get('USDT', 0) for b in MOCK_BALANCES.values())
        total_alkimi = sum(b.get('ALKIMI', 0) for b in MOCK_BALANCES.values())

        self.assertEqual(total_usdt, 200000.00)
        self.assertEqual(total_alkimi, 3500000.00)


class TestMockPrices(unittest.TestCase):
    """Test mock price generation"""

    def test_get_mock_prices(self):
        """Test getting multiple prices"""
        prices = get_mock_prices(['USDT', 'ALKIMI'])
        self.assertEqual(prices['USDT'], 1.00)
        self.assertEqual(prices['ALKIMI'], 0.20)

    def test_get_mock_prices_unknown_symbol(self):
        """Test unknown symbol returns default price"""
        prices = get_mock_prices(['UNKNOWN'])
        self.assertEqual(prices['UNKNOWN'], 1.0)

    def test_mock_prices_constants(self):
        """Test price constants are correct"""
        self.assertEqual(MOCK_PRICES['USDT'], 1.00)
        self.assertEqual(MOCK_PRICES['ALKIMI'], 0.20)


class TestMockTrades(unittest.TestCase):
    """Test mock trade generation"""

    def test_generate_random_trades(self):
        """Test generating random trades"""
        start_date = datetime(2025, 8, 19, 0, 0, 0)
        trades = generate_random_trades(
            exchange='mexc',
            symbols=['ALKIMI'],
            count=10,
            start_date=start_date
        )

        self.assertEqual(len(trades), 10)
        for trade in trades:
            self.assertIsInstance(trade, Trade)
            self.assertEqual(trade.symbol, 'ALKIMI')
            self.assertGreaterEqual(trade.timestamp, start_date)
            self.assertIn(trade.side, [TradeSide.BUY, TradeSide.SELL])
            self.assertGreater(trade.amount, 0)
            self.assertGreater(trade.price, 0)
            self.assertGreater(trade.fee, 0)

    def test_trades_sorted_by_timestamp(self):
        """Test trades are sorted chronologically"""
        start_date = datetime(2025, 8, 19, 0, 0, 0)
        trades = generate_random_trades(
            exchange='mexc',
            symbols=['ALKIMI'],
            count=20,
            start_date=start_date
        )

        timestamps = [t.timestamp for t in trades]
        self.assertEqual(timestamps, sorted(timestamps))

    def test_get_mock_trades(self):
        """Test getting mock trades for exchange"""
        start_date = datetime(2025, 8, 19, 0, 0, 0)
        trades = get_mock_trades('mexc', start_date)

        self.assertGreater(len(trades), 0)
        for trade in trades:
            self.assertGreaterEqual(trade.timestamp, start_date)

    def test_kraken_no_alkimi_trades(self):
        """Test Kraken has no ALKIMI trades (not listed)"""
        start_date = datetime(2025, 8, 19, 0, 0, 0)
        trades = get_mock_trades('kraken', start_date, symbols=['ALKIMI'])

        # Should have no trades for ALKIMI on Kraken
        alkimi_trades = [t for t in trades if t.symbol == 'ALKIMI']
        self.assertEqual(len(alkimi_trades), 0)

    def test_get_all_mock_trades(self):
        """Test getting all trades across exchanges"""
        start_date = datetime(2025, 8, 19, 0, 0, 0)
        all_trades = get_all_mock_trades(start_date)

        self.assertEqual(len(all_trades), 4)  # 4 exchanges
        for exchange, trades in all_trades.items():
            self.assertIn(exchange, ['mexc', 'kraken', 'kucoin', 'gateio'])
            self.assertGreater(len(trades), 0)

    def test_cached_trades_consistency(self):
        """Test cached trades are consistent across calls"""
        initialize_mock_trades(seed=42)

        trades1 = get_cached_trades('mexc')
        trades2 = get_cached_trades('mexc')

        self.assertEqual(len(trades1), len(trades2))
        for t1, t2 in zip(trades1, trades2):
            self.assertEqual(t1.timestamp, t2.timestamp)
            self.assertEqual(t1.amount, t2.amount)
            self.assertEqual(t1.price, t2.price)


class TestTradeSummary(unittest.TestCase):
    """Test trade summary functions"""

    def test_get_mock_trade_summary(self):
        """Test trade summary statistics"""
        start_date = datetime(2025, 8, 19, 0, 0, 0)
        summary = get_mock_trade_summary(start_date)

        for exchange, stats in summary.items():
            self.assertIn(exchange, ['mexc', 'kraken', 'kucoin', 'gateio'])
            self.assertIn('total_trades', stats)
            self.assertIn('buy_trades', stats)
            self.assertIn('sell_trades', stats)
            self.assertIn('buy_volume_usd', stats)
            self.assertIn('sell_volume_usd', stats)
            self.assertIn('total_fees_usdt', stats)

            # Verify buy + sell = total
            self.assertEqual(
                stats['buy_trades'] + stats['sell_trades'],
                stats['total_trades']
            )

    def test_get_portfolio_summary(self):
        """Test portfolio summary"""
        portfolio = get_portfolio_summary()

        self.assertEqual(portfolio['total_usdt'], 200000.00)
        self.assertEqual(portfolio['total_alkimi'], 3500000.00)
        self.assertEqual(portfolio['usdt_price'], 1.00)
        self.assertEqual(portfolio['alkimi_price'], 0.20)
        self.assertEqual(portfolio['total_value_usd'], 900000.00)
        self.assertIn('exchanges', portfolio)
        self.assertEqual(len(portfolio['exchanges']), 4)


class TestTradeDataQuality(unittest.TestCase):
    """Test quality and realism of generated trade data"""

    def test_price_ranges(self):
        """Test prices are within expected ranges"""
        start_date = datetime(2025, 8, 19, 0, 0, 0)
        trades = get_mock_trades('mexc', start_date)

        for trade in trades:
            if trade.symbol == 'USDT':
                # USDT should be close to $1 with some variation and trend
                # Range: 0.998-1.002 base * 1.20 trend * 1.05 volatility = ~0.95-1.26
                self.assertGreaterEqual(trade.price, 0.90)
                self.assertLessEqual(trade.price, 1.30)
            elif trade.symbol == 'ALKIMI':
                # ALKIMI should be in range $0.15-$0.25 with volatility and trend
                # Range: 0.15-0.25 base * 1.20 trend * 1.05 volatility = ~0.14-0.39
                self.assertGreaterEqual(trade.price, 0.13)
                self.assertLessEqual(trade.price, 0.40)

    def test_fee_calculation(self):
        """Test fees are reasonable (around 0.1%)"""
        start_date = datetime(2025, 8, 19, 0, 0, 0)
        trades = get_mock_trades('mexc', start_date)

        for trade in trades:
            cost = trade.price * trade.amount
            expected_fee = cost * 0.001
            # Fee should be close to 0.1% (allow some rounding)
            self.assertAlmostEqual(trade.fee, expected_fee, places=2)

    def test_trade_amounts(self):
        """Test trade amounts are reasonable"""
        start_date = datetime(2025, 8, 19, 0, 0, 0)
        trades = get_mock_trades('mexc', start_date)

        for trade in trades:
            self.assertGreater(trade.amount, 0)
            if trade.symbol == 'ALKIMI':
                self.assertGreaterEqual(trade.amount, 900)
                self.assertLessEqual(trade.amount, 55000)
            elif trade.symbol == 'USDT':
                self.assertGreaterEqual(trade.amount, 90)
                self.assertLessEqual(trade.amount, 11000)

    def test_trade_ids_unique(self):
        """Test trade IDs are unique"""
        start_date = datetime(2025, 8, 19, 0, 0, 0)
        trades = get_mock_trades('mexc', start_date)

        trade_ids = [t.trade_id for t in trades]
        self.assertEqual(len(trade_ids), len(set(trade_ids)))


class TestDateFiltering(unittest.TestCase):
    """Test date filtering functionality"""

    def test_trades_since_date(self):
        """Test filtering trades by since date"""
        start_date = datetime(2025, 8, 19, 0, 0, 0)
        filter_date = datetime(2025, 9, 1, 0, 0, 0)

        trades = get_cached_trades('mexc', since=filter_date)

        for trade in trades:
            self.assertGreaterEqual(trade.timestamp, filter_date)

    def test_trades_date_range(self):
        """Test trades span the expected date range"""
        start_date = datetime(2025, 8, 19, 0, 0, 0)
        trades = get_mock_trades('mexc', start_date)

        timestamps = [t.timestamp for t in trades]
        min_date = min(timestamps)
        max_date = max(timestamps)

        self.assertGreaterEqual(min_date, start_date)
        self.assertLessEqual(max_date, datetime.now())


if __name__ == '__main__':
    unittest.main()
