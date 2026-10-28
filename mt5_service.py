"""
MetaTrader 5 (MT5) Automated Synchronization Service
Direct connection via MT5 Python IPC API to sync trades, orders, commissions, and swap fees.
"""

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

            # Filter out non-trade balance operations (position_id == 0)
            trade_deals = [d for d in deals if d.position_id and d.position_id > 0 and d.symbol]

            # Group deals by position_id
            positions_map: Dict[int, List[Any]] = {}
            for d in trade_deals:
                pid = d.position_id
                if pid not in positions_map:
                    positions_map[pid] = []
                positions_map[pid].append(d)

            imported_count = 0
            updated_count = 0
            skipped_count = 0
            total_synced_pnl = 0.0

            for pos_id, p_deals in positions_map.items():
                # Sort deals chronologically
                p_deals.sort(key=lambda x: x.time)

                # Find entry deal (entry == 0 or DEAL_ENTRY_IN)
                entry_deal = next((d for d in p_deals if getattr(d, 'entry', 0) == 0), p_deals[0])
                exit_deal = next((d for d in p_deals if getattr(d, 'entry', 0) == 1), None)

                symbol = entry_deal.symbol
                asset_class = self.classify_asset_class(symbol)
                direction = TradeType.BUY if entry_deal.type == 0 else TradeType.SHORT
                quantity = entry_deal.volume
                entry_price = entry_deal.price
                entry_time = datetime.fromtimestamp(entry_deal.time)

                # Total commissions, swap, and net profit across deals for this position
                total_comm = abs(sum(d.commission for d in p_deals))
                total_swap = sum(d.swap for d in p_deals)
                total_profit = sum(d.profit for d in p_deals)

                # Check for Stop Loss & Take Profit from original orders
                stop_loss = None
                take_profit = None
                try:
                    orders = mt5.history_orders_get(position=pos_id)
                    if orders and len(orders) > 0:
                        first_order = orders[0]
                        if first_order.sl and first_order.sl > 0:
                            stop_loss = first_order.sl
                        if first_order.tp and first_order.tp > 0:
                            take_profit = first_order.tp
                except Exception:
                    pass

                trade_id = f"MT5-{pos_id}"
                existing_trade = trade_service.get_trade(trade_id)

                if exit_deal:
                    exit_price = exit_deal.price
                    exit_time = datetime.fromtimestamp(exit_deal.time)
                    status = TradeStatus.CLOSED
                else:
                    exit_price = None
                    exit_time = None
                    status = TradeStatus.OPEN

                if existing_trade:
                    # If trade transitioned from OPEN to CLOSED or needs updating
                    if existing_trade.status == TradeStatus.OPEN and status == TradeStatus.CLOSED:
                        existing_trade.exit_price = exit_price
                        existing_trade.exit_time = exit_time
                        existing_trade.status = TradeStatus.CLOSED
                        existing_trade.commission = total_comm
                        existing_trade.swap = total_swap
                        trade_service.update_trade(existing_trade)
                        updated_count += 1
                        total_synced_pnl += (existing_trade.net_pnl or 0.0)
                    else:
                        skipped_count += 1
                else:
                    # Create new synchronized trade
                    new_trade = Trade(
                        id=trade_id,
                        symbol=symbol,
                        trade_type=direction,
                        asset_class=asset_class,
                        quantity=quantity,
                        entry_price=entry_price,
                        exit_price=exit_price,
                        stop_loss=stop_loss,
                        take_profit=take_profit,
                        commission=total_comm,
                        swap=total_swap,
                        entry_time=entry_time,
                        exit_time=exit_time,
                        status=status,
                        setup="MT5 Automated Execution",
                        rating=4,
                        discipline_rating=5,
                        session="London" if 7 <= entry_time.hour <= 15 else ("NY" if 13 <= entry_time.hour <= 21 else "Asian"),
                        position_id=str(pos_id),
                        notes=f"Auto-imported from MetaTrader 5 terminal. Position #{pos_id}"
                    )
                    trade_service.create_trade(
                        id=new_trade.id,
                        symbol=new_trade.symbol,
                        trade_type=new_trade.trade_type,
                        asset_class=new_trade.asset_class,
                        quantity=new_trade.quantity,
                        entry_price=new_trade.entry_price,
                        exit_price=new_trade.exit_price,
                        stop_loss=new_trade.stop_loss,
                        take_profit=new_trade.take_profit,
                        commission=new_trade.commission,
                        swap=new_trade.swap,
                        entry_time=new_trade.entry_time,
                        exit_time=new_trade.exit_time,
                        status=new_trade.status,
                        setup=new_trade.setup,
                        rating=new_trade.rating,
                        discipline_rating=new_trade.discipline_rating,
                        session=new_trade.session,
                        position_id=new_trade.position_id,
                        notes=new_trade.notes
                    )
                    imported_count += 1
                    total_synced_pnl += (new_trade.net_pnl or 0.0)

            mt5.shutdown()
            return {
                "success": True,
                "imported": imported_count,
                "updated": updated_count,
                "skipped": skipped_count,
                "total_positions": len(positions_map),
                "total_deals_scanned": len(deals),
                "total_pnl": round(total_synced_pnl, 2),
                "message": f"Sync complete! {imported_count} new trades imported, {updated_count} updated, {skipped_count} already up-to-date."
            }

        except Exception as e:
            try:
                mt5.shutdown()
            except Exception:
                pass
            raise e
