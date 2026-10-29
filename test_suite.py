import sys
import os
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models import Trade, TradeType, TradeStatus, AssetClass
from services import TradeService
from calculators import TradingCalculator
from analytics import TradeAnalytics


def run_tests():
    print("Testing models...")
    t_long = Trade(id="T1", symbol="AAPL", trade_type=TradeType.BUY, quantity=100, entry_price=150.0)
    t_long.close_trade(exit_price=160.0)
    assert t_long.net_pnl == 1000.0, f"Expected 1000, got {t_long.net_pnl}"
    assert t_long.is_long is True
    assert t_long.is_short is False

    t_short = Trade(id="T2", symbol="TSLA", trade_type=TradeType.SHORT, quantity=50, entry_price=250.0, stop_loss=260.0, take_profit=230.0)
    t_short.close_trade(exit_price=235.0)
    assert t_short.net_pnl == 750.0, f"Expected 750, got {t_short.net_pnl}"
    assert t_short.is_short is True
    assert t_short.is_long is False
    assert t_short.planned_risk_per_unit == 10.0, f"Expected risk 10, got {t_short.planned_risk_per_unit}"
    assert t_short.planned_reward_per_unit == 20.0, f"Expected reward 20, got {t_short.planned_reward_per_unit}"
    assert t_short.planned_risk_reward == 2.0, f"Expected RR 2.0, got {t_short.planned_risk_reward}"
    print("Models tests passed!")

        with tempfile.TemporaryDirectory(prefix="trading-journal-tests-") as temp_dir:
        test_db = os.path.join(temp_dir, "test_trading.db")
        print("Testing services & database...")
        srv = TradeService(test_db)
        assert len(srv.get_all_trades()) == 0
        srv.seed_sample_data()
        trades = srv.get_all_trades()
        assert len(trades) > 0, "Seed should populate trades"
        perf = srv.get_performance_summary()
        assert "total_trades" in perf
        assert "win_rate" in perf
        assert "profit_factor" in perf
        assert "expectancy" in perf
        assert "sharpe_ratio" in perf
        assert "sortino_ratio" in perf
        print(f"Populated {len(trades)} sample trades. Win rate: {perf['win_rate']}%, Net P&L: ${perf['total_pnl']}")

        print("Testing position calculator...")
        res = TradingCalculator.calculate_position_size(
            account_size=25000, risk_percentage=1.0, entry_price=150.0, stop_loss=145.0
        )
        assert res["dollar_risk"] == 250.0
        assert res["shares"] == 50.0
        assert res["position_value"] == 7500.0
        print("Position calculator passed:", res)

        print("Testing CSV Export/Import...")
            export_file = os.path.join(temp_dir, "test_export.csv")
        count = srv.export_csv(export_file)
        assert count == len(trades)
        assert os.path.exists(export_file)

        # Test import into a fresh DB
            import_db = os.path.join(temp_dir, "test_import.db")
        srv_import = TradeService(import_db)
        imported_count = srv_import.import_csv(export_file)
        assert imported_count == count
        print(f"CSV Export/Import passed: {imported_count} trades verified.")

        print("\nALL VERIFICATION TESTS COMPLETED SUCCESSFULLY!")


if __name__ == "__main__":
    run_tests()

