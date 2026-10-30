"""Flask API tests for account equity capture and manual fallback labels."""

import importlib
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


if __name__ == "__main__":
    unittest.main()
