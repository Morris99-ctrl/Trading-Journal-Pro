"""
Trading Journal Web Application
Flask backend serving high-performance REST APIs and modern web dashboard.
"""

import os
import sys
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
app.config["SECRET_KEY"] = "trading-journal-pro-secret-2026"
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
        data = request.json or {}
        symbol = data.get("symbol", "").strip().upper()
        if not symbol:
            return jsonify({"success": False, "error": "Symbol is required"}), 400

        trade = service.create_trade(
            symbol=symbol,
            trade_type=data.get("trade_type", "BUY"),
            asset_class=data.get("asset_class", "STOCKS"),
            quantity=float(data.get("quantity", 0)),
            entry_price=float(data.get("entry_price", 0)),
            stop_loss=float(data["stop_loss"]) if data.get("stop_loss") else None,
            take_profit=float(data["take_profit"]) if data.get("take_profit") else None,
            commission=float(data.get("commission", 0.0)),
            swap=float(data.get("swap", 0.0)),
            setup=data.get("setup", "Discretionary"),
            rating=int(data.get("rating", 4)),
            discipline_rating=int(data.get("discipline_rating", 5)),
            tags=data.get("tags", ""),
            session=data.get("session", "NY"),
            notes=data.get("notes", ""),
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
        data = request.json or {}
        exit_price = float(data.get("exit_price", 0))
        commission = float(data.get("commission", 0.0))
        swap = float(data.get("swap", 0.0))
        notes = data.get("notes")

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
        data = request.json or {}
        days_back = int(data.get("days", 60))
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


@app.route("/api/portfolio/manual-snapshot", methods=["POST"])
def manual_equity_snapshot():
    """Record explicitly labelled user-entered equity; never mark it broker-verified."""
    try:
        data = request.get_json(silent=True) or {}
        account_label = str(data.get("account_id", "manual-account")).strip()
        currency = str(data.get("currency", "")).strip().upper()
        if not account_label:
            return jsonify({"success": False, "error": "Account label is required"}), 400
        # Namespace manual accounts so user-entered values cannot impersonate a broker account ID.
        account_id = account_label if account_label.startswith("manual:") else f"manual:{account_label}"
        if not currency:
            return jsonify({"success": False, "error": "Currency is required"}), 400
        balance = float(data["balance"])
        equity = float(data["equity"])
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
        data = request.json or {}
        account = float(data.get("account_size", 10000))
        risk_pct = float(data.get("risk_pct", 1.0))
        entry = float(data.get("entry_price", 100))
        stop = float(data.get("stop_loss", 95))

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
        data = request.json or {}
        date_str = data.get("date") or datetime.now().strftime("%Y-%m-%d")
        service.save_daily_log(
            date_str=date_str,
            market_bias=data.get("market_bias", "Neutral"),
            news_events=data.get("news_events", ""),
            rules_checked=data.get("rules_checked", True),
            mindset_score=int(data.get("mindset_score", 5)),
            post_market_notes=data.get("post_market_notes", "")
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

    filename = secure_filename(f"{trade_id}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
    save_path = Path(app.config["UPLOAD_FOLDER"]) / filename
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

