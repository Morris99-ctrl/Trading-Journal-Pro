"""
Trading Journal Database Layer
SQLite storage with automatic migration, robust row mapping, daily journaling, auto-backup, and CSV Import/Export.
"""

import sqlite3
import csv
import os
import shutil
from typing import List, Optional, Dict, Any
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
from models import Trade, TradeType, TradeStatus, AssetClass
from calculators import TradingCalculator


class TradeDatabase:
    """Robust SQLite database manager for trade journals, backups, and daily reflections"""

    def __init__(self, db_path: str = "trading_journal.db"):
        self.db_path = str(Path(db_path).resolve())
        self.init_database()

    @contextmanager
    def _connection(self):
        """Context manager ensuring SQLite connection is always closed cleanly"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
        finally:
            conn.close()

    def init_database(self):
        """Create tables and execute migrations if needed"""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    symbol TEXT NOT NULL,
                    trade_type TEXT NOT NULL,
                    asset_class TEXT DEFAULT 'STOCKS',
                    quantity REAL NOT NULL,
                    entry_price REAL NOT NULL,
                    exit_price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    commission REAL DEFAULT 0.0,
                    swap REAL DEFAULT 0.0,
                    entry_time TEXT,
                    exit_time TEXT,
                    status TEXT NOT NULL,
                    setup TEXT DEFAULT 'Discretionary',
                    rating INTEGER DEFAULT 0,
                    discipline_rating INTEGER DEFAULT 5,
                    tags TEXT DEFAULT '',
                    screenshot_path TEXT,
                    session TEXT DEFAULT 'NY',
                    position_id TEXT,
                    notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Create daily_logs table for morning prep & evening reviews
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_logs (
                    date TEXT PRIMARY KEY,
                    market_bias TEXT,
                    news_events TEXT,
                    rules_checked INTEGER DEFAULT 1,
                    mindset_score INTEGER DEFAULT 5,
                    post_market_notes TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # Ensure columns exist in case of legacy tables
            cursor.execute("PRAGMA table_info(trades)")
            columns = {col["name"] for col in cursor.fetchall()}

            migrations = {
                "asset_class": "ALTER TABLE trades ADD COLUMN asset_class TEXT DEFAULT 'STOCKS'",
                "commission": "ALTER TABLE trades ADD COLUMN commission REAL DEFAULT 0.0",
                "swap": "ALTER TABLE trades ADD COLUMN swap REAL DEFAULT 0.0",
                "setup": "ALTER TABLE trades ADD COLUMN setup TEXT DEFAULT 'Discretionary'",
                "rating": "ALTER TABLE trades ADD COLUMN rating INTEGER DEFAULT 0",
                "discipline_rating": "ALTER TABLE trades ADD COLUMN discipline_rating INTEGER DEFAULT 5",
                "tags": "ALTER TABLE trades ADD COLUMN tags TEXT DEFAULT ''",
                "screenshot_path": "ALTER TABLE trades ADD COLUMN screenshot_path TEXT",
                "session": "ALTER TABLE trades ADD COLUMN session TEXT DEFAULT 'NY'",
                "position_id": "ALTER TABLE trades ADD COLUMN position_id TEXT"
            }

            for col_name, sql in migrations.items():
                if col_name not in columns:
                    try:
                        cursor.execute(sql)
                    except sqlite3.OperationalError:
                        pass

            conn.commit()

        # Execute daily auto-backup on startup
        self.auto_backup()

    def auto_backup(self, max_backups: int = 30) -> Optional[str]:
        """
        Create a timestamped backup in backups/ folder.
        Prunes backups older than max_backups to keep disk clean.
        """
        db_file = Path(self.db_path)
        if not db_file.exists() or db_file.stat().st_size == 0:
            return None

        backup_dir = db_file.parent / "backups"
        backup_dir.mkdir(parents=True, exist_ok=True)

        today_str = datetime.now().strftime("%Y-%m-%d")
        backup_file = backup_dir / f"trading_journal_{today_str}.db"

        try:
            shutil.copy2(str(db_file), str(backup_file))

            # Prune old backups, retaining only the latest max_backups
            all_backups = sorted(backup_dir.glob("trading_journal_*.db"), key=os.path.getmtime, reverse=True)
            for old_b in all_backups[max_backups:]:
                try:
                    old_b.unlink()
                except Exception:
                    pass

            return str(backup_file)
        except Exception as e:
            print(f"Auto-backup warning: {e}")
            return None

    def list_backups(self) -> List[Dict[str, Any]]:
        """Return list of existing backup files and metadata"""
        backup_dir = Path(self.db_path).parent / "backups"
        if not backup_dir.exists():
            return []
        backups = []
        for f in sorted(backup_dir.glob("trading_journal_*.db"), key=os.path.getmtime, reverse=True):
            backups.append({
                "filename": f.name,
                "size_kb": round(f.stat().st_size / 1024, 1),
                "modified": datetime.fromtimestamp(f.stat().st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            })
        return backups

    def add_trade(self, trade: Trade) -> bool:
        """Insert a trade into the database"""
        sql = '''
            INSERT INTO trades (
                id, symbol, trade_type, asset_class, quantity, entry_price,
                exit_price, stop_loss, take_profit, commission, swap, entry_time,
                exit_time, status, setup, rating, discipline_rating, tags,
                screenshot_path, session, position_id, notes
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        '''
        with self._connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (
                    trade.id,
                    trade.symbol.upper(),
                    trade.trade_type.value,
                    trade.asset_class.value,
                    trade.quantity,
                    trade.entry_price,
                    trade.exit_price,
                    trade.stop_loss,
                    trade.take_profit,
                    trade.commission,
                    trade.swap,
                    trade.entry_time.isoformat() if trade.entry_time else None,
                    trade.exit_time.isoformat() if trade.exit_time else None,
                    trade.status.value,
                    trade.setup,
                    trade.rating,
                    trade.discipline_rating,
                    trade.tags,
                    trade.screenshot_path,
                    trade.session,
                    trade.position_id,
                    trade.notes
                ))
                conn.commit()
                return True
            except sqlite3.Error as e:
                print(f"Error adding trade: {e}")
                return False

    def get_trade(self, trade_id: str) -> Optional[Trade]:
        """Fetch a single trade by ID"""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trades WHERE id = ?', (trade_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_trade(row)
        return None

    def get_trade_by_position_id(self, position_id: str) -> Optional[Trade]:
        """Fetch a trade by MT5 position ticket ID"""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM trades WHERE position_id = ?', (str(position_id),))
            row = cursor.fetchone()
            if row:
                return self._row_to_trade(row)
        return None

    def get_all_trades(
        self,
        status: Optional[TradeStatus] = None,
        symbol: Optional[str] = None,
        asset_class: Optional[AssetClass] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        date_basis: str = "entry"
    ) -> List[Trade]:
        """Fetch trades with optional filters.

        date_basis='entry' filters by entry_time (trade-cohort view).
        date_basis='exit' filters by exit_time (realized-performance view).
        """
        if date_basis not in ("entry", "exit"):
            raise ValueError("date_basis must be 'entry' or 'exit'")

        date_column = "entry_time" if date_basis == "entry" else "exit_time"
        query = 'SELECT * FROM trades WHERE 1=1'
        params: List[Any] = []

        if status:
            query += ' AND status = ?'
            params.append(status.value)
        if symbol:
            query += ' AND symbol LIKE ?'
            params.append(f"%{symbol.upper()}%")
        if asset_class:
            query += ' AND asset_class = ?'
            params.append(asset_class.value)
        if start_date:
            query += f' AND {date_column} >= ?'
            params.append(start_date.isoformat())
        if end_date:
            query += f' AND {date_column} <= ?'
            params.append(end_date.isoformat())

        order_column = "entry_time" if date_basis == "entry" else "exit_time"
        query += f' ORDER BY {order_column} DESC'

        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_trade(row) for row in rows]

    def update_trade(self, trade: Trade) -> bool:
        """Update an existing trade"""
        sql = '''
            UPDATE trades SET
                symbol = ?,
                trade_type = ?,
                asset_class = ?,
                quantity = ?,
                entry_price = ?,
                exit_price = ?,
                stop_loss = ?,
                take_profit = ?,
                commission = ?,
                swap = ?,
                entry_time = ?,
                exit_time = ?,
                status = ?,
                setup = ?,
                rating = ?,
                discipline_rating = ?,
                tags = ?,
                screenshot_path = ?,
                session = ?,
                position_id = ?,
                notes = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        '''
        with self._connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql, (
                    trade.symbol.upper(),
                    trade.trade_type.value,
                    trade.asset_class.value,
                    trade.quantity,
                    trade.entry_price,
                    trade.exit_price,
                    trade.stop_loss,
                    trade.take_profit,
                    trade.commission,
                    trade.swap,
                    trade.entry_time.isoformat() if trade.entry_time else None,
                    trade.exit_time.isoformat() if trade.exit_time else None,
                    trade.status.value,
                    trade.setup,
                    trade.rating,
                    trade.discipline_rating,
                    trade.tags,
                    trade.screenshot_path,
                    trade.session,
                    trade.position_id,
                    trade.notes,
                    trade.id
                ))
                conn.commit()
                return cursor.rowcount > 0
            except sqlite3.Error as e:
                print(f"Error updating trade {trade.id}: {e}")
                return False

    def delete_trade(self, trade_id: str) -> bool:
        """Delete a trade by ID"""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM trades WHERE id = ?', (trade_id,))
            conn.commit()
            return cursor.rowcount > 0

    def clear_all_trades(self) -> bool:
        """Remove all trades from the database"""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM trades')
            conn.commit()
            return True

    # Daily Log Operations
    def save_daily_log(
        self,
        date_str: str,
        market_bias: str = "Neutral",
        news_events: str = "",
        rules_checked: bool = True,
        mindset_score: int = 5,
        post_market_notes: str = ""
    ) -> bool:
        """Record or update daily preparation and review"""
        sql = '''
            INSERT INTO daily_logs (date, market_bias, news_events, rules_checked, mindset_score, post_market_notes)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(date) DO UPDATE SET
                market_bias = excluded.market_bias,
                news_events = excluded.news_events,
                rules_checked = excluded.rules_checked,
                mindset_score = excluded.mindset_score,
                post_market_notes = excluded.post_market_notes
        '''
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(sql, (date_str, market_bias, news_events, 1 if rules_checked else 0, mindset_score, post_market_notes))
            conn.commit()
            return True

    def get_daily_log(self, date_str: str) -> Optional[Dict[str, Any]]:
        """Fetch daily prep & review by date (YYYY-MM-DD)"""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM daily_logs WHERE date = ?', (date_str,))
            row = cursor.fetchone()
            if row:
                return dict(row)
        return None

    def get_all_daily_logs(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Fetch recent daily journal logs"""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM daily_logs ORDER BY date DESC LIMIT ?', (limit,))
            return [dict(r) for r in cursor.fetchall()]

    def calculate_performance_metrics(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """Calculate complete performance metrics using TradingCalculator"""
        trades = self.get_all_trades(status=TradeStatus.CLOSED, start_date=start_date, end_date=end_date)
        return TradingCalculator.analyze_trade_series(trades)

    def export_csv(self, file_path: str) -> int:
        """Export all trades to a CSV file. Returns count of exported rows."""
        trades = self.get_all_trades()
        if not trades:
            return 0

        path = Path(file_path).resolve()
        path.parent.mkdir(parents=True, exist_ok=True)

        fieldnames = [
            "id", "symbol", "trade_type", "asset_class", "quantity",
            "entry_price", "exit_price", "stop_loss", "take_profit",
            "commission", "swap", "entry_time", "exit_time", "status",
            "setup", "rating", "discipline_rating", "tags", "session",
            "position_id", "notes", "net_pnl", "gross_pnl", "return_pct", "r_multiple"
        ]

        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            for trade in trades:
                d = trade.to_dict()
                writer.writerow({k: d.get(k, "") for k in fieldnames})

        return len(trades)

    def import_csv(self, file_path: str) -> int:
        """Import trades from a CSV file. Returns count of successfully imported rows."""
        path = Path(file_path).resolve()
        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        count = 0
        with open(path, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    entry_time = datetime.fromisoformat(row["entry_time"]) if row.get("entry_time") else datetime.now()
                    exit_time = datetime.fromisoformat(row["exit_time"]) if row.get("exit_time") else None

                    trade = Trade(
                        id=row.get("id") or f"IMP{count+1}",
                        symbol=row.get("symbol", "").upper(),
                        trade_type=TradeType(row.get("trade_type", "BUY").upper()),
                        asset_class=AssetClass(row.get("asset_class", "STOCKS").upper()),
                        quantity=float(row.get("quantity", 0)),
                        entry_price=float(row.get("entry_price", 0)),
                        exit_price=float(row["exit_price"]) if row.get("exit_price") else None,
                        stop_loss=float(row["stop_loss"]) if row.get("stop_loss") else None,
                        take_profit=float(row["take_profit"]) if row.get("take_profit") else None,
                        commission=float(row.get("commission", 0.0)),
                        swap=float(row.get("swap", 0.0)),
                        entry_time=entry_time,
                        exit_time=exit_time,
                        status=TradeStatus(row.get("status", "OPEN").upper()),
                        setup=row.get("setup", "Discretionary"),
                        rating=int(row.get("rating", 0)),
                        discipline_rating=int(row.get("discipline_rating", 5)),
                        tags=row.get("tags", ""),
                        session=row.get("session", "NY"),
                        position_id=row.get("position_id"),
                        notes=row.get("notes", "")
                    )
                    existing = self.get_trade(trade.id)
                    if existing:
                        self.update_trade(trade)
                    else:
                        self.add_trade(trade)
                    count += 1
                except Exception as ex:
                    print(f"Skipping malformed CSV row {row}: {ex}")

        return count

    def _row_to_trade(self, row: sqlite3.Row) -> Trade:
        """Safely convert database row to Trade object using named column keys"""
        keys = row.keys()

        entry_time_str = row["entry_time"] if "entry_time" in keys else None
        exit_time_str = row["exit_time"] if "exit_time" in keys else None

        entry_time = None
        if entry_time_str:
            try:
                entry_time = datetime.fromisoformat(entry_time_str)
            except Exception:
                pass

        exit_time = None
        if exit_time_str:
            try:
                exit_time = datetime.fromisoformat(exit_time_str)
            except Exception:
                pass

        return Trade(
            id=row["id"],
            symbol=row["symbol"],
            trade_type=TradeType(row["trade_type"]),
            asset_class=AssetClass(row["asset_class"]) if ("asset_class" in keys and row["asset_class"]) else AssetClass.STOCKS,
            quantity=float(row["quantity"]),
            entry_price=float(row["entry_price"]),
            exit_price=float(row["exit_price"]) if row["exit_price"] is not None else None,
            stop_loss=float(row["stop_loss"]) if row["stop_loss"] is not None else None,
            take_profit=float(row["take_profit"]) if row["take_profit"] is not None else None,
            commission=float(row["commission"]) if ("commission" in keys and row["commission"] is not None) else 0.0,
            swap=float(row["swap"]) if ("swap" in keys and row["swap"] is not None) else 0.0,
            entry_time=entry_time,
            exit_time=exit_time,
            status=TradeStatus(row["status"]),
            setup=row["setup"] if ("setup" in keys and row["setup"]) else "Discretionary",
            rating=int(row["rating"]) if ("rating" in keys and row["rating"] is not None) else 0,
            discipline_rating=int(row["discipline_rating"]) if ("discipline_rating" in keys and row["discipline_rating"] is not None) else 5,
            tags=row["tags"] if ("tags" in keys and row["tags"]) else "",
            screenshot_path=row["screenshot_path"] if "screenshot_path" in keys else None,
            session=row["session"] if ("session" in keys and row["session"]) else "NY",
            position_id=str(row["position_id"]) if ("position_id" in keys and row["position_id"]) else None,
            notes=row["notes"] or ""
        )
