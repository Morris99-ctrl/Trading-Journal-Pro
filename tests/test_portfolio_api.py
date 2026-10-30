"""Flask API tests for account equity capture and manual fallback labels."""

import importlib
import tempfile
from pathlib import Path
import importlib.util
import unittest
from unittest.mock import patch


class FakeWebService:
    def __init__(self, db_path=None):
        self.snapshots = []

    def record_equity_snapshot(self, **kwargs):
        self.snapshots.append(kwargs)
        return len(self.snapshots)

    def get_portfolio_accounts(self):
        return [{"account_id": "123@Broker-Demo", "currency": "USD", "snapshot_count": 2}]

    def get_portfolio_performance(self, account_id="default"):
        return {
            "status": "ok",
            "account_id": account_id,
            "snapshot_count": 2,
            "equity_curve": [],
            "total_return_pct": 1.0,
            "max_drawdown_pct": 0.5,
        }

    def record_portfolio_cash_flow(self, **kwargs):
        if not hasattr(self, "cash_flows"):
            self.cash_flows = []
        self.cash_flows.append(kwargs)
        return len(self.cash_flows)

    def capture_mt5_equity_snapshot(self):
        return {
            "success": True, "account_id": "123@Broker-Demo",
            "balance": 1000.0, "equity": 1010.0, "currency": "USD", "source": "mt5",
        }


@unittest.skipUnless(importlib.util.find_spec("flask"), "Flask is an optional runtime dependency")
class PortfolioAPITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Avoid creating a real database or MT5 connection during API tests.
        with patch("services.TradeService", FakeWebService):
            cls.web_app = importlib.import_module("web_app")
        cls.original_service = cls.web_app.service

    def setUp(self):
        self.fake_service = FakeWebService()
        self.web_app.service = self.fake_service
        self.client = self.web_app.app.test_client()

    def tearDown(self):
        self.web_app.service = self.original_service

    def test_manual_snapshot_is_namespaced_and_never_marked_as_mt5(self):
        response = self.client.post("/api/portfolio/manual-snapshot", json={
            "account_id": "my-account",
            "currency": "kes",
            "balance": 10000,
            "equity": 9800,
        })
        payload = response.get_json()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["account_id"], "manual:my-account")
        self.assertEqual(payload["source"], "manual")
        self.assertEqual(self.fake_service.snapshots[0]["source"], "manual")
        self.assertEqual(self.fake_service.snapshots[0]["currency"], "KES")
        self.assertIn("not broker verified", self.fake_service.snapshots[0]["notes"])

    def test_manual_snapshot_requires_currency(self):
        response = self.client.post("/api/portfolio/manual-snapshot", json={
            "account_id": "my-account", "balance": 100, "equity": 100,
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])
        self.assertEqual(self.fake_service.snapshots, [])

    def test_portfolio_performance_uses_requested_account(self):
        response = self.client.get("/api/portfolio/performance?account_id=123%40Broker-Demo")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["data"]["account_id"], "123@Broker-Demo")

    def test_mt5_snapshot_route_returns_broker_capture(self):
        response = self.client.post("/api/mt5/snapshot")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["source"], "mt5")

    def test_cash_flow_requires_existing_account_and_matching_currency(self):
        response = self.client.post("/api/portfolio/cash-flow", json={
            "account_id": "missing-account", "flow_type": "deposit",
            "amount": 100, "currency": "USD",
        })
        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.get_json()["success"])

        response = self.client.post("/api/portfolio/cash-flow", json={
            "account_id": "123@Broker-Demo", "flow_type": "deposit",
            "amount": 100, "currency": "KES",
        })
        self.assertEqual(response.status_code, 400)
        self.assertIn("Currency must match", response.get_json()["error"])

    def test_cash_flow_rejects_invalid_type_and_amounts(self):
        for payload in (
            {"flow_type": "transfer", "amount": 100},
            {"flow_type": "deposit", "amount": 0},
            {"flow_type": "withdrawal", "amount": -1},
            {"flow_type": "deposit", "amount": "NaN"},
            {"flow_type": "deposit", "amount": "Infinity"},
        ):
            with self.subTest(payload=payload):
                response = self.client.post("/api/portfolio/cash-flow", json={
                    "account_id": "123@Broker-Demo", "currency": "USD", **payload,
                })
                self.assertEqual(response.status_code, 400)
                self.assertFalse(response.get_json()["success"])
        self.assertFalse(getattr(self.fake_service, "cash_flows", []))

    def test_cash_flow_records_deposit_and_withdrawal(self):
        for flow_type in ("deposit", "withdrawal"):
            response = self.client.post("/api/portfolio/cash-flow", json={
                "account_id": "123@Broker-Demo", "flow_type": flow_type,
                "amount": 250, "currency": "USD", "notes": "test flow",
            })
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            self.assertTrue(response.get_json()["success"])
        self.assertEqual([flow["flow_type"] for flow in self.fake_service.cash_flows], ["deposit", "withdrawal"])
        self.assertEqual(self.fake_service.cash_flows[0]["amount"], 250)

    def test_dashboard_renders_portfolio_controls(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        for expected in (
            'id="portfolioAccountSelect"',
            'id="portfolioEquityChart"',
            'id="portfolioReturn"',
            'id="portfolioDrawdown"',
            'submitManualEquitySnapshot(event)',
            'captureMT5Equity()',
        ):
            self.assertIn(expected, html)

    def test_cash_flow_persists_in_sqlite_for_selected_account(self):
        from datetime import datetime, timezone
        from services import TradeService

        with tempfile.TemporaryDirectory(prefix="portfolio-flow-e2e-") as tmp:
            real_service = TradeService(str(Path(tmp) / "journal.db"))
            self.web_app.service = real_service
            real_service.record_equity_snapshot(
                captured_at=datetime(2026, 10, 1, 9, tzinfo=timezone.utc),
                balance=10000, equity=10000, account_id="manual:flow-test",
                currency="KES", source="manual",
            )
            response = self.client.post("/api/portfolio/cash-flow", json={
                "account_id": "manual:flow-test", "flow_type": "deposit",
                "amount": 5000, "currency": "KES",
                "occurred_at": "2026-10-01T12:00:00+00:00", "notes": "Monthly contribution",
            })
            self.assertEqual(response.status_code, 200, response.get_data(as_text=True))
            flows = real_service.db.get_portfolio_cash_flows("manual:flow-test")
            self.assertEqual(len(flows), 1)
            self.assertEqual(flows[0]["flow_type"], "deposit")
            self.assertEqual(flows[0]["amount"], 5000)
            self.assertEqual(flows[0]["currency"], "KES")
            self.assertEqual(flows[0]["notes"], "Monthly contribution")
            self.web_app.service = self.fake_service

    def test_manual_snapshot_persists_through_performance_endpoint(self):
        # Exercise the actual SQLite-backed service across the full HTTP path.
        from services import TradeService

        with tempfile.TemporaryDirectory(prefix="portfolio-api-e2e-") as tmp:
            real_service = TradeService(str(Path(tmp) / "journal.db"))
            self.web_app.service = real_service
            first = self.client.post("/api/portfolio/manual-snapshot", json={
                "account_id": "integration-test",
                "currency": "KES",
                "balance": 10000,
                "equity": 10000,
            })
            self.assertEqual(first.status_code, 200, first.get_data(as_text=True))

            second = self.client.post("/api/portfolio/manual-snapshot", json={
                "account_id": "integration-test",
                "currency": "KES",
                "balance": 10000,
                "equity": 10500,
            })
            self.assertEqual(second.status_code, 200, second.get_data(as_text=True))

            accounts = self.client.get("/api/portfolio/accounts")
            self.assertEqual(accounts.status_code, 200)
            self.assertEqual(accounts.get_json()["data"][0]["account_id"], "manual:integration-test")

            performance = self.client.get(
                "/api/portfolio/performance?account_id=manual%3Aintegration-test"
            )
            self.assertEqual(performance.status_code, 200)
            payload = performance.get_json()["data"]
            self.assertEqual(payload["snapshot_count"], 2)
            self.assertEqual(len(payload["equity_curve"]), 2)
            self.assertEqual(payload["equity_curve"][-1]["equity"], 10500)
            self.assertIsNotNone(payload["total_return_pct"])
            self.web_app.service = self.fake_service


if __name__ == "__main__":
    unittest.main()
