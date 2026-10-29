"""
Trading Journal Service Layer
Business logic, trade management workflows, MT5 auto-sync, sample data generator, and export/import services.
"""

import random
import string
import shutil
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path
from models import Trade, TradeType, TradeStatus, AssetClass
from data import TradeDatabase
from calculators import TradingCalculator
from portfolio_analytics import calculate_portfolio_performance
from mt5_service import MT5SyncService


class TradeService:
    """Core service orchestrating data persistence, trade lifecycle, MT5 sync, and reporting"""

    def __init__(self, db_path: str = "trading_journal.db"):
        self.db = TradeDatabase(db_path)
        self.mt5_sync = MT5SyncService()
        self.screenshots_dir = Path("screenshots").resolve()
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def generate_trade_id() -> str:
        """Generate a clean unique trade ID (e.g., TRD-7K2X)"""
        suffix = ''.join(random.choices(string.ascii_uppercase + string.digits, k=5))
        return f"TRD-{suffix}"

    def create_trade(self, **kwargs) -> Trade:
        """Create and persist a new trade"""
        trade_id = kwargs.pop('id', None) or self.generate_trade_id()

        # Parse string enums if supplied
        if isinstance(kwargs.get('trade_type'), str):
            kwargs['trade_type'] = TradeType(kwargs['trade_type'].upper())
        if isinstance(kwargs.get('status'), str):
            kwargs['status'] = TradeStatus(kwargs['status'].upper())
        if isinstance(kwargs.get('asset_class'), str):
            kwargs['asset_class'] = AssetClass(kwargs['asset_class'].upper())

        # Ensure entry_time
        if 'entry_time' not in kwargs or kwargs['entry_time'] is None:
            kwargs['entry_time'] = datetime.now()

        trade = Trade(id=trade_id, **kwargs)
        self.db.add_trade(trade)
        return trade

    def get_trade(self, trade_id: str) -> Optional[Trade]:
        """Get trade by ID"""
        return self.db.get_trade(trade_id)

    def get_all_trades(
        self,
        status: Optional[TradeStatus] = None,
        symbol: Optional[str] = None,
        asset_class: Optional[AssetClass] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        date_basis: str = "entry"
    ) -> List[Trade]:
        """Get matching trades; date_basis may be 'entry' or 'exit'."""
        return self.db.get_all_trades(
            status=status,
            symbol=symbol,
            asset_class=asset_class,
            start_date=start_date,
            end_date=end_date,
            date_basis=date_basis
        )

    def get_open_trades(self) -> List[Trade]:
        """Get all currently open positions"""
        return self.db.get_all_trades(status=TradeStatus.OPEN)

    def get_closed_trades(self) -> List[Trade]:
        """Get all closed trades"""
        return self.db.get_all_trades(status=TradeStatus.CLOSED)

    def close_trade(
        self,
        trade_id: str,
        exit_price: float,
        exit_time: Optional[datetime] = None,
        commission: float = 0.0,
        swap: float = 0.0,
        notes: Optional[str] = None
    ) -> Optional[Trade]:
        """Close an active position and update the database"""
        trade = self.db.get_trade(trade_id)
        if trade and trade.is_open:
            trade.close_trade(
                exit_price=exit_price,
                exit_time=exit_time or datetime.now(),
                commission=commission,
                swap=swap,
                notes=notes
            )
            self.db.update_trade(trade)
            return trade
        return None

    def update_trade(self, trade: Trade) -> bool:
        """Update trade attributes"""
        return self.db.update_trade(trade)

    def delete_trade(self, trade_id: str) -> bool:
        """Delete trade by ID"""
        return self.db.delete_trade(trade_id)

    def get_performance_summary(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        initial_balance: float = 10000.0
    ) -> Dict[str, Any]:
        """Calculate complete performance report and metrics"""
        trades = self.get_all_trades(
            status=TradeStatus.CLOSED,
            start_date=start_date,
            end_date=end_date,
            date_basis="exit"
        )
        return TradingCalculator.analyze_trade_series(trades, initial_balance=initial_balance)

    def get_trade_history(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Historical trades and metrics"""
        performance = self.get_performance_summary(start_date, end_date)
        return {
            'period': {
                'start_date': start_date.isoformat() if start_date else None,
                'end_date': end_date.isoformat() if end_date else None
            },
            'performance': performance,
            'trades': self.get_all_trades(
                start_date=start_date,
                end_date=end_date,
                date_basis="exit"
            )
        }

    # Portfolio-level equity and risk analytics
    def record_equity_snapshot(
        self, captured_at: datetime, balance: float, equity: float,
        account_id: str = "default", currency: str = "",
        source: str = "manual", notes: str = "",
    ) -> int:
        """Record an actual broker/account balance and equity observation."""
        return self.db.add_equity_snapshot(
            captured_at=captured_at, balance=balance, equity=equity,
            account_id=account_id, currency=currency, source=source, notes=notes,
        )

    def record_portfolio_cash_flow(
        self, occurred_at: datetime, flow_type: str, amount: float,
        account_id: str = "default", currency: str = "", notes: str = "",
    ) -> int:
        """Record an external deposit or withdrawal, not a trading P&L event."""
        return self.db.add_portfolio_cash_flow(
            occurred_at=occurred_at, flow_type=flow_type, amount=amount,
            account_id=account_id, currency=currency, notes=notes,
        )

    def get_portfolio_performance(
        self, account_id: str = "default",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        """Return cash-flow-adjusted portfolio returns from stored equity snapshots."""
        snapshots = self.db.get_equity_snapshots(account_id, start_date, end_date)
        flows = self.db.get_portfolio_cash_flows(account_id, start_date, end_date)
        normalized_flows = [
            {"occurred_at": flow["occurred_at"], "type": flow["flow_type"], "amount": flow["amount"], "currency": flow["currency"]}
            for flow in flows
        ]
        result = calculate_portfolio_performance(snapshots, normalized_flows)
        result["account_id"] = account_id
        result["currency"] = next((item["currency"] for item in snapshots if item["currency"]), "")
        return result

    # MetaTrader 5 Sync Methods
    def get_mt5_status(self) -> Dict[str, Any]:
        """Get live MT5 connection status"""
        return self.mt5_sync.get_terminal_status()

    def sync_mt5(self, days_back: int = 60) -> Dict[str, Any]:
        """Perform one-click MT5 synchronization"""
        return self.mt5_sync.sync_trades(self, days_back=days_back)

    # Daily Prep and Reflection Journal
    def save_daily_log(
        self,
        date_str: str,
        market_bias: str = "Neutral",
        news_events: str = "",
        rules_checked: bool = True,
        mindset_score: int = 5,
        post_market_notes: str = ""
    ) -> bool:
        """Save or update daily journal prep and review"""
        return self.db.save_daily_log(
            date_str=date_str,
            market_bias=market_bias,
            news_events=news_events,
            rules_checked=rules_checked,
            mindset_score=mindset_score,
            post_market_notes=post_market_notes
        )

    def get_daily_log(self, date_str: str) -> Optional[Dict[str, Any]]:
        """Get daily log by date"""
        return self.db.get_daily_log(date_str)

    def get_all_daily_logs(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Get list of recent daily journal logs"""
        return self.db.get_all_daily_logs(limit=limit)

    # Screenshot handling
    def attach_screenshot(self, trade_id: str, file_path: str) -> bool:
        """Attach a chart screenshot to a trade"""
        trade = self.get_trade(trade_id)
        if not trade:
            return False
        trade.screenshot_path = file_path
        return self.update_trade(trade)

    def export_csv(self, file_path: str = "trades_export.csv") -> int:
        """Export trades to CSV"""
        return self.db.export_csv(file_path)

    def import_csv(self, file_path: str) -> int:
        """Import trades from CSV"""
        return self.db.import_csv(file_path)

    def create_backup(self) -> Optional[str]:
        """Manually trigger a database backup"""
        return self.db.auto_backup()

    def list_backups(self) -> List[Dict[str, Any]]:
        """List historical backups"""
        return self.db.list_backups()

    def seed_sample_data(self, clear_first: bool = False):
        """Seed realistic institutional-grade sample trades across multiple asset classes"""
        if clear_first:
            self.db.clear_all_trades()

        now = datetime.now()

        samples = [
            # Closed Trades - Winning Breakout
            {
                "symbol": "NVDA",
                "trade_type": TradeType.BUY,
                "asset_class": AssetClass.STOCKS,
                "quantity": 50,
                "entry_price": 120.50,
                "exit_price": 138.20,
                "stop_loss": 115.00,
                "take_profit": 136.00,
                "commission": 2.50,
                "entry_time": now - timedelta(days=28),
                "exit_time": now - timedelta(days=22),
                "status": TradeStatus.CLOSED,
                "setup": "Bull Flag Breakout",
                "rating": 5,
                "discipline_rating": 5,
                "tags": "Followed Plan, A+ Setup, Key Level",
                "session": "NY",
                "notes": "Strong earnings follow-through. Trailed stop above 20 EMA."
            },
            # Closed Trades - Winning Short
            {
                "symbol": "TSLA",
                "trade_type": TradeType.SHORT,
                "asset_class": AssetClass.STOCKS,
                "quantity": 40,
                "entry_price": 260.00,
                "exit_price": 235.00,
                "stop_loss": 272.00,
                "take_profit": 230.00,
                "commission": 3.00,
                "entry_time": now - timedelta(days=21),
                "exit_time": now - timedelta(days=16),
                "status": TradeStatus.CLOSED,
                "setup": "Double Top Breakdown",
                "rating": 4,
                "discipline_rating": 5,
                "tags": "Followed Plan, High R:R",
                "session": "NY",
                "notes": "Rejected key resistance. Covered in scale at target."
            },
            # Closed Trades - Managed Loss
            {
                "symbol": "AAPL",
                "trade_type": TradeType.BUY,
                "asset_class": AssetClass.STOCKS,
                "quantity": 100,
                "entry_price": 182.00,
                "exit_price": 178.50,
                "stop_loss": 178.50,
                "take_profit": 192.00,
                "commission": 2.00,
                "entry_time": now - timedelta(days=15),
                "exit_time": now - timedelta(days=13),
                "status": TradeStatus.CLOSED,
                "setup": "Support Bounce",
                "rating": 3,
                "discipline_rating": 5,
                "tags": "Disciplined Stop Loss",
                "session": "NY",
                "notes": "Market broad selloff triggered stop. Good discipline adhering to risk plan."
            },
            # Closed Trades - Crypto Winner
            {
                "symbol": "BTCUSDT",
                "trade_type": TradeType.BUY,
                "asset_class": AssetClass.CRYPTO,
                "quantity": 0.25,
                "entry_price": 62500.00,
                "exit_price": 67800.00,
                "stop_loss": 60800.00,
                "take_profit": 67000.00,
                "commission": 6.50,
                "entry_time": now - timedelta(days=12),
                "exit_time": now - timedelta(days=7),
                "status": TradeStatus.CLOSED,
                "setup": "Daily S/R Flip",
                "rating": 5,
                "discipline_rating": 5,
                "tags": "High Volume, Trend Continuation",
                "session": "London",
                "notes": "Weekly level retested cleanly. Target reached with strong volume."
            },
            # Closed Trades - Forex Winner
            {
                "symbol": "EURUSD",
                "trade_type": TradeType.SHORT,
                "asset_class": AssetClass.FOREX,
                "quantity": 10000,
                "entry_price": 1.0920,
                "exit_price": 1.0830,
                "stop_loss": 1.0960,
                "take_profit": 1.0820,
                "commission": 1.50,
                "entry_time": now - timedelta(days=8),
                "exit_time": now - timedelta(days=4),
                "status": TradeStatus.CLOSED,
                "setup": "Order Block Retest",
                "rating": 4,
                "discipline_rating": 4,
                "tags": "News Follow-through",
                "session": "London",
                "notes": "Fed speech dovish sentiment. Nice 2.25R outcome."
            },
            # Closed Trades - Loss Short
            {
                "symbol": "AMD",
                "trade_type": TradeType.SHORT,
                "asset_class": AssetClass.STOCKS,
                "quantity": 60,
                "entry_price": 155.00,
                "exit_price": 161.00,
                "stop_loss": 161.00,
                "take_profit": 142.00,
                "commission": 2.00,
                "entry_time": now - timedelta(days=6),
                "exit_time": now - timedelta(days=3),
                "status": TradeStatus.CLOSED,
                "setup": "Resistance Rejection",
                "rating": 2,
                "discipline_rating": 3,
                "tags": "Early Entry",
                "session": "NY",
                "notes": "Squeezed above resistance on unexpected AI semiconductor upgrade."
            },
            # Open Trade 1 - High Potential Breakout
            {
                "symbol": "MSFT",
                "trade_type": TradeType.BUY,
                "asset_class": AssetClass.STOCKS,
                "quantity": 75,
                "entry_price": 420.00,
                "stop_loss": 412.00,
                "take_profit": 445.00,
                "commission": 3.00,
                "entry_time": now - timedelta(days=2),
                "status": TradeStatus.OPEN,
                "setup": "All-Time High Breakout",
                "rating": 5,
                "discipline_rating": 5,
                "tags": "Breakout",
                "session": "NY",
                "notes": "Holding above previous ATH. Good volume accumulation."
            },
            # Open Trade 2 - Mean Reversion
            {
                "symbol": "ETHUSDT",
                "trade_type": TradeType.BUY,
                "asset_class": AssetClass.CRYPTO,
                "quantity": 2.5,
                "entry_price": 2640.00,
                "stop_loss": 2540.00,
                "take_profit": 2900.00,
                "commission": 4.00,
                "entry_time": now - timedelta(hours=14),
                "status": TradeStatus.OPEN,
                "setup": "Oversold RSI Divergence",
                "rating": 4,
                "discipline_rating": 4,
                "tags": "Fibonacci Retracement",
                "session": "Asian",
                "notes": "4H bullish divergence at 0.618 Fib retracement."
            }
        ]

        for s in samples:
            self.create_trade(**s)
