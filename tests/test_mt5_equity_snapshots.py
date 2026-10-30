"""Mocked integration tests for MT5 account-equity snapshot capture."""

import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from data import TradeDatabase
from mt5_service import MT5SyncService
from services import TradeService


class FakeMT5Account:
    def __init__(self, account=None, initialize_ok=True):
        self.account = account
        self.initialize_ok = initialize_ok
        self.shutdown_count = 0

    def initialize(self, timeout=5000):
        return self.initialize_ok

    def account_info(self):
        return self.account

    def last_error(self):
        return (0, "mock MT5 error")

    def shutdown(self):
        self.shutdown_count += 1


class SnapshotRecorder:
    def __init__(self, db):
        self.db = db

    def record_equity_snapshot(self, **kwargs):
        return self.db.add_equity_snapshot(**kwargs)


class MT5EquityCaptureTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="mt5-equity-snapshots-")
        self.db = TradeDatabase(str(Path(self.temp_dir.name) / "journal.db"))
        self.when = datetime(2026, 10, 30, 10, 0, 0)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_captures_broker_balance_equity_currency_and_account_identity(self):
        mt5 = FakeMT5Account(SimpleNamespace(
            login=123456, server="Broker-Demo", currency="usd",
            balance=10000.0, equity=9875.5,
        ))
        sync = MT5SyncService()
        sync._mt5 = mt5

        result = sync.capture_account_snapshot(SnapshotRecorder(self.db), captured_at=self.when)

        self.assertTrue(result["success"])
        self.assertEqual(result["account_id"], "123456@Broker-Demo")
        self.assertEqual(result["balance"], 10000.0)
        self.assertEqual(result["equity"], 9875.5)
        self.assertEqual(result["currency"], "USD")
        self.assertEqual(result["source"], "mt5")
        self.assertEqual(mt5.shutdown_count, 1)

        snapshots = self.db.get_equity_snapshots("123456@Broker-Demo")
        self.assertEqual(len(snapshots), 1)
        self.assertEqual(snapshots[0]["source"], "mt5")
        self.assertEqual(snapshots[0]["currency"], "USD")
        self.assertEqual(snapshots[0]["equity"], 9875.5)

    def test_missing_account_info_fails_closed_and_shuts_down_terminal(self):
        mt5 = FakeMT5Account(account=None)
        sync = MT5SyncService()
        sync._mt5 = mt5

        with self.assertRaisesRegex(ConnectionError, "no account information"):
            sync.capture_account_snapshot(SnapshotRecorder(self.db), captured_at=self.when)

        self.assertEqual(mt5.shutdown_count, 1)
        self.assertEqual(self.db.get_equity_accounts(), [])

    def test_incomplete_account_identity_is_rejected(self):
        mt5 = FakeMT5Account(SimpleNamespace(
            login=123456, server="", currency="USD", balance=1000, equity=1000,
        ))
        sync = MT5SyncService()
        sync._mt5 = mt5

        with self.assertRaisesRegex(ValueError, "identity or account currency"):
            sync.capture_account_snapshot(SnapshotRecorder(self.db), captured_at=self.when)

        self.assertEqual(mt5.shutdown_count, 1)
        self.assertEqual(self.db.get_equity_accounts(), [])

    def test_service_exposes_actual_equity_curve_and_account_list(self):
        account_id = "123456@Broker-Demo"
        self.db.add_equity_snapshot(
            self.when, 10000, 10000, account_id=account_id,
            currency="USD", source="mt5",
        )
        self.db.add_equity_snapshot(
            self.when + timedelta(days=1), 10000, 10100, account_id=account_id,
            currency="USD", source="mt5",
        )

        # Exercise the service query/analytics methods without connecting to a terminal.
        service = TradeService.__new__(TradeService)
        service.db = self.db
        accounts = service.get_portfolio_accounts()
        performance = service.get_portfolio_performance(account_id)

        self.assertEqual(accounts[0]["account_id"], account_id)
        self.assertEqual(performance["snapshot_count"], 2)
        self.assertEqual(len(performance["equity_curve"]), 2)
        self.assertEqual(performance["equity_curve"][-1]["equity"], 10100)
        self.assertEqual(performance["equity_curve"][-1]["source"], "mt5")


if __name__ == "__main__":
    unittest.main()
