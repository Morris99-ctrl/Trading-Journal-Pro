"""
Trading Journal Data Models
Professional-grade domain models for trade tracking, risk management, and psychology attribution.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum


class TradeType(Enum):
    BUY = "BUY"       # Long entry
    LONG = "LONG"     # Long alias
    SHORT = "SHORT"   # Short entry
    SELL = "SELL"     # Short entry / Sell alias
    COVER = "COVER"   # Cover alias


class TradeStatus(Enum):
    OPEN = "OPEN"
    CLOSED = "CLOSED"
    CANCELLED = "CANCELLED"


class AssetClass(Enum):
    STOCKS = "STOCKS"
    FOREX = "FOREX"
    CRYPTO = "CRYPTO"
    FUTURES = "FUTURES"
    OPTIONS = "OPTIONS"
    COMMODITIES = "COMMODITIES"
    INDICES = "INDICES"


@dataclass
class Trade:
    """Professional Trade entity with full risk, MT5 sync, and psychology tracking"""
    id: str
    symbol: str
    trade_type: TradeType
    quantity: float
    entry_price: float
    asset_class: AssetClass = AssetClass.STOCKS
    exit_price: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    commission: float = 0.0
    swap: float = 0.0
    entry_time: Optional[datetime] = None
    exit_time: Optional[datetime] = None
    status: TradeStatus = TradeStatus.OPEN
    setup: str = "Discretionary"
    rating: int = 0  # 1-5 quality rating
    discipline_rating: int = 5  # 1-5 execution discipline
    tags: str = ""  # e.g., "Followed Plan, A+ Setup, Key Level"
    screenshot_path: Optional[str] = None
    session: str = "NY"  # "London", "NY", "Asian", "Overlap"
    position_id: Optional[str] = None  # MT5 Ticket / Broker ID
    notes: str = ""

    def __post_init__(self):
        if self.entry_time is None:
            self.entry_time = datetime.now()
        if isinstance(self.trade_type, str):
            self.trade_type = TradeType(self.trade_type.upper())
        if isinstance(self.status, str):
            self.status = TradeStatus(self.status.upper())
        if isinstance(self.asset_class, str):
            self.asset_class = AssetClass(self.asset_class.upper())

    @property
    def is_open(self) -> bool:
        return self.status == TradeStatus.OPEN

    @property
    def is_closed(self) -> bool:
        return self.status == TradeStatus.CLOSED

    @property
    def is_long(self) -> bool:
        """True if the trade is a LONG position (BUY / LONG)"""
        return self.trade_type in (TradeType.BUY, TradeType.LONG)

    @property
    def is_short(self) -> bool:
        """True if the trade is a SHORT position (SHORT / SELL / COVER)"""
        return self.trade_type in (TradeType.SHORT, TradeType.SELL, TradeType.COVER)

    @property
    def direction(self) -> str:
        return "LONG" if self.is_long else "SHORT"

    @property
    def invested_capital(self) -> float:
        """Total capital invested in entry position"""
        return self.entry_price * self.quantity

    @property
    def gross_pnl(self) -> Optional[float]:
        """Realized gross P&L if closed, else None"""
        if self.status != TradeStatus.CLOSED or self.exit_price is None:
            return None
        if self.is_long:
            return (self.exit_price - self.entry_price) * self.quantity
        else:
            return (self.entry_price - self.exit_price) * self.quantity

    @property
    def net_pnl(self) -> Optional[float]:
        """Realized net P&L after commission and swap fees"""
        gross = self.gross_pnl
        if gross is None:
            return None
        return gross - self.commission + self.swap

    @property
    def return_pct(self) -> Optional[float]:
        """Percentage return on position capital"""
        net = self.net_pnl
        if net is None or self.invested_capital == 0:
            return None
        return (net / self.invested_capital) * 100.0

    @property
    def planned_risk_per_unit(self) -> Optional[float]:
        """Distance between entry price and stop loss"""
        if self.stop_loss is None:
            return None
        if self.is_long:
            return max(0.0, self.entry_price - self.stop_loss)
        else:
            return max(0.0, self.stop_loss - self.entry_price)

    @property
    def planned_reward_per_unit(self) -> Optional[float]:
        """Distance between entry price and take profit"""
        if self.take_profit is None:
            return None
        if self.is_long:
            return max(0.0, self.take_profit - self.entry_price)
        else:
            return max(0.0, self.entry_price - self.take_profit)

    @property
    def planned_total_risk(self) -> Optional[float]:
        """Total dollar amount at risk based on stop loss"""
        r_unit = self.planned_risk_per_unit
        if r_unit is None:
            return None
        return r_unit * self.quantity + self.commission

    @property
    def planned_risk_reward(self) -> Optional[float]:
        """Planned Risk to Reward ratio (Reward / Risk)"""
        r = self.planned_risk_per_unit
        target = self.planned_reward_per_unit
        if r and target and r > 0:
            return target / r
        return None

    @property
    def r_multiple(self) -> Optional[float]:
        """Realized return in R multiples (profit / initial risk)"""
        net = self.net_pnl
        risk = self.planned_total_risk
        if net is not None and risk and risk > 0:
            return net / risk
        return None

    def close_trade(self, exit_price: float, exit_time: Optional[datetime] = None,
                    commission: Optional[float] = None, swap: Optional[float] = None,
                    notes: Optional[str] = None) -> float:
        """Close the trade with exit price and return net P&L"""
        if self.status != TradeStatus.OPEN:
            raise ValueError(f"Cannot close trade {self.id}: trade status is already {self.status.value}")
        
        self.exit_price = exit_price
        self.exit_time = exit_time or datetime.now()
        self.status = TradeStatus.CLOSED
        if commission is not None:
            self.commission += commission
        if swap is not None:
            self.swap += swap
        if notes:
            self.notes = f"{self.notes} | {notes}".strip(" |")
        
        return self.net_pnl or 0.0

    def calculate_unrealized_pnl(self, current_price: float) -> float:
        """Calculate unrealized net P&L for open position"""
        if self.status != TradeStatus.OPEN:
            return 0.0
        if self.is_long:
            gross = (current_price - self.entry_price) * self.quantity
        else:
            gross = (self.entry_price - current_price) * self.quantity
        return gross - self.commission + self.swap

    def to_dict(self) -> Dict[str, Any]:
        """Serialize trade to dictionary for JSON APIs and CSV Export"""
        return {
            "id": self.id,
            "symbol": self.symbol,
            "trade_type": self.trade_type.value,
            "asset_class": self.asset_class.value,
            "quantity": self.quantity,
            "entry_price": self.entry_price,
            "exit_price": self.exit_price,
            "stop_loss": self.stop_loss,
            "take_profit": self.take_profit,
            "commission": self.commission,
            "swap": self.swap,
            "entry_time": self.entry_time.isoformat() if self.entry_time else None,
            "exit_time": self.exit_time.isoformat() if self.exit_time else None,
            "status": self.status.value,
            "setup": self.setup,
            "rating": self.rating,
            "discipline_rating": self.discipline_rating,
            "tags": self.tags,
            "screenshot_path": self.screenshot_path,
            "session": self.session,
            "position_id": self.position_id,
            "notes": self.notes,
            "net_pnl": round(self.net_pnl, 2) if self.net_pnl is not None else None,
            "gross_pnl": round(self.gross_pnl, 2) if self.gross_pnl is not None else None,
            "return_pct": round(self.return_pct, 2) if self.return_pct is not None else None,
            "r_multiple": round(self.r_multiple, 2) if self.r_multiple is not None else None
        }
