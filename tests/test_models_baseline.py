"""Safe, isolated characterization tests for the Trade domain model.

Run from the repository root with:
    python -m unittest discover -s tests -v

These tests use in-memory Python objects only and never open or delete journal files.
"""
import unittest

from models import Trade, TradeStatus, TradeType


class TradeModelBaselineTests(unittest.TestCase):
    def test_long_trade_realized_pnl_after_costs(self):
        trade = Trade(
            id="baseline-long",
            symbol="TEST",
            trade_type=TradeType.BUY,
            quantity=10,
            entry_price=100.0,
            commission=2.0,
            swap=0.5,
        )

        trade.close_trade(exit_price=110.0)

        self.assertEqual(trade.status, TradeStatus.CLOSED)
        self.assertAlmostEqual(trade.gross_pnl, 100.0)
        self.assertAlmostEqual(trade.net_pnl, 98.5)

    def test_short_trade_realized_pnl_after_costs(self):
        trade = Trade(
            id="baseline-short",
            symbol="TEST",
            trade_type=TradeType.SHORT,
            quantity=4,
            entry_price=50.0,
            commission=1.0,
            swap=-0.25,
        )

        trade.close_trade(exit_price=45.0)

        self.assertAlmostEqual(trade.gross_pnl, 20.0)
        self.assertAlmostEqual(trade.net_pnl, 18.75)

    def test_open_trade_has_no_realized_pnl(self):
        trade = Trade(
            id="baseline-open",
            symbol="TEST",
            trade_type=TradeType.BUY,
            quantity=1,
            entry_price=100.0,
        )

        self.assertTrue(trade.is_open)
        self.assertIsNone(trade.gross_pnl)
        self.assertIsNone(trade.net_pnl)

    def test_closing_a_closed_trade_is_rejected(self):
        trade = Trade(
            id="baseline-closed",
            symbol="TEST",
            trade_type=TradeType.BUY,
            quantity=1,
            entry_price=100.0,
        )
        trade.close_trade(exit_price=101.0)

        with self.assertRaises(ValueError):
            trade.close_trade(exit_price=102.0)

    def test_to_dict_contains_core_fields(self):
        trade = Trade(
            id="baseline-serialize",
            symbol="TEST",
            trade_type=TradeType.BUY,
            quantity=2,
            entry_price=10.0,
        )

        result = trade.to_dict()

        self.assertEqual(result["id"], "baseline-serialize")
        self.assertEqual(result["symbol"], "TEST")
        self.assertEqual(result["trade_type"], "BUY")
        self.assertIsNone(result["net_pnl"])


if __name__ == "__main__":
    unittest.main()
