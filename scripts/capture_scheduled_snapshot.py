"""Capture one broker-verified MT5 equity snapshot for OS task schedulers.

Example:
    python scripts/capture_scheduled_snapshot.py

This is a one-shot command. Schedule it with Windows Task Scheduler or cron.
It does not place, modify, or close trades.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _masked_account_id(account_id: Any) -> str:
    """Mask the login portion of login@server before printing diagnostics."""
    raw = str(account_id or "")
    login, separator, server = raw.partition("@")
    if not separator:
        return "unavailable"
    suffix = login[-4:] if len(login) > 4 else ""
    masked = ("*" * max(4, len(login) - 4)) + suffix
    return f"{masked}@{server}"


def capture_once(service=None) -> dict[str, Any]:
    """Capture one MT5 snapshot using the journal's standard database."""
    os.chdir(ROOT)
    if service is None:
        from services import TradeService
        service = TradeService(str(ROOT / "trading_journal.db"))

    result = service.capture_mt5_equity_snapshot()
    return {
        "success": bool(result.get("success")),
        "snapshot_id": result.get("snapshot_id"),
        "account_id": _masked_account_id(result.get("account_id")),
        "captured_at": result.get("captured_at"),
        "currency": result.get("currency"),
        "source": result.get("source"),
        "orders_placed": False,
        "orders_modified": False,
        "orders_closed": False,
    }


def main() -> int:
    try:
        report = capture_once()
    except Exception as exc:
        print(json.dumps({"success": False, "error": str(exc)}, indent=2))
        return 1
    print(json.dumps(report, indent=2, default=str))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
