"""Unit tests for the sanitized, read-only MT5 diagnostic report."""

import unittest
from types import SimpleNamespace

from scripts.mt5_readonly_diagnostics import build_report, _masked_login


class ReadOnlyDiagnosticReportTests(unittest.TestCase):
    def test_login_is_masked(self):
        self.assertEqual(_masked_login(12345678), "****5678")
        self.assertEqual(_masked_login(None), "unavailable")

    def test_report_summarizes_positions_and_deal_lifecycles_without_sensitive_values(self):
        account = SimpleNamespace(
            login=12345678, server="Demo-Server", company="Example Broker",
            currency="USD", trade_allowed=True, balance=10000.0, equity=10100.0,
        )
        terminal = SimpleNamespace(name="MetaTrader 5", build=5000, path=r"C:\Users\private\terminal.exe")
        positions = [SimpleNamespace(symbol="XAUUSD"), SimpleNamespace(symbol="EURUSD")]
        deals = [
            SimpleNamespace(ticket=1, position_id=777, symbol="XAUUSD", entry=0, type=0,
                           volume=1.0, price=2000.0, profit=0.0, commission=-2.0,
                           swap=0.0, fee=0.0, time=100, time_msc=100000),
            SimpleNamespace(ticket=2, position_id=777, symbol="XAUUSD", entry=1, type=1,
                           volume=1.0, price=2010.0, profit=10.0, commission=-1.0,
                           swap=-0.2, fee=0.0, time=200, time_msc=200000),
        ]

        report = build_report(account, terminal, positions, deals)

        self.assertEqual(report["account"]["login_masked"], "****5678")
        self.assertEqual(report["account"]["currency"], "USD")
        self.assertEqual(report["positions"]["open_position_count"], 2)
        self.assertEqual(report["history"]["deal_count"], 2)
        self.assertEqual(report["history"]["supported_position_groups"], 1)
        self.assertEqual(report["history"]["closed_lifecycles"], 1)
        self.assertNotIn("balance", report["account"])
        self.assertNotIn("equity", report["account"])
        self.assertNotIn("path", report["terminal"])
        self.assertNotIn("12345678", repr(report))
        self.assertFalse(report["safety"]["orders_placed"])
        self.assertFalse(report["safety"]["journal_database_written"])


if __name__ == "__main__":
    unittest.main()
