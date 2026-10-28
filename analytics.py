"""
Trading Journal Analytics Module
High-level quantitative analytics, cohort analysis, and risk metrics.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from models import Trade, TradeStatus, AssetClass
from data import TradeDatabase
from calculators import TradingCalculator


class TradeAnalytics:
    """Quantitative analytics engine for trade journal intelligence"""

    def __init__(self, db_path: str = "trading_journal.db"):
        self.db = TradeDatabase(db_path)

    def get_period_analysis(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """Analysis for trades closed within a specified date window"""
        trades = self.db.get_all_trades(status=TradeStatus.CLOSED, start_date=start_date, end_date=end_date)
        return TradingCalculator.analyze_trade_series(trades)

    def get_win_loss_analysis(self) -> Dict[str, Any]:
        """Overall performance metrics across all closed trades"""
        trades = self.db.get_all_trades(status=TradeStatus.CLOSED)
        return TradingCalculator.analyze_trade_series(trades)

    def get_open_trades_analysis(self, price_estimates: Optional[Dict[str, float]] = None) -> Dict[str, Any]:
        """Analysis of open positions including estimated unrealized P&L and total capital at risk"""
        open_trades = self.db.get_all_trades(status=TradeStatus.OPEN)
        estimates = price_estimates or {}

        total_invested = sum(t.invested_capital for t in open_trades)
        total_risk = sum(t.planned_total_risk or 0.0 for t in open_trades)

        unrealized_pnls = []
        for t in open_trades:
            # If a price estimate is given for the symbol, use it; otherwise use entry price (0 unrealized gross)
            curr = estimates.get(t.symbol, t.entry_price)
            unrealized_pnls.append(t.calculate_unrealized_pnl(curr))

        total_unrealized = sum(unrealized_pnls)

        return {
            'open_trades_count': len(open_trades),
            'total_invested_capital': round(total_invested, 2),
            'total_planned_risk': round(total_risk, 2),
            'total_unrealized_pnl': round(total_unrealized, 2),
            'average_unrealized_pnl': round(total_unrealized / len(open_trades), 2) if open_trades else 0.0,
            'trades': open_trades
        }

    def get_monthly_performance(self) -> Dict[str, Dict[str, Any]]:
        """Performance broken down by month (YYYY-MM)"""
        trades = self.db.get_all_trades(status=TradeStatus.CLOSED)
        monthly_map: Dict[str, List[Trade]] = {}

        for trade in trades:
            dt = trade.exit_time or trade.entry_time
            if dt:
                month_key = dt.strftime("%Y-%m")
                if month_key not in monthly_map:
                    monthly_map[month_key] = []
                monthly_map[month_key].append(trade)

        result = {}
        for month_key in sorted(monthly_map.keys()):
            result[month_key] = TradingCalculator.analyze_trade_series(monthly_map[month_key])

        return result

    def get_symbol_analysis(self) -> Dict[str, Dict[str, Any]]:
        """Performance breakdown grouped by ticker symbol"""
        trades = self.db.get_all_trades(status=TradeStatus.CLOSED)
        symbol_map: Dict[str, List[Trade]] = {}

        for trade in trades:
            s = trade.symbol.upper()
            if s not in symbol_map:
                symbol_map[s] = []
            symbol_map[s].append(trade)

        return {
            symbol: TradingCalculator.analyze_trade_series(t_list)
            for symbol, t_list in symbol_map.items()
        }

    def get_setup_analysis(self) -> Dict[str, Dict[str, Any]]:
        """Performance metrics grouped by trade setup / strategy"""
        trades = self.db.get_all_trades(status=TradeStatus.CLOSED)
        setup_map: Dict[str, List[Trade]] = {}

        for trade in trades:
            setup = trade.setup or "Discretionary"
            if setup not in setup_map:
                setup_map[setup] = []
            setup_map[setup].append(trade)

        return {
            setup: TradingCalculator.analyze_trade_series(t_list)
            for setup, t_list in setup_map.items()
        }

    def get_asset_class_analysis(self) -> Dict[str, Dict[str, Any]]:
        """Performance metrics grouped by Asset Class (Stocks, Forex, Crypto, etc.)"""
        trades = self.db.get_all_trades(status=TradeStatus.CLOSED)
        asset_map: Dict[str, List[Trade]] = {}

        for trade in trades:
            ac = trade.asset_class.value
            if ac not in asset_map:
                asset_map[ac] = []
            asset_map[ac].append(trade)

        return {
            ac: TradingCalculator.analyze_trade_series(t_list)
            for ac, t_list in asset_map.items()
        }

    def get_performance_trends(self, days: int = 30) -> List[Dict[str, Any]]:
        """Weekly rolling performance trend buckets"""
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days)

        trends = []
        step_days = 7
        current_start = start_date

        while current_start < end_date:
            current_end = min(current_start + timedelta(days=step_days), end_date)
            analysis = self.get_period_analysis(current_start, current_end)
            trends.append({
                'period_start': current_start.strftime("%Y-%m-%d"),
                'period_end': current_end.strftime("%Y-%m-%d"),
                'analysis': analysis
            })
            current_start += timedelta(days=step_days)

        return trends

    def get_risk_metrics(self) -> Dict[str, Any]:
        """Value at Risk (VaR), Expected Shortfall, and downside ratios"""
        trades = self.db.get_all_trades(status=TradeStatus.CLOSED)
        analysis = TradingCalculator.analyze_trade_series(trades)

        pnls = [t.net_pnl for t in trades if t.net_pnl is not None]
        var_95 = 0.0
        expected_shortfall = 0.0

        if pnls:
            sorted_pnls = sorted(pnls)
            cutoff_idx = max(0, int(len(sorted_pnls) * 0.05))
            var_95 = abs(sorted_pnls[cutoff_idx]) if sorted_pnls[cutoff_idx] < 0 else 0.0
            tail_losses = [abs(p) for p in sorted_pnls[:cutoff_idx + 1] if p < 0]
            if tail_losses:
                import statistics
                expected_shortfall = statistics.mean(tail_losses)

        return {
            'volatility': analysis.get('pnl_std_dev', 0.0),
            'max_drawdown': analysis.get('max_drawdown', 0.0),
            'max_drawdown_pct': analysis.get('max_drawdown_pct', 0.0),
            'sharpe_ratio': analysis.get('sharpe_ratio', 0.0),
            'sortino_ratio': analysis.get('sortino_ratio', 0.0),
            'calmar_ratio': analysis.get('calmar_ratio', 0.0),
            'var_95': round(var_95, 2),
            'expected_shortfall': round(expected_shortfall, 2)
        }
