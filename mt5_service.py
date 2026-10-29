"""
MetaTrader 5 (MT5) Automated Synchronization Service
Direct connection via MT5 Python IPC API to sync trades, orders, commissions, and swap fees.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, TYPE_CHECKING
from models import Trade, TradeType, TradeStatus, AssetClass

if TYPE_CHECKING:
    from services import TradeService


class MT5SyncService:
    """Institutional MetaTrader 5 trade sync engine"""

    def __init__(self):
        self._mt5 = None
        try:
            import MetaTrader5 as mt5
            self._mt5 = mt5
        except ImportError:
            self._mt5 = None

    def is_available(self) -> bool:
        """Check if MT5 Python library is installed"""
        return self._mt5 is not None

    def get_terminal_status(self) -> Dict[str, Any]:
        """Check if MetaTrader 5 terminal is currently running and reachable"""
        if not self.is_available():
            return {
                "available": False,
                "connected": False,
                "message": "MetaTrader5 Python module not installed."
            }

        mt5 = self._mt5
        try:
            if not mt5.initialize(timeout=3000):
                err = mt5.last_error()
                return {
                    "available": True,
                    "connected": False,
                    "message": f"Terminal offline or unreachable: {err}"
                }

            acc = mt5.account_info()
            term = mt5.terminal_info()

            status = {
                "available": True,
                "connected": True,
                "login": acc.login if acc else "Unknown",
                "server": acc.server if acc else "Unknown",
                "balance": acc.balance if acc else 0.0,
                "equity": acc.equity if acc else 0.0,
                "currency": acc.currency if acc else "USD",
                "company": acc.company if acc else "MetaTrader 5 Broker",
                "name": acc.name if acc else "",
                "leverage": acc.leverage if acc else 1,
                "terminal_path": term.path if term else ""
            }
            mt5.shutdown()
            return status
        except Exception as e:
            try:
                mt5.shutdown()
            except Exception:
                pass
            return {
                "available": True,
                "connected": False,
                "message": f"Connection error: {str(e)}"
            }

    @staticmethod
    def classify_asset_class(symbol: str) -> AssetClass:
        """Classify symbol into institutional asset class"""
        s = symbol.upper()
        if any(m in s for m in ["XAU", "XAG", "GOLD", "SILVER", "OIL", "WTI", "BRENT", "NATGAS"]):
            return AssetClass.COMMODITIES
        if any(idx in s for idx in ["US30", "NAS100", "SPX500", "GER40", "UK100", "DJ30", "NDX", "DAX", "WS30", "USTEC"]):
            return AssetClass.INDICES
        if any(c in s for c in ["BTC", "ETH", "SOL", "XRP", "DOGE", "USDT"]):
            return AssetClass.CRYPTO
        if any(fx in s for fx in ["EUR", "GBP", "USD", "JPY", "AUD", "NZD", "CAD", "CHF"]):
            return AssetClass.FOREX
        return AssetClass.STOCKS

    @staticmethod
    def aggregate_position_deals(deals: List[Any]) -> Optional[Dict[str, Any]]:
        """Aggregate MT5 deals for one position without assuming price × volume is P&L.

        MT5 deal profit, commission, swap, and fee are signed account-currency
        amounts. Broker net P&L is the sum of those fields across every deal.
        Reversal deals are rejected because one position ticket can then encode
        more than one exposure lifecycle and needs a dedicated split model.
        """
        if not deals:
            return None

        ordered = sorted(deals, key=lambda deal: (getattr(deal, "time_msc", 0), getattr(deal, "time", 0), getattr(deal, "ticket", 0)))
        if any(getattr(deal, "entry", None) == 2 for deal in ordered):  # DEAL_ENTRY_INOUT
            return None

        entries = [d for d in ordered if getattr(d, "entry", None) == 0]  # DEAL_ENTRY_IN
        exits = [d for d in ordered if getattr(d, "entry", None) in (1, 3)]  # OUT / OUT_BY
        if not entries:
            return None

        entry_volume = sum(float(getattr(d, "volume", 0.0) or 0.0) for d in entries)
        exit_volume = sum(float(getattr(d, "volume", 0.0) or 0.0) for d in exits)
        if entry_volume <= 0:
            return None

        weighted_entry = sum(float(d.price) * float(d.volume) for d in entries) / entry_volume
        weighted_exit = (
            sum(float(d.price) * float(d.volume) for d in exits) / exit_volume
            if exit_volume > 0 else None
        )
        closed = exit_volume >= entry_volume - max(1e-8, entry_volume * 1e-6)
        gross_pnl = sum(float(getattr(d, "profit", 0.0) or 0.0) for d in ordered)
        commission_signed = sum(float(getattr(d, "commission", 0.0) or 0.0) for d in ordered)
        swap = sum(float(getattr(d, "swap", 0.0) or 0.0) for d in ordered)
        fee = sum(float(getattr(d, "fee", 0.0) or 0.0) for d in ordered)
        net_pnl = gross_pnl + commission_signed + swap + fee

        first_entry = entries[0]
        last_exit = exits[-1] if closed and exits else None
        return {
            "symbol": first_entry.symbol,
            "direction": TradeType.BUY if first_entry.type == 0 else TradeType.SHORT,
            "entry_volume": entry_volume,
            "exit_volume": exit_volume,
            "remaining_volume": max(0.0, entry_volume - exit_volume),
            "quantity": entry_volume if closed else max(0.0, entry_volume - exit_volume),
            "entry_price": weighted_entry,
            "exit_price": weighted_exit if closed else None,
            "entry_time": datetime.fromtimestamp(first_entry.time),
            "exit_time": datetime.fromtimestamp(last_exit.time) if last_exit else None,
            "status": TradeStatus.CLOSED if closed else TradeStatus.OPEN,
            "commission": abs(commission_signed),
            "swap": swap,
            "broker_gross_pnl": gross_pnl if closed else None,
            "broker_net_pnl": net_pnl if closed else None,
            "deal_count": len(ordered),
        }

    def sync_trades(
        self,
        trade_service: TradeService,
        days_back: int = 60,
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        Extract round-trip trades from MT5 terminal history deals and synchronize with database.
        Pairs DEAL_ENTRY_IN with DEAL_ENTRY_OUT by position_id.
        """
        if not self.is_available():
            raise RuntimeError("MetaTrader5 module is not installed.")

        mt5 = self._mt5
        if not mt5.initialize(timeout=5000):
            err = mt5.last_error()
            raise ConnectionError(f"Could not connect to MetaTrader 5: {err}")

        try:
            end_dt = to_date or datetime.now()
            start_dt = from_date or (end_dt - timedelta(days=days_back))

            deals = mt5.history_deals_get(start_dt, end_dt)
            if deals is None:
                err = mt5.last_error()
                mt5.shutdown()
                return {
                    "imported": 0,
                    "updated": 0,
                    "skipped": 0,
                    "total_deals": 0,
                    "message": f"No deals returned: {err}"
                }

            # Ignore balance/credit operations that do not belong to a position.
            trade_deals = [d for d in deals if getattr(d, "position_id", 0) and d.position_id > 0 and getattr(d, "symbol", None)]

            positions_map: Dict[int, List[Any]] = {}
            for deal in trade_deals:
                positions_map.setdefault(int(deal.position_id), []).append(deal)

            imported_count = 0
            updated_count = 0
            skipped_count = 0
            unsupported_count = 0
            total_synced_pnl = 0.0

            for pos_id, position_deals in positions_map.items():
                aggregate = self.aggregate_position_deals(position_deals)
                if aggregate is None:
                    unsupported_count += 1
                    continue

                symbol = aggregate["symbol"]
                entry_time = aggregate["entry_time"]
                stop_loss = None
                take_profit = None
                try:
                    orders = mt5.history_orders_get(position=pos_id)
                    if orders:
                        first_order = sorted(orders, key=lambda order: getattr(order, "time_setup", 0))[0]
                        if getattr(first_order, "sl", 0) and first_order.sl > 0:
                            stop_loss = first_order.sl
                        if getattr(first_order, "tp", 0) and first_order.tp > 0:
                            take_profit = first_order.tp
                except Exception:
                    pass

                trade_id = f"MT5-{pos_id}"
                existing_trade = trade_service.get_trade(trade_id)
                fields = {
                    "symbol": symbol,
                    "trade_type": aggregate["direction"],
                    "asset_class": self.classify_asset_class(symbol),
                    "quantity": aggregate["quantity"],
                    "entry_price": aggregate["entry_price"],
                    "exit_price": aggregate["exit_price"],
                    "stop_loss": stop_loss,
                    "take_profit": take_profit,
                    "commission": aggregate["commission"],
                    "swap": aggregate["swap"],
                    "entry_time": aggregate["entry_time"],
                    "exit_time": aggregate["exit_time"],
                    "status": aggregate["status"],
                    "broker_gross_pnl": aggregate["broker_gross_pnl"],
                    "broker_net_pnl": aggregate["broker_net_pnl"],
                }

                if existing_trade:
                    # Reconcile MT5-managed records on every sync so newly arrived
                    # partial exits, fees, swaps, and final closes are not ignored.
                    for name, value in fields.items():
                        setattr(existing_trade, name, value)
                    if not trade_service.update_trade(existing_trade):
                        raise RuntimeError(f"Failed to persist MT5 reconciliation for position {pos_id}")
                    updated_count += 1
                    total_synced_pnl += existing_trade.net_pnl or 0.0
                    continue

                trade_service.create_trade(
                    id=trade_id,
                    **fields,
                    setup="MT5 Automated Execution",
                    rating=4,
                    discipline_rating=5,
                    session="London" if 7 <= entry_time.hour <= 15 else ("NY" if 13 <= entry_time.hour <= 21 else "Asian"),
                    position_id=str(pos_id),
                    notes=f"Auto-imported from MetaTrader 5 terminal. Position #{pos_id}; reconciled from {aggregate['deal_count']} deals."
                )
                imported_count += 1
                if aggregate["broker_net_pnl"] is not None:
                    total_synced_pnl += aggregate["broker_net_pnl"]

            mt5.shutdown()
            return {
                "success": True,
                "imported": imported_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "total_positions": len(positions_map),
                "unsupported_positions": unsupported_count,
                "total_deals_scanned": len(deals),
                "total_pnl": round(total_synced_pnl, 2),
                "message": f"Sync complete! {imported_count} new trades imported, {updated_count} reconciled, {skipped_count} skipped, {unsupported_count} unsupported reversal/malformed positions skipped."
            }

        except Exception as e:
            try:
                mt5.shutdown()
            except Exception:
                pass
            raise e
