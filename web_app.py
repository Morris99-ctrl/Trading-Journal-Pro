"""
Trading Journal Web Application
Flask backend serving high-performance REST APIs and modern web dashboard.
"""

import os
import sys
import math
import secrets
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_from_directory, send_file
from werkzeug.utils import secure_filename

# Add current directory to path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from services import TradeService
from calculators import TradingCalculator
from models import TradeType, TradeStatus, AssetClass

app = Flask(__name__, template_folder="templates", static_folder="static")
app.config["SECRET_KEY"] = os.environ.get("TRADING_JOURNAL_SECRET_KEY") or secrets.token_hex(32)
app.config["TRUSTED_HOSTS"] = ["localhost", "127.0.0.1"]
app.config["UPLOAD_FOLDER"] = str(BASE_DIR / "screenshots")
app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024  # 16 MB max image upload

# Initialize trade service
db_path = str(BASE_DIR / "trading_journal.db")
service = TradeService(db_path)

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif"}


@app.route("/manifest.json")
def manifest():
    """Serve PWA Web App Manifest"""
    return send_from_directory("static", "manifest.json")


@app.route("/favicon.ico")
def favicon():
    """Serve application favicon (ICO for broad compatibility)"""
    ico = BASE_DIR / "static" / "app_icon.ico"
    if ico.exists():
        return send_from_directory("static", "app_icon.ico", mimetype="image/x-icon")
    return send_from_directory("static", "icon.svg", mimetype="image/svg+xml")


def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def _json_object():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        raise ValueError("A JSON object is required")
    return data


def _finite_number(value, field_name: str, *, minimum=None, allow_zero=True) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(f"{field_name} must be a valid number")
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    if minimum is not None and (number < minimum or (not allow_zero and number == minimum)):
        qualifier = "greater than" if not allow_zero else "at least"
        raise ValueError(f"{field_name} must be {qualifier} {minimum}")
    return number


def _bounded_text(value, field_name: str, *, max_length: int, default="") -> str:
    if value is None:
        value = default
    if not isinstance(value, str):
        raise ValueError(f"{field_name} must be text")
    value = value.strip()
    if len(value) > max_length:
        raise ValueError(f"{field_name} must be {max_length} characters or fewer")
    return value


@app.after_request
def add_security_headers(response):
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
    if request.path.startswith("/api/"):
        response.headers["Cache-Control"] = "no-store"
    return response


@app.route("/")
def index():
    """Render main web dashboard"""
    return render_template("index.html")


# ==========================================
# REST API ENDPOINTS
# ==========================================

@app.route("/api/stats", methods=["GET"])
def get_stats():
    """Get complete quantitative performance summary"""
    try:
        summary = service.get_performance_summary()
        # Group performance by setup
        trades = service.get_closed_trades()
        setup_map = {}
        for t in trades:
            s = t.setup or "Discretionary"
            if s not in setup_map:
                setup_map[s] = {"pnl": 0.0, "count": 0, "wins": 0}
            setup_map[s]["pnl"] += (t.net_pnl or 0.0)
            setup_map[s]["count"] += 1
            if (t.net_pnl or 0) > 0:
                setup_map[s]["wins"] += 1

        setup_data = [
            {"setup": k, "pnl": round(v["pnl"], 2), "count": v["count"], "win_rate": round(v["wins"] / v["count"] * 100, 1)}
            for k, v in setup_map.items()
        ]
        setup_data.sort(key=lambda x: x["pnl"], reverse=True)

        # Daily P&L breakdown
        daily_map = {}
        for t in trades:
            dt = t.exit_time or t.entry_time
            if dt:
                day_str = dt.strftime("%Y-%m-%d")
                daily_map[day_str] = daily_map.get(day_str, 0.0) + (t.net_pnl or 0.0)

        daily_data = [
            {"date": d, "pnl": round(daily_map[d], 2)}
            for d in sorted(daily_map.keys())
        ]

        summary["setup_breakdown"] = setup_data
        summary["daily_pnl"] = daily_data
        return jsonify({"success": True, "data": summary})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/trades", methods=["GET"])
def get_trades():
    """Get list of trades with filtering"""
    try:
        status_param = request.args.get("status")
        symbol_param = request.args.get("symbol")
        status_enum = None
        if status_param and status_param.upper() != "ALL":
            status_enum = TradeStatus(status_param.upper())

        trades = service.get_all_trades(status=status_enum, symbol=symbol_param)
        return jsonify({"success": True, "data": [t.to_dict() for t in trades]})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/trades", methods=["POST"])
def create_trade():
    """Create a new trade record"""
    try:
        data = _json_object()
        symbol = _bounded_text(data.get("symbol"), "Symbol", max_length=32).upper()
        if not symbol:
            raise ValueError("Symbol is required")
        trade_type = _bounded_text(data.get("trade_type", "BUY"), "Trade type", max_length=16).upper()
        asset_class = _bounded_text(data.get("asset_class", "STOCKS"), "Asset class", max_length=20).upper()
        if trade_type not in TradeType.__members__:
            raise ValueError("Unsupported trade type")
        if asset_class not in AssetClass.__members__:
            raise ValueError("Unsupported asset class")
        rating = int(_finite_number(data.get("rating", 4), "Rating", minimum=1))
        discipline_rating = int(_finite_number(data.get("discipline_rating", 5), "Discipline rating", minimum=1))
        if rating > 5 or discipline_rating > 5:
            raise ValueError("Ratings must be between 1 and 5")
        trade = service.create_trade(
            symbol=symbol, trade_type=trade_type, asset_class=asset_class,
            quantity=_finite_number(data.get("quantity"), "Quantity", minimum=0, allow_zero=False),
            entry_price=_finite_number(data.get("entry_price"), "Entry price", minimum=0, allow_zero=False),
            stop_loss=_finite_number(data["stop_loss"], "Stop loss", minimum=0, allow_zero=False) if data.get("stop_loss") not in (None, "") else None,
            take_profit=_finite_number(data["take_profit"], "Take profit", minimum=0, allow_zero=False) if data.get("take_profit") not in (None, "") else None,
            commission=_finite_number(data.get("commission", 0), "Commission", minimum=0),
            swap=_finite_number(data.get("swap", 0), "Swap"),
            setup=_bounded_text(data.get("setup", "Discretionary"), "Setup", max_length=80),
            rating=rating, discipline_rating=discipline_rating,
            tags=_bounded_text(data.get("tags", ""), "Tags", max_length=500),
            session=_bounded_text(data.get("session", "NY"), "Session", max_length=32),
            notes=_bounded_text(data.get("notes", ""), "Notes", max_length=5000),
            status=TradeStatus.OPEN
        )
        return jsonify({"success": True, "data": trade.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/trades/<trade_id>", methods=["GET"])
def get_single_trade(trade_id):
    """Fetch single trade by ID"""
    trade = service.get_trade(trade_id)
    if not trade:
        return jsonify({"success": False, "error": "Trade not found"}), 404
    return jsonify({"success": True, "data": trade.to_dict()})


@app.route("/api/trades/<trade_id>/close", methods=["POST"])
def close_trade(trade_id):
    """Close an open trade"""
    try:
        data = _json_object()
        exit_price = _finite_number(data.get("exit_price"), "Exit price", minimum=0, allow_zero=False)
        commission = _finite_number(data.get("commission", 0.0), "Commission", minimum=0)
        swap = _finite_number(data.get("swap", 0.0), "Swap")
        notes = _bounded_text(data.get("notes"), "Notes", max_length=5000) or None

        closed = service.close_trade(
            trade_id=trade_id,
            exit_price=exit_price,
            commission=commission,
            swap=swap,
            notes=notes
        )
        if not closed:
            return jsonify({"success": False, "error": "Trade not found or already closed"}), 400

        return jsonify({"success": True, "data": closed.to_dict()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/trades/<trade_id>", methods=["DELETE"])
def delete_trade(trade_id):
    """Delete a trade by ID"""
    success = service.delete_trade(trade_id)
    if success:
        return jsonify({"success": True, "message": f"Trade {trade_id} deleted"})
    return jsonify({"success": False, "error": "Trade not found"}), 404


@app.route("/api/mt5/status", methods=["GET"])
def mt5_status():
    """Check MetaTrader 5 terminal connection status"""
    status = service.get_mt5_status()
    return jsonify(status)


@app.route("/api/mt5/sync", methods=["POST"])
def mt5_sync():
    """Trigger automated trade synchronization from MT5"""
    try:
        data = _json_object()
        days_back = int(_finite_number(data.get("days", 60), "Days", minimum=1))
        if days_back > 3650:
            raise ValueError("Days must not exceed 3650")
        result = service.sync_mt5(days_back=days_back)
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/mt5/snapshot", methods=["POST"])
def mt5_equity_snapshot():
    """Capture the current broker-reported MT5 account balance and equity."""
    try:
        result = service.capture_mt5_equity_snapshot()
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 503


@app.route("/api/portfolio/accounts", methods=["GET"])
def portfolio_accounts():
    """List account IDs with stored equity snapshots."""
    try:
        return jsonify({"success": True, "data": service.get_portfolio_accounts()})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/api/portfolio/performance", methods=["GET"])
def portfolio_performance():
    """Return account equity history and cash-flow-adjusted performance."""
    try:
        account_id = request.args.get("account_id")
        if not account_id:
            accounts = service.get_portfolio_accounts()
            account_id = accounts[0]["account_id"] if accounts else "default"
        result = service.get_portfolio_performance(account_id=account_id)
        return jsonify({"success": True, "data": result})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/portfolio/cash-flow", methods=["POST"])
def portfolio_cash_flow():
    """Record a deposit or withdrawal for an existing portfolio account."""
    try:
        data = _json_object()
        account_id = _bounded_text(data.get("account_id"), "Account", max_length=128)
        flow_type = _bounded_text(data.get("flow_type"), "Flow type", max_length=16).lower()
        currency = _bounded_text(data.get("currency"), "Currency", max_length=8).upper()
        notes = _bounded_text(data.get("notes"), "Notes", max_length=500)
        if not account_id:
            return jsonify({"success": False, "error": "Account is required"}), 400
        if flow_type not in ("deposit", "withdrawal"):
            return jsonify({"success": False, "error": "Flow type must be deposit or withdrawal"}), 400
        if not currency:
            return jsonify({"success": False, "error": "Currency is required"}), 400
        if len(notes) > 500:
            return jsonify({"success": False, "error": "Notes must be 500 characters or fewer"}), 400

        accounts = service.get_portfolio_accounts()
        account = next((item for item in accounts if item.get("account_id") == account_id), None)
        if account is None:
            return jsonify({"success": False, "error": "Select an existing portfolio account"}), 400
        account_currency = str(account.get("currency") or "").strip().upper()
        if account_currency and currency != account_currency:
            return jsonify({"success": False, "error": f"Currency must match the account currency ({account_currency})"}), 400

        amount = _finite_number(data.get("amount"), "Amount", minimum=0, allow_zero=False)

        occurred_raw = data.get("occurred_at")
        if occurred_raw:
            occurred_at = datetime.fromisoformat(str(occurred_raw))
            if occurred_at.tzinfo is None:
                occurred_at = occurred_at.astimezone()
        else:
            occurred_at = datetime.now().astimezone()

        flow_id = service.record_portfolio_cash_flow(
            occurred_at=occurred_at, flow_type=flow_type, amount=amount,
            account_id=account_id, currency=currency, notes=notes,
        )
        return jsonify({
            "success": True, "flow_id": flow_id, "account_id": account_id,
            "flow_type": flow_type, "amount": amount, "currency": currency,
            "occurred_at": occurred_at.isoformat(), "notes": notes,
        })
    except (TypeError, ValueError, OverflowError) as e:
        return jsonify({"success": False, "error": str(e) or "Invalid cash-flow details"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/portfolio/manual-snapshot", methods=["POST"])
def manual_equity_snapshot():
    """Record explicitly labelled user-entered equity; never mark it broker-verified."""
    try:
        data = _json_object()
        account_label = _bounded_text(data.get("account_id", "manual-account"), "Account label", max_length=100)
        currency = _bounded_text(data.get("currency"), "Currency", max_length=8).upper()
        if not account_label:
            return jsonify({"success": False, "error": "Account label is required"}), 400
        # Namespace manual accounts so user-entered values cannot impersonate a broker account ID.
        account_id = account_label if account_label.startswith("manual:") else f"manual:{account_label}"
        if not currency:
            return jsonify({"success": False, "error": "Currency is required"}), 400
        balance = _finite_number(data.get("balance"), "Balance", minimum=0)
        equity = _finite_number(data.get("equity"), "Equity", minimum=0)
        captured_at = datetime.now().astimezone()
        snapshot_id = service.record_equity_snapshot(
            captured_at=captured_at, balance=balance, equity=equity,
            account_id=account_id, currency=currency, source="manual",
            notes="Manually entered; not broker verified.",
        )
        return jsonify({
            "success": True, "snapshot_id": snapshot_id, "account_id": account_id,
            "captured_at": captured_at.isoformat(), "balance": balance,
            "equity": equity, "currency": currency, "source": "manual",
        })
    except (KeyError, TypeError, ValueError) as e:
        return jsonify({"success": False, "error": str(e) or "Balance and equity must be valid numbers"}), 400
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/calc/position-size", methods=["POST"])
def calc_position():
    """Calculate position sizing based on risk percentage"""
    try:
        data = _json_object()
        account = _finite_number(data.get("account_size", 10000), "Account size", minimum=0, allow_zero=False)
        risk_pct = _finite_number(data.get("risk_pct", 1.0), "Risk percentage", minimum=0, allow_zero=False)
        if risk_pct > 100:
            raise ValueError("Risk percentage must not exceed 100")
        entry = _finite_number(data.get("entry_price", 100), "Entry price", minimum=0, allow_zero=False)
        stop = _finite_number(data.get("stop_loss", 95), "Stop loss", minimum=0, allow_zero=False)

        res = TradingCalculator.calculate_position_size(
            account_size=account,
            risk_percentage=risk_pct,
            entry_price=entry,
            stop_loss=stop
        )
        return jsonify({"success": True, "data": res})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/daily-logs", methods=["GET", "POST"])
def daily_logs():
    """Get or save daily pre/post market logs"""
    if request.method == "GET":
        date_param = request.args.get("date")
        if date_param:
            log = service.get_daily_log(date_param)
            return jsonify({"success": True, "data": log})
        logs = service.get_all_daily_logs()
        return jsonify({"success": True, "data": logs})

    try:
        data = _json_object()
        date_str = _bounded_text(data.get("date") or datetime.now().strftime("%Y-%m-%d"), "Date", max_length=10)
        datetime.strptime(date_str, "%Y-%m-%d")
        mindset_score = int(_finite_number(data.get("mindset_score", 5), "Mindset score", minimum=1))
        if mindset_score > 5:
            raise ValueError("Mindset score must be between 1 and 5")
        rules_checked = data.get("rules_checked", True)
        if not isinstance(rules_checked, bool):
            raise ValueError("Rules checked must be true or false")
        service.save_daily_log(
            date_str=date_str,
            market_bias=_bounded_text(data.get("market_bias", "Neutral"), "Market bias", max_length=40),
            news_events=_bounded_text(data.get("news_events", ""), "News events", max_length=5000),
            rules_checked=rules_checked,
            mindset_score=mindset_score,
            post_market_notes=_bounded_text(data.get("post_market_notes", ""), "Post-market notes", max_length=5000)
        )
        return jsonify({"success": True, "message": "Daily log saved"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400


@app.route("/api/trades/<trade_id>/upload-screenshot", methods=["POST"])
def upload_screenshot(trade_id):
    """Upload chart screenshot for a trade"""
    if "image" not in request.files:
        return jsonify({"success": False, "error": "No file uploaded"}), 400
    file = request.files["image"]
    if file.filename == "" or not allowed_file(file.filename):
        return jsonify({"success": False, "error": "Invalid image file"}), 400
    extension = file.filename.rsplit(".", 1)[1].lower()
    header = file.stream.read(16)
    file.stream.seek(0)
    signatures = {
        "png": header.startswith(b"\x89PNG\r\n\x1a\n"),
        "jpg": header.startswith(b"\xff\xd8\xff"),
        "jpeg": header.startswith(b"\\xff\\xd8\\xff"),
        "gif": header.startswith((b"GIF87a", b"GIF89a")),
        "webp": len(header) >= 12 and header[:4] == b"RIFF" and header[8:12] == b"WEBP",
    }
    if not signatures.get(extension, False):
        return jsonify({"success": False, "error": "File content does not match an allowed image type"}), 400
    if not service.get_trade(trade_id):
        return jsonify({"success": False, "error": "Trade not found"}), 404

    filename = secure_filename(f"{trade_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
    upload_dir = Path(app.config["UPLOAD_FOLDER"]).resolve()
    upload_dir.mkdir(parents=True, exist_ok=True)
    save_path = (upload_dir / filename).resolve()
    if upload_dir not in save_path.parents:
        return jsonify({"success": False, "error": "Invalid upload path"}), 400
    file.save(str(save_path))

    service.attach_screenshot(trade_id, filename)
    return jsonify({"success": True, "filename": filename})


@app.route("/screenshots/<filename>")
def get_screenshot(filename):
    """Serve uploaded trade screenshots"""
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/api/export-csv", methods=["GET"])
def export_csv():
    """Download database trades as CSV"""
    out_file = str(BASE_DIR / "trades_export.csv")
    service.export_csv(out_file)
    return send_file(out_file, as_attachment=True, download_name="trading_journal_export.csv")


@app.route("/api/backups", methods=["GET", "POST"])
def manage_backups():
    """List backups or trigger an immediate database backup"""
    if request.method == "POST":
        res = service.create_backup()
        if res:
            return jsonify({"success": True, "message": f"Backup created successfully: {Path(res).name}"})
        return jsonify({"success": False, "error": "Backup failed"}), 500
    
    backups = service.list_backups()
    return jsonify({"success": True, "data": backups})


@app.route("/api/seed-samples", methods=["POST"])
def seed_samples():
    """Seed realistic sample dataset"""
    service.seed_sample_data(clear_first=False)
    return jsonify({"success": True, "message": "Sample trades seeded successfully"})


if __name__ == "__main__":
    print("=" * 65)
    print("★ TRADING JOURNAL PRO - MODERN WEB DASHBOARD ★")
    print("Server running at: http://127.0.0.1:5000")
    print("Press Ctrl+C to terminate the web server.")
    print("=" * 65)
    app.run(host="127.0.0.1", port=5000, debug=False)

