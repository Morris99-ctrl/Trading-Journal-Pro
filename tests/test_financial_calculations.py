"""Regression tests for financial ratios and reporting-period semantics."""

import math
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from analytics import TradeAnalytics
from calculators import TradingCalculator
from data import TradeDatabase
from models import Trade, TradeStatus, TradeType


class FinancialRatioTests(unittest.TestCase):
    def test_sharpe_ratio_is_not_annualized_from_trade_count(self):
        result = TradingCalculator.calculate_sharpe_ratio([0.01, 0.03])
        expected = 0.02 / math.sqrt(0.0002)
        self.assertAlmostEqual(result, expected)

    def test_sharpe_ratio_applies_per_observation_hurdle(self):
        result = TradingCalculator.calculate_sharpe_ratio([0.01, 0.03], risk_free_rate=0.01)
        expected = 0.01 / math.sqrt(0.0002)
        self.assertAlmostEqual(result, expected)

    def test_sortino_downside_deviation_uses_all_observations(self):
        result = TradingCalculator.calculate_sortino_ratio([0.10, -0.10])
        self.assertAlmostEqual(result, 0.0)

    def test_sortino_is_infinite_when_positive_mean_has_no_downside(self):
        result = TradingCalculator.calculate_sortino_ratio([0.01, 0.02])
        self.assertTrue(math.isinf(result))

    def test_short_series_returns_zero_for_sharpe_and_sortino(self):
        self.assertEqual(TradingCalculator.calculate_sharpe_ratio([0.02]), 0.0)
        self.assertEqual(TradingCalculator.calculate_sortino_ratio([0.02]), 0.0)


class ReportingDateBasisTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="journal-finance-tests-")
        self.db_path = str(Path(self.temp_dir.name) / "journal.db")
        self.db = TradeDatabase(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def add_closed_trade(self, trade_id, entry_time, exit_time, pnl_direction=1):
        trade = Trade(
            id=trade_id,
            symbol="TEST",
            trade_type=TradeType.BUY if pnl_direction > 0 else TradeType.SHORT,
            quantity=1,
            entry_price=100.0,
            exit_price=110.0 if pnl_direction > 0 else 90.0,
            entry_time=entry_time,
            exit_time=exit_time,
            status=TradeStatus.CLOSED,
        )
        self.assertTrue(self.db.add_trade(trade))
        return trade

    def test_exit_date_filter_includes_old_entry_closed_inside_period(self):
        self.add_closed_trade(
            "closed-in-period",
            datetime(2025, 12, 20),
            datetime(2026, 1, 10),
        )
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31, 23, 59, 59)

        by_exit = self.db.get_all_trades(
            status=TradeStatus.CLOSED,
            start_date=start,
            end_date=end,
            date_basis="exit",
        )
        self.assertEqual([trade.id for trade in by_exit], ["closed-in-period"])

    def test_exit_date_filter_excludes_trade_closed_after_period(self):
        self.add_closed_trade(
            "closed-after-period",
            datetime(2026, 1, 10),
            datetime(2026, 2, 5),
        )
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31, 23, 59, 59)

        by_exit = self.db.get_all_trades(
            status=TradeStatus.CLOSED,
            start_date=start,
            end_date=end,
            date_basis="exit",
        )
        self.assertEqual(by_exit, [])

    def test_entry_date_filter_remains_available_for_cohort_analysis(self):
        self.add_closed_trade(
            "entry-in-period",
            datetime(2026, 1, 10),
            datetime(2026, 2, 5),
        )
        start = datetime(2026, 1, 1)
        end = datetime(2026, 1, 31, 23, 59, 59)

        by_entry = self.db.get_all_trades(
            status=TradeStatus.CLOSED,
            start_date=start,
            end_date=end,
            date_basis="entry",
        )
        self.assertEqual([trade.id for trade in by_entry], ["entry-in-period"])

    def test_invalid_date_basis_is_rejected(self):
        with self.assertRaises(ValueError):
            self.db.get_all_trades(date_basis="magic")

    def test_period_analysis_uses_exit_dates(self):
        self.add_closed_trade(
            "period-analysis-exit",
            datetime(2025, 12, 20),
            datetime(2026, 1, 10),
        )
        analytics = TradeAnalytics(self.db_path)
        result = analytics.get_period_analysis(
            datetime(2026, 1, 1),
            datetime(2026, 1, 31, 23, 59, 59),
        )
        self.assertEqual(result["total_trades"], 1)
        self.assertAlmostEqual(result["total_pnl"], 10.0)


class DrawdownSeriesTests(unittest.TestCase):
    @staticmethod
    def closed_trade(trade_id, pnl, entry_time, exit_time):
        return Trade(
            id=trade_id,
            symbol="TEST",
            trade_type=TradeType.BUY,
            quantity=1,
            entry_price=100.0,
            exit_price=100.0 + pnl,
            entry_time=entry_time,
            exit_time=exit_time,
            status=TradeStatus.CLOSED,
        )

    def test_drawdown_tracks_peak_to_trough_and_current_drawdown(self):
        trades = [
            self.closed_trade("win", 100.0, datetime(2026, 1, 1), datetime(2026, 1, 3)),
            self.closed_trade("loss-one", -50.0, datetime(2026, 1, 1), datetime(2026, 1, 4)),
            self.closed_trade("loss-two", -100.0, datetime(2026, 1, 2), datetime(2026, 1, 5)),
        ]
        result = TradingCalculator.calculate_drawdown_series(trades, initial_balance=10000.0)
        self.assertEqual(result["peak_balance"], 10100.0)
        self.assertEqual(result["current_balance"], 9950.0)
        self.assertEqual(result["max_drawdown_dollars"], 150.0)
        self.assertAlmostEqual(result["max_drawdown_pct"], 150.0 / 10100.0 * 100.0, places=2)
        self.assertEqual(result["current_drawdown_dollars"], 150.0)

    def test_drawdown_curve_is_sorted_by_close_time(self):
        late_close = self.closed_trade(
            "late-close", 20.0, datetime(2026, 1, 1), datetime(2026, 1, 5)
        )
        early_close = self.closed_trade(
            "early-close", 10.0, datetime(2026, 1, 4), datetime(2026, 1, 3)
        )
        result = TradingCalculator.calculate_drawdown_series(
            [late_close, early_close], initial_balance=1000.0
        )
        times = [point["time"] for point in result["equity_curve"]]
        self.assertEqual(times, sorted(times))
        self.assertEqual(
            [point["equity"] for point in result["equity_curve"]],
            [1000.0, 1010.0, 1030.0],
        )

    def test_drawdown_rejects_non_positive_initial_balance(self):
        with self.assertRaises(ValueError):
            TradingCalculator.calculate_drawdown_series([], initial_balance=0.0)


if __name__ == "__main__":
    unittest.main()
