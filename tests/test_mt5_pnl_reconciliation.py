"""Mocked tests for broker-authoritative MT5 P&L aggregation and persistence."""

import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

from data import TradeDatabase
from models import Trade, TradeStatus, TradeType
from mt5_service import MT5SyncService


def deal(ticket, entry, deal_type, volume, price, profit=0.0, commission=0.0, swap=0.0, fee=0.0, time=0):
    return SimpleNamespace(
        ticket=ticket,
        position_id=777,
        symbol="XAUUSD",
        entry=entry,
        type=deal_type,
        volume=volume,
        price=price,
        profit=profit,
        commission=commission,
        swap=swap,
        fee=fee,
        time=time,
        time_msc=time * 1000,
    )


class MT5DealAggregationTests(unittest.TestCase):
    def test_multiple_partial_exits_use_all_broker_deal_amounts(self):
        deals = [
            deal(1, 0, 0, 1.0, 2000.0, commission=-2.0, time=100),
            deal(2, 1, 1, 0.4, 2010.0, profit=40.0, commission=-0.8, swap=-0.1, fee=-0.05, time=200),
            deal(3, 1, 1, 0.6, 1990.0, profit=-60.0, commission=-1.2, swap=-0.2, fee=-0.05, time=300),
        ]

        result = MT5SyncService.aggregate_position_deals(deals)

        self.assertEqual(result["status"], TradeStatus.CLOSED)
        self.assertAlmostEqual(result["entry_price"], 2000.0)
        self.assertAlmostEqual(result["exit_price"], 1998.0)
        self.assertEqual(result["quantity"], 1.0)
        self.assertEqual(result["broker_gross_pnl"], -20.0)
        self.assertAlmostEqual(result["broker_net_pnl"], -24.4)
        self.assertEqual(result["deal_count"], 3)

    def test_partial_close_remains_open_and_does_not_publish_realized_broker_pnl(self):
        result = MT5SyncService.aggregate_position_deals([
            deal(1, 0, 0, 1.0, 2000.0, commission=-2.0, time=100),
            deal(2, 1, 1, 0.25, 2010.0, profit=25.0, commission=-0.5, time=200),
        ])

        self.assertEqual(result["status"], TradeStatus.OPEN)
        self.assertAlmostEqual(result["remaining_volume"], 0.75)
        self.assertAlmostEqual(result["quantity"], 0.75)
        self.assertIsNone(result["exit_price"])
        self.assertIsNone(result["broker_net_pnl"])

    def test_reversal_deal_is_rejected_for_separate_lifecycle_handling(self):
        result = MT5SyncService.aggregate_position_deals([
            deal(1, 0, 0, 1.0, 2000.0, time=100),
            deal(2, 2, 1, 1.5, 1990.0, profit=-10.0, time=200),
        ])
        self.assertIsNone(result)

    def test_missing_entry_deal_is_rejected(self):
        result = MT5SyncService.aggregate_position_deals([
            deal(2, 1, 1, 1.0, 2010.0, profit=10.0, time=200),
        ])
        self.assertIsNone(result)


class BrokerPnLPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(prefix="journal-broker-pnl-")
        self.db_path = str(Path(self.temp_dir.name) / "journal.db")
        self.db = TradeDatabase(self.db_path)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_broker_pnl_round_trips_through_database_and_overrides_price_formula(self):
        trade = Trade(
            id="MT5-777",
            symbol="XAUUSD",
            trade_type=TradeType.BUY,
            quantity=1.0,
            entry_price=2000.0,
            exit_price=1998.0,
            commission=4.0,
            swap=-0.3,
            entry_time=datetime(2026, 1, 1),
            exit_time=datetime(2026, 1, 2),
            status=TradeStatus.CLOSED,
            position_id="777",
            broker_gross_pnl=-20.0,
            broker_net_pnl=-24.4,
        )
        self.assertTrue(self.db.add_trade(trade))

        loaded = self.db.get_trade("MT5-777")
        self.assertEqual(loaded.broker_gross_pnl, -20.0)
        self.assertAlmostEqual(loaded.broker_net_pnl, -24.4)
        self.assertEqual(loaded.gross_pnl, -20.0)
        self.assertAlmostEqual(loaded.net_pnl, -24.4)

    def test_manual_trade_without_broker_values_keeps_existing_formula(self):
        trade = Trade(
            id="manual",
            symbol="TEST",
            trade_type=TradeType.BUY,
            quantity=2,
            entry_price=100,
            exit_price=105,
            commission=1,
            swap=-0.25,
            status=TradeStatus.CLOSED,
        )
        self.assertAlmostEqual(trade.gross_pnl, 10.0)
        self.assertAlmostEqual(trade.net_pnl, 8.75)


if __name__ == "__main__":
    unittest.main()
