"""Portfolio-level analytics from actual account-equity snapshots and external cash flows.

Returns use Modified Dietz for each snapshot interval. This is a cash-flow-adjusted
approximation, not exact subperiod time-weighted return unless valuations bracket
each external flow. Risk ratios are unannualized and only reported when intervals
have a consistent cadence.
"""

import math
import statistics
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

from calculators import TradingCalculator


def _timestamp(value: Any) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, str):
        parsed = datetime.fromisoformat(value)
    else:
        raise ValueError("timestamp must be a datetime or ISO-8601 string")
    # Naive timestamps are interpreted as UTC, consistently. Prefer timezone-aware
    # timestamps at ingestion to avoid silently mixing server-local time zones.
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _finite_number(value: Any, field: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"{field} must be a finite number")
    if not math.isfinite(number):
        raise ValueError(f"{field} must be a finite number")
    return number


def calculate_portfolio_performance(
    snapshots: Iterable[Dict[str, Any]],
    cash_flows: Iterable[Dict[str, Any]] = (),
) -> Dict[str, Any]:
    """Calculate cash-flow-adjusted returns and flow-neutral drawdown.

    Snapshot fields: captured_at (ISO string or datetime), equity (account currency).
    Cash-flow fields: occurred_at, amount (positive magnitude), type ('deposit' or
    'withdrawal'). Flows exactly at the starting snapshot are already reflected in
    starting equity and are excluded; flows in (start, end] belong to that interval.
    """
    normalized_snapshots = []
    for item in snapshots:
        captured_at = _timestamp(item.get("captured_at"))
        equity = _finite_number(item.get("equity"), "equity")
        if equity < 0:
            raise ValueError("equity cannot be negative")
        normalized_snapshots.append({
            "captured_at": captured_at,
            "equity": equity,
            "balance": _finite_number(item.get("balance", equity), "balance"),
            "currency": str(item.get("currency") or ""),
            "source": str(item.get("source") or ""),
            "account_id": str(item.get("account_id") or "default"),
        })

    normalized_snapshots.sort(key=lambda x: x["captured_at"])
    for previous, current in zip(normalized_snapshots, normalized_snapshots[1:]):
        if current["captured_at"] == previous["captured_at"]:
            raise ValueError("duplicate snapshot timestamps are not allowed")
        if current["account_id"] != previous["account_id"]:
            raise ValueError("snapshots from different accounts cannot share one series")
        if previous["currency"] and current["currency"] and previous["currency"] != current["currency"]:
            raise ValueError("account currency must remain consistent within a series")

    normalized_flows = []
    for item in cash_flows:
        flow_type = str(item.get("type", "")).strip().lower()
        if flow_type not in ("deposit", "withdrawal"):
            raise ValueError("cash flow type must be 'deposit' or 'withdrawal'")
        amount = _finite_number(item.get("amount"), "cash flow amount")
        if amount <= 0:
            raise ValueError("cash flow amount must be greater than zero")
        normalized_flows.append({
            "occurred_at": _timestamp(item.get("occurred_at")),
            "amount": amount if flow_type == "deposit" else -amount,
            "type": flow_type,
        })
    normalized_flows.sort(key=lambda x: x["occurred_at"])

    if len(normalized_snapshots) < 2:
        return {
            "status": "insufficient_data",
            "message": "At least two account-equity snapshots are required.",
            "snapshot_count": len(normalized_snapshots),
            "period_count": 0,
            "periods": [],
            "total_return_pct": None,
            "max_drawdown_pct": None,
            "sharpe_ratio": None,
            "sortino_ratio": None,
            "risk_metrics_status": "unavailable: insufficient snapshots",
        }

    periods = []
    equity_index = 1.0
    peak_index = 1.0
    max_drawdown_pct = 0.0
    returns = []
    durations_days = []

    for start, end in zip(normalized_snapshots, normalized_snapshots[1:]):
        start_time, end_time = start["captured_at"], end["captured_at"]
        elapsed_seconds = (end_time - start_time).total_seconds()
        if elapsed_seconds <= 0:
            raise ValueError("snapshot timestamps must be strictly increasing")
        interval_flows = [
            flow for flow in normalized_flows
            if start_time < flow["occurred_at"] <= end_time
        ]
        net_flow = sum(flow["amount"] for flow in interval_flows)
        weighted_flows = sum(
            flow["amount"] * (
                (end_time - flow["occurred_at"]).total_seconds() / elapsed_seconds
            )
            for flow in interval_flows
        )
        denominator = start["equity"] + weighted_flows
        numerator = end["equity"] - start["equity"] - net_flow

        if denominator <= 0:
            periods.append({
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "start_equity": start["equity"],
                "end_equity": end["equity"],
                "external_net_flow": round(net_flow, 8),
                "return_pct": None,
                "status": "unavailable: non-positive Modified Dietz denominator",
            })
            durations_days.append(elapsed_seconds / 86400.0)
            continue

        period_return = numerator / denominator
        if not math.isfinite(period_return) or period_return <= -1.0:
            periods.append({
                "start": start_time.isoformat(),
                "end": end_time.isoformat(),
                "start_equity": start["equity"],
                "end_equity": end["equity"],
                "external_net_flow": round(net_flow, 8),
                "return_pct": None,
                "status": "unavailable: invalid return",
            })
            durations_days.append(elapsed_seconds / 86400.0)
            continue

        equity_index *= (1.0 + period_return)
        peak_index = max(peak_index, equity_index)
        drawdown_pct = (peak_index - equity_index) / peak_index * 100.0
        max_drawdown_pct = max(max_drawdown_pct, drawdown_pct)
        returns.append(period_return)
        durations_days.append(elapsed_seconds / 86400.0)
        periods.append({
            "start": start_time.isoformat(),
            "end": end_time.isoformat(),
            "duration_days": round(elapsed_seconds / 86400.0, 6),
            "start_equity": round(start["equity"], 2),
            "end_equity": round(end["equity"], 2),
            "external_net_flow": round(net_flow, 8),
            "return_pct": round(period_return * 100.0, 8),
            "equity_index": round(equity_index, 10),
            "drawdown_pct": round(drawdown_pct, 8),
            "status": "ok",
        })

    valid_periods = [p for p in periods if p["return_pct"] is not None]
    total_return_pct = (equity_index - 1.0) * 100.0
    cadence_consistent = False
    if len(durations_days) >= 2 and all(d > 0 for d in durations_days):
        median_duration = statistics.median(durations_days)
        cadence_consistent = all(
            abs(duration - median_duration) <= max(1e-6, median_duration * 0.05)
            for duration in durations_days
        )
    if len(returns) >= 2 and cadence_consistent and len(returns) == len(periods):
        sharpe = TradingCalculator.calculate_sharpe_ratio(returns)
        sortino = TradingCalculator.calculate_sortino_ratio(returns)
        sortino_result: Optional[float] = sortino
        risk_status = "unannualized per-observation ratios; consistent snapshot cadence"
    else:
        sharpe = None
        sortino_result = None
        if len(returns) < 2:
            risk_status = "unavailable: at least two valid return observations required"
        elif not cadence_consistent:
            risk_status = "unavailable: snapshot intervals have inconsistent durations"
        else:
            risk_status = "unavailable: one or more intervals has invalid return data"

    return {
        "status": "ok",
        "method": "Modified Dietz per snapshot interval",
        "snapshot_count": len(normalized_snapshots),
        "period_count": len(periods),
        "valid_period_count": len(valid_periods),
        "periods": periods,
        "total_return_pct": round(total_return_pct, 8) if all(p["return_pct"] is not None for p in periods) else None,
        "max_drawdown_pct": round(max_drawdown_pct, 8) if all(p["return_pct"] is not None for p in periods) else None,
        "sharpe_ratio": round(sharpe, 8) if sharpe is not None else None,
        "sortino_ratio": (
            round(sortino_result, 8)
            if sortino_result is not None and math.isfinite(sortino_result)
            else ("inf" if sortino_result is not None else None)
        ),
        "risk_metrics_status": risk_status,
        "cash_flow_count": len(normalized_flows),
        "external_net_flow_total": round(sum(flow["amount"] for flow in normalized_flows), 8),
    }
