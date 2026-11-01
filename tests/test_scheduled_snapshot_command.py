"""Tests for the one-shot scheduled MT5 equity snapshot command."""

import unittest
from unittest.mock import Mock

from scripts.capture_scheduled_snapshot import _masked_account_id, capture_once


class ScheduledSnapshotCommandTests(unittest.TestCase):
    def test_account_login_is_masked_in_command_output(self):
        self.assertEqual(_masked_account_id("12345678@Demo-Server"), "****5678@Demo-Server")
        self.assertEqual(_masked_account_id("12@Demo-Server"), "****@Demo-Server")
        self.assertEqual(_masked_account_id(None), "unavailable")

    def test_capture_once_reports_snapshot_without_exposing_full_login(self):
        service = Mock()
        service.capture_mt5_equity_snapshot.return_value = {
            "success": True,
            "snapshot_id": 42,
            "account_id": "12345678@Demo-Server",
            "captured_at": "2026-10-30T09:00:00+03:00",
            "currency": "KES",
            "source": "mt5",
        }

        result = capture_once(service)

        service.capture_mt5_equity_snapshot.assert_called_once_with()
        self.assertTrue(result["success"])
        self.assertEqual(result["snapshot_id"], 42)
        self.assertEqual(result["account_id"], "****5678@Demo-Server")
        self.assertEqual(result["currency"], "KES")
        self.assertFalse(result["orders_placed"])
        self.assertNotIn("12345678", repr(result))


if __name__ == "__main__":
    unittest.main()
