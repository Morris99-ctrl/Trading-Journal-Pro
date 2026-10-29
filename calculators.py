"""
Trading Journal Calculator
Advanced financial calculations, statistical analysis, risk ratios, and position sizing.
"""

import math
import statistics
from datetime import datetime
from typing import List, Dict, Any, Optional
from models import Trade, TradeStatus, TradeType


class TradingCalculator:
    """Comprehensive financial and quantitative calculations for trading"""

    @staticmethod
    def calculate_realized_pnl(trade: Trade) -> float:
        """Calculate net realized P&L for a closed trade"""
        if trade.status != TradeStatus.CLOSED or trade.exit_price is None:
            return 0.0
        return trade.net_pnl if trade.net_pnl is not None else 0.0

    @staticmethod
    def calculate_unrealized_pnl(trade: Trade, current_price: float) -> float:
        """Calculate unrealized P&L for an open trade"""
        return trade.calculate_unrealized_pnl(current_price)

    @staticmethod
    def calculate_risk_reward_ratio(trade: Trade) -> Optional[float]:
        """Calculate planned Reward-to-Risk ratio"""
        return trade.planned_risk_reward

    @staticmethod
    def calculate_position_size(
        account_size: float,
        risk_percentage: float,
        entry_price: float,
        stop_loss: float
    ) -> Dict[str, Any]:
        """
        Calculate professional position sizing based on fixed percentage risk.
        Returns units/shares, dollar risk, position capital, and leverage ratio.
        """
        if account_size <= 0:
            raise ValueError("Account size must be greater than zero")
        if risk_percentage <= 0 or risk_percentage > 100:
            raise ValueError("Risk percentage must be between 0 and 100")
        if entry_price <= 0 or stop_loss <= 0:
            raise ValueError("Prices must be greater than zero")

        dollar_risk = account_size * (risk_percentage / 100.0)
        risk_per_unit = abs(entry_price - stop_loss)

        if risk_per_unit == 0:
            return {
                "shares": 0,
                "dollar_risk": 0.0,
                "position_value": 0.0,
                "leverage": 0.0,
                "risk_per_unit": 0.0
            }

        shares = dollar_risk / risk_per_unit
        position_value = shares * entry_price
        leverage = position_value / account_size

        return {
            "shares": round(shares, 4),
            "dollar_risk": round(dollar_risk, 2),
            "position_value": round(position_value, 2),
            "leverage": round(leverage, 2),
            "risk_per_unit": round(risk_per_unit, 4)
        }

    @staticmethod
    def calculate_streaks(trades: List[Trade]) -> Dict[str, int]:
        """Calculate max winning streak, max losing streak, and current streak"""
        closed_trades = [t for t in trades if t.is_closed and t.exit_price is not None]
        # Sort chronologically by exit time or entry time
        closed_trades = sorted(closed_trades, key=lambda t: t.exit_time or t.entry_time or datetime.min)

        max_win_streak = 0
        max_loss_streak = 0
        current_streak = 0  # positive for wins, negative for losses
        temp_win = 0
        temp_loss = 0

        for trade in closed_trades:
            pnl = trade.net_pnl or 0.0
            if pnl > 0:
                temp_win += 1
                temp_loss = 0
                max_win_streak = max(max_win_streak, temp_win)
                current_streak = current_streak + 1 if current_streak > 0 else 1
            elif pnl < 0:
                temp_loss += 1
                temp_win = 0
                max_loss_streak = max(max_loss_streak, temp_loss)
                current_streak = current_streak - 1 if current_streak < 0 else -1
            else:
                temp_win = 0
                temp_loss = 0
                current_streak = 0

        return {
            "max_win_streak": max_win_streak,
            "max_loss_streak": max_loss_streak,
            "current_streak": current_streak
        }

    @staticmethod
    def calculate_drawdown_series(trades: List[Trade], initial_balance: float = 10000.0) -> Dict[str, Any]:
        """Calculate realized-equity curve and peak-to-trough drawdown."""
        if initial_balance <= 0:
            raise ValueError("Initial balance must be greater than zero")

        closed_trades = [t for t in trades if t.is_closed and t.exit_price is not None]

        def close_time(trade: Trade) -> datetime:
            return trade.exit_time or trade.entry_time or datetime.min

        # Epoch keys avoid Python errors when naive and aware datetimes are mixed.
        def sort_key(trade: Trade) -> float:
            timestamp = close_time(trade)
            try:
                return timestamp.timestamp()
            except (OSError, OverflowError, ValueError):
                return timestamp.replace(tzinfo=None).toordinal() * 86400 + (
                    timestamp.hour * 3600 + timestamp.minute * 60 + timestamp.second
                )

        closed_trades.sort(key=sort_key)
        current_balance = initial_balance
        peak = initial_balance
        max_dd_dollars = 0.0
        max_dd_pct = 0.0

        first_timestamp = (
            close_time(closed_trades[0]).isoformat()
            if closed_trades else datetime.now().isoformat()
        )
        equity_curve = [{"time": first_timestamp, "equity": round(initial_balance, 2)}]

        for trade in closed_trades:
            current_balance += trade.net_pnl or 0.0
            equity_curve.append({
                "time": close_time(trade).isoformat(),
                "equity": round(current_balance, 2),
            })

            if current_balance > peak:
                peak = current_balance
            else:
                drawdown_dollars = peak - current_balance
                drawdown_pct = drawdown_dollars / peak * 100.0
                max_dd_dollars = max(max_dd_dollars, drawdown_dollars)
                max_dd_pct = max(max_dd_pct, drawdown_pct)

        current_dd_dollars = max(0.0, peak - current_balance)
        current_dd_pct = current_dd_dollars / peak * 100.0

        return {
            "initial_balance": round(initial_balance, 2),
            "current_balance": round(current_balance, 2),
            "peak_balance": round(peak, 2),
            "max_drawdown_dollars": round(max_dd_dollars, 2),
            "max_drawdown_pct": round(max_dd_pct, 2),
            "current_drawdown_dollars": round(current_dd_dollars, 2),
            "current_drawdown_pct": round(current_dd_pct, 2),
            "equity_curve": equity_curve
        }

    @staticmethod
    def calculate_sharpe_ratio(returns: List[float], risk_free_rate: float = 0.0) -> float:
        """Calculate an unannualized, per-observation Sharpe ratio.

        Returns must be decimal returns from a consistent observation period.
        Trade-by-trade returns are not daily portfolio returns, so they must not
        be annualized with an assumed 252 trades per year. The risk-free rate,
        when supplied, must be expressed per observation rather than annually.
        """
        if len(returns) < 2:
            return 0.0
        mean_excess_return = statistics.mean(returns) - risk_free_rate
        std_ret = statistics.stdev(returns)
        if std_ret <= 1e-9:
            return 0.0
        return mean_excess_return / std_ret

    @staticmethod
    def calculate_sortino_ratio(returns: List[float], target_return: float = 0.0) -> float:
        """Calculate an unannualized, per-observation Sortino ratio.

        Returns and target_return must use the same observation frequency.
        Downside deviation is calculated across all observations, treating
        observations at or above the target as zero downside.
        """
        if len(returns) < 2:
            return 0.0

        mean_excess_return = statistics.mean(returns) - target_return
        downside_squares = [min(0.0, r - target_return) ** 2 for r in returns]
        downside_deviation = math.sqrt(sum(downside_squares) / len(returns))
        if downside_deviation <= 1e-9:
            return float('inf') if mean_excess_return > 0 else 0.0
        return mean_excess_return / downside_deviation

    @staticmethod
    def analyze_trade_series(trades: List[Trade], initial_balance: float = 10000.0) -> Dict[str, Any]:
        """Comprehensive analysis of closed trades with advanced quantitative metrics"""
        closed_trades = [t for t in trades if t.is_closed and t.exit_price is not None]
        if not closed_trades:
            return TradingCalculator._empty_analysis(initial_balance)

        pnl_values = [t.net_pnl or 0.0 for t in closed_trades]
        win_pnls = [p for p in pnl_values if p > 0]
        loss_pnls = [p for p in pnl_values if p < 0]
        breakeven_pnls = [p for p in pnl_values if p == 0]

        total_trades = len(closed_trades)
        winning_trades = len(win_pnls)
        losing_trades = len(loss_pnls)
        breakeven_trades = len(breakeven_pnls)

        gross_profit = sum(win_pnls)
        gross_loss = abs(sum(loss_pnls))
        total_pnl = sum(pnl_values)
        total_commissions = sum(t.commission for t in closed_trades)

        win_rate = (winning_trades / total_trades * 100.0) if total_trades > 0 else 0.0
        loss_rate = (losing_trades / total_trades * 100.0) if total_trades > 0 else 0.0

        average_win = statistics.mean(win_pnls) if win_pnls else 0.0
        average_loss = abs(statistics.mean(loss_pnls)) if loss_pnls else 0.0
        win_loss_ratio = (average_win / average_loss) if average_loss > 0 else (float('inf') if average_win > 0 else 0.0)

        average_trade = statistics.mean(pnl_values) if pnl_values else 0.0
        profit_factor = (gross_profit / gross_loss) if gross_loss > 0 else (float('inf') if gross_profit > 0 else 0.0)

        # Mathematical expectancy: (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
        p_win = winning_trades / total_trades if total_trades > 0 else 0.0
        p_loss = losing_trades / total_trades if total_trades > 0 else 0.0
        expectancy = (p_win * average_win) - (p_loss * average_loss)

        # R-Multiple metrics
        r_multiples = [t.r_multiple for t in closed_trades if t.r_multiple is not None]
        avg_r_multiple = statistics.mean(r_multiples) if r_multiples else 0.0

        # Drawdown analysis
        dd_data = TradingCalculator.calculate_drawdown_series(closed_trades, initial_balance)
        max_drawdown_dollars = dd_data["max_drawdown_dollars"]
        max_drawdown_pct = dd_data["max_drawdown_pct"]

        # Recovery factor: Net Profit / Max Drawdown
        recovery_factor = (total_pnl / max_drawdown_dollars) if max_drawdown_dollars > 0 else float('inf')

        # Trade-level position returns: useful for per-trade diagnostics, not portfolio-period risk ratios.
        return_pcts = [t.return_pct / 100.0 for t in closed_trades if t.return_pct is not None]
        sharpe = TradingCalculator.calculate_sharpe_ratio(return_pcts) if return_pcts else 0.0
        sortino = TradingCalculator.calculate_sortino_ratio(return_pcts) if return_pcts else 0.0

        # Calmar Ratio: Return % / Max Drawdown %
        total_return_pct = (total_pnl / initial_balance * 100.0) if initial_balance > 0 else 0.0
        calmar = (total_return_pct / max_drawdown_pct) if max_drawdown_pct > 0 else 0.0

        streaks = TradingCalculator.calculate_streaks(closed_trades)

        # Directional breakdown
        long_trades = [t for t in closed_trades if t.is_long]
        short_trades = [t for t in closed_trades if t.is_short]

        long_pnl = sum(t.net_pnl or 0.0 for t in long_trades)
        short_pnl = sum(t.net_pnl or 0.0 for t in short_trades)
        long_win_rate = (len([t for t in long_trades if (t.net_pnl or 0) > 0]) / len(long_trades) * 100.0) if long_trades else 0.0
        short_win_rate = (len([t for t in short_trades if (t.net_pnl or 0) > 0]) / len(short_trades) * 100.0) if short_trades else 0.0

        return {
            "total_trades": total_trades,
            "winning_trades": winning_trades,
            "losing_trades": losing_trades,
            "breakeven_trades": breakeven_trades,
            "win_rate": round(win_rate, 2),
            "loss_rate": round(loss_rate, 2),
            "total_pnl": round(total_pnl, 2),
            "gross_profit": round(gross_profit, 2),
            "gross_loss": round(gross_loss, 2),
            "total_commissions": round(total_commissions, 2),
            "average_win": round(average_win, 2),
            "average_loss": round(average_loss, 2),
            "win_loss_ratio": round(win_loss_ratio, 2) if win_loss_ratio != float('inf') else "inf",
            "average_trade": round(average_trade, 2),
            "profit_factor": round(profit_factor, 2) if profit_factor != float('inf') else "inf",
            "expectancy": round(expectancy, 2),
            "avg_r_multiple": round(avg_r_multiple, 2),
            "best_trade": round(max(pnl_values), 2) if pnl_values else 0.0,
            "worst_trade": round(min(pnl_values), 2) if pnl_values else 0.0,
            "pnl_std_dev": round(statistics.stdev(pnl_values), 2) if len(pnl_values) > 1 else 0.0,
            "max_drawdown": round(max_drawdown_dollars, 2),
            "max_drawdown_pct": round(max_drawdown_pct, 2),
            "recovery_factor": round(recovery_factor, 2) if recovery_factor != float('inf') else "inf",
            "sharpe_ratio": round(sharpe, 2),
            "sortino_ratio": round(sortino, 2) if sortino != float('inf') else "inf",
            "calmar_ratio": round(calmar, 2),
            "max_win_streak": streaks["max_win_streak"],
            "max_loss_streak": streaks["max_loss_streak"],
            "current_streak": streaks["current_streak"],
            "long_trades_count": len(long_trades),
            "long_pnl": round(long_pnl, 2),
            "long_win_rate": round(long_win_rate, 2),
            "short_trades_count": len(short_trades),
            "short_pnl": round(short_pnl, 2),
            "short_win_rate": round(short_win_rate, 2),
            "equity_curve": dd_data["equity_curve"]
        }

    @staticmethod
    def _empty_analysis(initial_balance: float = 10000.0) -> Dict[str, Any]:
        """Default response when no closed trades exist"""
        return {
            "total_trades": 0,
            "winning_trades": 0,
            "losing_trades": 0,
            "breakeven_trades": 0,
            "win_rate": 0.0,
            "loss_rate": 0.0,
            "total_pnl": 0.0,
            "gross_profit": 0.0,
            "gross_loss": 0.0,
            "total_commissions": 0.0,
            "average_win": 0.0,
            "average_loss": 0.0,
            "win_loss_ratio": 0.0,
            "average_trade": 0.0,
            "profit_factor": 0.0,
            "expectancy": 0.0,
            "avg_r_multiple": 0.0,
            "best_trade": 0.0,
            "worst_trade": 0.0,
            "pnl_std_dev": 0.0,
            "max_drawdown": 0.0,
            "max_drawdown_pct": 0.0,
            "recovery_factor": 0.0,
            "sharpe_ratio": 0.0,
            "sortino_ratio": 0.0,
            "calmar_ratio": 0.0,
            "max_win_streak": 0,
            "max_loss_streak": 0,
            "current_streak": 0,
            "long_trades_count": 0,
            "long_pnl": 0.0,
            "long_win_rate": 0.0,
            "short_trades_count": 0,
            "short_pnl": 0.0,
            "short_win_rate": 0.0,
            "equity_curve": [{"time": datetime.now().isoformat(), "equity": initial_balance}]
        }
