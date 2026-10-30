"""Read-only MetaTrader 5 diagnostics for Priority 4 live-terminal validation.

Run from the repository root:
    python scripts/mt5_readonly_diagnostics.py --days 30

This script never places, modifies, or closes orders and never writes to the journal DB.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from mt5_service import MT5SyncService


def _value(obj: Any, name: str, default: Any = None) -> Any:
    return getattr(obj, name, default) if obj is not None else default


def _masked_login(login: Any) -> str:
    raw = str(login or "")
    if len(raw) <= 4:
        return "****" if raw else "unavailable"
    return "*" * (len(raw) - 4) + raw[-4:]


def build_report(account: Any, terminal: Any, positions: Any, deals: Any) -> dict[str, Any]:
    """Build a sanitized, JSON-safe summary from MT5 objects."""
    position_rows = list(positions or [])
    deal_rows = list(deals or [])
    grouped: dict[int, list[Any]] = {}
    for deal in deal_rows:
        position_id = _value(deal, "position_id", 0)
        if position_id:
            grouped.setdefault(int(position_id), []).append(deal)

    supported = 0
    unsupported = 0
    open_from_history = 0
    closed_from_history = 0
    symbols: Counter[str] = Counter()
    for position_deals in grouped.values():
        aggregate = MT5SyncService.aggregate_position_deals(position_deals)
        if aggregate is None:
            unsupported += 1
            continue
        supported += 1
        symbols[str(aggregate["symbol"])] += 1
        if str(aggregate["status"]).lower().endswith("open"):
            open_from_history += 1
        else:
            closed_from_history += 1

    return {
        "diagnostic": "MT5 read-only terminal check",
        "generated_at": datetime.now().astimezone().isoformat(),
        "account": {
            "login_masked": _masked_login(_value(account, "login")),
            "server": _value(account, "server", ""),
            "company": _value(account, "company", ""),
            "currency": _value(account, "currency", ""),
            "trade_allowed": bool(_value(account, "trade_allowed", False)),
            "balance_available": _value(account, "balance") is not None,
            "equity_available": _value(account, "equity") is not None,
        },
        "terminal": {
            "connected": terminal is not None,
            "name": _value(terminal, "name", ""),
            "build": _value(terminal, "build", None),
            "path_included": False,
        },
        "positions": {
            "query_succeeded": positions is not None,
            "open_position_count": len(position_rows),
            "symbols": dict(Counter(str(_value(p, "symbol", "unknown")) for p in position_rows)),
        },
        "history": {
            "query_succeeded": deals is not None,
            "deal_count": len(deal_rows),
            "position_groups": len(grouped),
            "supported_position_groups": supported,
            "unsupported_position_groups": unsupported,
            "open_lifecycles": open_from_history,
            "closed_lifecycles": closed_from_history,
            "symbols": dict(symbols),
        },
        "safety": {
            "orders_placed": False,
            "orders_modified": False,
            "orders_closed": False,
            "journal_database_written": False,
            "account_login_fully_disclosed": False,
        },
    }


def run(days: int = 30) -> dict[str, Any]:
    if days < 1 or days > 3650:
        raise ValueError("--days must be between 1 and 3650")

    try:
        import MetaTrader5 as mt5
    except ImportError as exc:
        raise RuntimeError(
            "MetaTrader5 Python package is unavailable. Run this on the Windows "
            "computer where the MT5 terminal is installed, using that Python environment."
        ) from exc

    if not mt5.initialize(timeout=10000):
        raise ConnectionError(f"MT5 initialize() failed: {mt5.last_error()}")

    try:
        account = mt5.account_info()
        terminal = mt5.terminal_info()
        if account is None:
            raise RuntimeError(f"MT5 account_info() returned no data: {mt5.last_error()}")

        positions = mt5.positions_get()
        if positions is None:
            positions_error = mt5.last_error()
            raise RuntimeError(f"MT5 positions_get() failed: {positions_error}")

        end = datetime.now()
        start = end - timedelta(days=days)
        deals = mt5.history_deals_get(start, end)
        if deals is None:
            deals_error = mt5.last_error()
            raise RuntimeError(f"MT5 history_deals_get() failed: {deals_error}")

        return build_report(account, terminal, positions, deals)
    finally:
        mt5.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser(description="Run read-only MT5 terminal diagnostics.")
    parser.add_argument("--days", type=int, default=30, help="History lookback in days (1-3650).")
    args = parser.parse_args()

    try:
        report = run(args.days)
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        return 1

    print(json.dumps({"success": True, "report": report}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
