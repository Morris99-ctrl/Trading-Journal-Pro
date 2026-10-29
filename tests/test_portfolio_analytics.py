"""Regression tests for cash-flow-adjusted portfolio equity analytics."""

import math
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from data import TradeDatabase
from portfolio_analytics import calculate_portfolio_performance


class PortfolioPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.t0 = datetime(2026, 1, 1, 12, 0, 0)
        self.t1 = self.t0 + timedelta(days=1)
        self.t2 = self.t0 + timedelta(days=2)

    def snap(self, when, equity, account="demo", currency="USD"):
        return {
            "captured_at": when.isoformat(),
            "equity": equity,
            "balance": equity,
            "account_id": account,
            "currency": currency,
            "source": "test",
        }

    def flow(self, when, kind, amount, currency="USD"):
        return {
            "occurred_at": when.isoformat(),
            "type": kind,
            "amount": amount,
            "currency": currency,
        }

    def test_deposit_is_not_misreported_as_profit(self):
        result = calculate_portfolio_performance(
            [self.snap(self.t0, 1000), self.snap(self.t2, 1600)],
            [self.flow(self.t1, "deposit", 500)],
        )
        # Modified Dietz: (1600 - 1000 - 500) / (1000 + 0.5*500) = 8%.
        self.assertAlmostEqual(result["periods"][0]["return_pct"], 8.0)
        self.assertAlmostEqual(result["total_return_pct"], 8.0)
        self.assertEqual(result["periods"][0]["external_net_flow"], 500)

    def test_withdrawal_is_not_misreported_as_trading_loss(self):
        result = calculate_portfolio_performance(
            [self.snap(self.t0, 1000), self.snap(self.t2, 900)],
            [self.flow(self.t1, "withdrawal", 200)],
        )
        # (900 - 1000 - (-200)) / (1000 - 0.5*200) = 100/900.
        self.assertAlmostEqual(result["periods"][0]["return_pct"], 100 / 900 * 100)
        self.assertEqual(result["periods"][0]["external_net_flow"], -200)

    def test_deposit_does_not_create_false_peak_or_drawdown(self):
        result = calculate_portfolio_performance(
            [
                self.snap(self.t0, 1000),
                self.snap(self.t1, 1500),
                self.snap(self.t2, 1400),
            ],
            [self.flow(self.t1, "deposit", 500)],
        )
        self.assertAlmostEqual(result["periods"][0]["return_pct"], 0.0)
        self.assertAlmostEqual(result["periods"][1]["return_pct"], -100 / 1500 * 100)
        self.assertAlmostEqual(result["max_drawdown_pct"], 100 / 1500 * 100)

    def test_cash_flow_at_start_snapshot_is_already_in_starting_equity(self):
        result = calculate_portfolio_performance(
            [self.snap(self.t0, 1500), self.snap(self.t1, 1600)],
            [self.flow(self.t0, "deposit", 500)],
        )
        self.assertAlmostEqual(result["periods"][0]["return_pct"], 100 / 1500 * 100)
        self.assertEqual(result["periods"][0]["external_net_flow"], 0)

    def test_requires_two_snapshots(self):
        result = calculate_portfolio_performance([self.snap(self.t0, 1000)])
        self.assertEqual(result["status"], "insufficient_data")
        self.assertIsNone(result["total_return_pct"])
        self.assertIsNone(result["sharpe_ratio"])

    def test_duplicate_snapshot_times_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "duplicate snapshot"):
            calculate_portfolio_performance([
                self.snap(self.t0, 1000), self.snap(self.t0, 1010)
            ])

    def test_invalid_cash_flow_type_or_amount_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "flow type"):
            calculate_portfolio_performance(
                [self.snap(self.t0, 1000), self.snap(self.t1, 1000)],
                [self.flow(self.t0, "transfer", 100)],
            )
        with self.assertRaisesRegex(ValueError, "greater than zero"):
            calculate_portfolio_performance(
                [self.snap(self.t0, 1000), self.snap(self.t1, 1000)],
                [self.flow(self.t0, "deposit", 0)],
            )

    def test_risk_ratios_require_consistent_snapshot_intervals(self):
        regular = calculate_portfolio_performance([
            self.snap(self.t0, 1000),
            self.snap(self.t1, 1010),
            self.snap(self.t2, 1000),
        ])
        self.assertIsNotNone(regular["sharpe_ratio"])
        self.assertIn("unannualized", regular["risk_metrics_status"])

        irregular = calculate_portfolio_performance([
            self.snap(self.t0, 1000),
            self.snap(self.t1, 1010),
            self.snap(self.t2 + timedelta(days=2), 1000),
        ])
        self.assertIsNone(irregular["sharpe_ratio"])
        self.assertIn("inconsistent durations", irregular["risk_metrics_status"])

    def test_currency_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "currency"):
            calculate_portfolio_performance([
                self.snap(self.t0, 1000, currency="USD"),
                self.snap(self.t1, 1010, currency="KES"),
            ])

    def test_cash_flow_currency_mismatch_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "cash-flow currency"):
            calculate_portfolio_performance(
                [self.snap(self.t0, 1000, currency="USD"), self.snap(self.t1, 1100, currency="USD")],
                [self.flow(self.t0 + timedelta(hours=12), "deposit", 100, currency="KES")],
            )


class PortfolioPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="portfolio-equity-tests-")
        self.db = TradeDatabase(str(Path(self.temp_dir.name) / "portfolio.db"))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_snapshots_and_flows_round_trip_through_sqlite(self):
        t0 = datetime(2026, 1, 1, 12)
        t1 = t0 + timedelta(days=1)
        snapshot_id = self.db.add_equity_snapshot(
            t0, balance=1000, equity=1020, account_id="demo",
            currency="USD", source="broker",
        )
        flow_id = self.db.add_portfolio_cash_flow(
            t1, "deposit", 200, account_id="demo", currency="USD",
        )
        self.assertGreater(snapshot_id, 0)
        self.assertGreater(flow_id, 0)
        snapshots = self.db.get_equity_snapshots("demo")
        flows = self.db.get_portfolio_cash_flows("demo")
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["equity"], 1020)
        self.assertEqual(snapshots[0]["source"], "broker")
        self.assertEqual(len(flows), 1)
        self.assertEqual(flows[0]["flow_type"], "deposit")
        self.assertEqual(flows[0]["amount"], 200)

    def test_duplicate_account_timestamp_is_rejected_by_database(self):
        when = datetime(2026, 1, 1, 12)
        self.db.add_equity_snapshot(when, 1000, 1000, account_id="demo")
        with self.assertRaises(Exception):
            self.db.add_equity_snapshot(when, 1010, 1010, account_id="demo")

    def test_invalid_flow_is_rejected_before_database_write(self):
        with self.assertRaises(ValueError):
            self.db.add_portfolio_cash_flow(
                datetime(2026, 1, 1), "deposit", -10
            )


if __name__ == "__main__":
    unittest.main()
