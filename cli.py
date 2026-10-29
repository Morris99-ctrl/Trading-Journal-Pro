#!/usr/bin/env python3
"""
Trading Journal CLI
Professional Command-Line Interface for trade tracking, analytics, and risk management.
"""

import os
import sys
from typing import Optional
from datetime import datetime, timedelta
from models import Trade, TradeType, TradeStatus, AssetClass
from services import TradeService
from calculators import TradingCalculator


class TradingJournalCLI:
    """Professional command-line interface for trading journals"""

    def __init__(self, service: TradeService):
        self.service = service

    def run(self):
        """Main loop for CLI"""
        print("\n" + "=" * 75)
        print("★ PROFESSIONAL TRADING JOURNAL CLI ★")
        print("Type 'help' for available commands or 'stats' for quick overview.")
        print("=" * 75)

        while True:
            try:
                raw = input("\n[TradingJournal] > ").strip()
                if not raw:
                    continue

                parts = raw.split()
                cmd = parts[0].lower()
                arg = " ".join(parts[1:]) if len(parts) > 1 else ""

                if cmd in ("exit", "quit", "q"):
                    print("Goodbye!")
                    break
                elif cmd == "help":
                    self.show_help()
                elif cmd in ("trades", "list", "all"):
                    self.list_trades()
                elif cmd == "open":
                    self.list_open_trades()
                elif cmd == "closed":
                    self.list_closed_trades()
                elif cmd == "add":
                    self.add_trade_interactive()
                elif cmd in ("sync", "mt5"):
                    days = int(arg) if arg and arg.isdigit() else 60
                    print(f"Connecting to MetaTrader 5 and syncing deals from last {days} days...")
                    try:
                        res = self.service.sync_mt5(days_back=days)
                        print(f"✓ {res['message']}")
                    except Exception as e:
                        print(f"MT5 Sync error: {e}")
                elif cmd == "web":
                    print("Launching Web Dashboard at http://127.0.0.1:5000...")
                    import webbrowser
                    webbrowser.open("http://127.0.0.1:5000")
                    os.system(f'"{sys.executable}" web_app.py')
                elif cmd == "close":
                    if not arg:
                        print("Usage: close <trade_id>")
                    else:
                        self.close_trade_interactive(arg)
                elif cmd == "delete":
                    if not arg:
                        print("Usage: delete <trade_id>")
                    else:
                        self.delete_trade(arg)
                elif cmd in ("stats", "summary", "perf"):
                    self.show_stats()
                elif cmd == "period":
                    if not arg:
                        print("Usage: period <days> (e.g., period 30)")
                    else:
                        self.period_stats(arg)
                elif cmd in ("calc", "risk"):
                    self.position_calculator()
                elif cmd == "export":
                    filename = arg if arg else "trades_export.csv"
                    count = self.service.export_csv(filename)
                    print(f"Successfully exported {count} trades to {filename}")
                elif cmd == "import":
                    if not arg:
                        print("Usage: import <filename.csv>")
                    else:
                        count = self.service.import_csv(arg)
                        print(f"Successfully imported {count} trades from {arg}")
                elif cmd == "sample":
                    self.service.seed_sample_data(clear_first=False)
                    print("Sample trades seeded successfully!")
                elif cmd == "clear":
                    confirm = input("Are you sure you want to delete ALL trades? (y/N): ").strip().lower()
                    if confirm == 'y':
                        self.service.db.clear_all_trades()
                        print("All trades cleared.")
                else:
                    print(f"Unknown command: '{cmd}'. Type 'help' for commands.")
            except KeyboardInterrupt:
                print("\nExiting...")
                break
            except Exception as e:
                print(f"Error: {e}")

    def show_help(self):
        """Display help command menu"""
        help_text = """
Commands:
  trades, list       - View all recorded trades
  open               - View currently active open positions
  closed             - View closed trades with realized P&L
  add                - Interactive trade entry wizard
  close <trade_id>   - Close an open trade with exit price & notes
  delete <trade_id>  - Delete a trade by ID
  stats, summary     - Display comprehensive performance & risk metrics
  period <days>      - Analyze performance over the last N days
  calc               - Position Sizing & Risk Management calculator
  export [file.csv]  - Export database to CSV
  import <file.csv>  - Import trades from CSV
  sample             - Load realistic multi-asset sample trades
  clear              - Delete all trades from database
  exit, quit         - Exit the CLI
        """
        print(help_text)

    def list_trades(self):
        """List all trades with comprehensive table formatting"""
        trades = self.service.get_all_trades()
        if not trades:
            print("No trades found in journal. Type 'add' to record a trade or 'sample' to load examples.")
            return

        print(f"\n{'ID':<10} {'Symbol':<8} {'Type':<6} {'Asset':<8} {'Qty':<8} {'Entry':<9} {'Exit':<9} {'Net P&L':<11} {'R-Mult':<8} {'Status':<7}")
        print("-" * 92)

        for t in trades:
            exit_str = f"{t.exit_price:.2f}" if t.exit_price is not None else "--"
            pnl_str = f"${t.net_pnl:+.2f}" if t.net_pnl is not None else "--"
            r_str = f"{t.r_multiple:+.2f}R" if t.r_multiple is not None else "--"
            print(f"{t.id:<10} {t.symbol:<8} {t.trade_type.value:<6} {t.asset_class.value:<8} {t.quantity:<8.2f} {t.entry_price:<9.2f} {exit_str:<9} {pnl_str:<11} {r_str:<8} {t.status.value:<7}")

    def list_open_trades(self):
        """List active open positions with planned risk"""
        trades = self.service.get_open_trades()
        if not trades:
            print("\nNo open trades found.")
            return

        print(f"\n{'ID':<10} {'Symbol':<8} {'Type':<6} {'Qty':<8} {'Entry':<9} {'Stop Loss':<10} {'Target':<10} {'Risk $':<9} {'Setup':<20}")
        print("-" * 92)

        for t in trades:
            sl_str = f"{t.stop_loss:.2f}" if t.stop_loss else "--"
            tp_str = f"{t.take_profit:.2f}" if t.take_profit else "--"
            risk_str = f"${t.planned_total_risk:.2f}" if t.planned_total_risk else "--"
            print(f"{t.id:<10} {t.symbol:<8} {t.trade_type.value:<6} {t.quantity:<8.2f} {t.entry_price:<9.2f} {sl_str:<10} {tp_str:<10} {risk_str:<9} {t.setup:<20}")

    def list_closed_trades(self):
        """List closed trades with realized performance"""
        trades = self.service.get_closed_trades()
        if not trades:
            print("\nNo closed trades found.")
            return

        print(f"\n{'ID':<10} {'Symbol':<8} {'Type':<6} {'Entry':<9} {'Exit':<9} {'Net P&L':<11} {'Return %':<10} {'R':<8} {'Setup':<18}")
        print("-" * 88)

        for t in trades:
            pnl = t.net_pnl or 0.0
            ret_pct = f"{t.return_pct:+.2f}%" if t.return_pct is not None else "--"
            r_str = f"{t.r_multiple:+.2f}R" if t.r_multiple is not None else "--"
            print(f"{t.id:<10} {t.symbol:<8} {t.trade_type.value:<6} {t.entry_price:<9.2f} {t.exit_price:<9.2f} ${pnl:<+10.2f} {ret_pct:<10} {r_str:<8} {t.setup:<18}")

    def add_trade_interactive(self):
        """Interactive prompt to record a new trade with risk calculations"""
        print("\n--- New Trade Entry Wizard ---")
        try:
            symbol = input("Symbol (e.g. NVDA, EURUSD, BTCUSDT): ").strip().upper()
            if not symbol:
                print("Symbol cannot be empty.")
                return

            t_type = input("Trade Direction (BUY / SHORT) [default: BUY]: ").strip().upper() or "BUY"
            if t_type not in ("BUY", "SHORT", "LONG", "SELL"):
                print("Invalid direction. Use BUY or SHORT.")
                return

            asset_class = input("Asset Class (STOCKS/FOREX/CRYPTO/FUTURES) [STOCKS]: ").strip().upper() or "STOCKS"
            quantity = float(input("Position Size / Quantity: ").strip())
            entry_price = float(input("Entry Price: ").strip())

            sl_in = input("Stop Loss Price (optional, Enter to skip): ").strip()
            stop_loss = float(sl_in) if sl_in else None

            tp_in = input("Take Profit Price (optional, Enter to skip): ").strip()
            take_profit = float(tp_in) if tp_in else None

            comm_in = input("Commission / Fees [0.0]: ").strip()
            commission = float(comm_in) if comm_in else 0.0

            setup = input("Strategy / Setup (e.g., Breakout, Pullback) [Discretionary]: ").strip() or "Discretionary"
            notes = input("Notes / Trade Rationale: ").strip()

            trade = self.service.create_trade(
                symbol=symbol,
                trade_type=t_type,
                asset_class=asset_class,
                quantity=quantity,
                entry_price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                commission=commission,
                setup=setup,
                notes=notes,
                status=TradeStatus.OPEN
            )

            print(f"\n Trade recorded successfully! ID: {trade.id}")
            if trade.planned_risk_reward:
                print(f"Planned Reward/Risk: {trade.planned_risk_reward:.2f}:1")
            if trade.planned_total_risk:
                print(f"Total Capital at Risk: ${trade.planned_total_risk:.2f}")

        except ValueError as ve:
            print(f"Input error: {ve}")

    def close_trade_interactive(self, trade_id: str):
        """Close an active position"""
        trade = self.service.get_trade(trade_id)
        if not trade:
            print(f"Trade '{trade_id}' not found.")
            return
        if not trade.is_open:
            print(f"Trade '{trade_id}' is already closed.")
            return

        try:
            print(f"\nClosing Trade {trade.id} ({trade.symbol} {trade.trade_type.value} @ {trade.entry_price})")
            exit_price = float(input("Exit Price: ").strip())
            comm_in = input(f"Exit Commission [0.0]: ").strip()
            exit_commission = float(comm_in) if comm_in else 0.0
            notes = input("Exit Notes / Review: ").strip()

            closed_trade = self.service.close_trade(
                trade_id=trade_id,
                exit_price=exit_price,
                commission=exit_commission,
                notes=notes
            )

            if closed_trade and closed_trade.net_pnl is not None:
                pnl = closed_trade.net_pnl
                r = closed_trade.r_multiple
                r_str = f" ({r:+.2f}R)" if r is not None else ""
                print(f"\nTrade {trade_id} closed! Net P&L: ${pnl:+.2f}{r_str}")
        except ValueError as ve:
            print(f"Input error: {ve}")

    def delete_trade(self, trade_id: str):
        """Delete trade by ID"""
        trade = self.service.get_trade(trade_id)
        if not trade:
            print(f"Trade '{trade_id}' not found.")
            return
        confirm = input(f"Delete trade {trade_id} ({trade.symbol})? (y/N): ").strip().lower()
        if confirm == 'y':
            self.service.delete_trade(trade_id)
            print(f"Trade {trade_id} deleted.")

    def show_stats(self):
        """Display overall quantitative statistics"""
        summary = self.service.get_performance_summary()
        self._print_stats_card("OVERALL TRADING PERFORMANCE", summary)

    def period_stats(self, days_arg: str):
        """Display stats for specific lookback period"""
        try:
            days = int(days_arg)
            start_date = datetime.now() - timedelta(days=days)
            summary = self.service.get_performance_summary(start_date=start_date)
            self._print_stats_card(f"PERFORMANCE - LAST {days} DAYS", summary)
        except ValueError:
            print("Invalid lookback days. Use an integer like 'period 30'.")

    def _print_stats_card(self, title: str, s: dict):
        """Formatted stats card"""
        print("\n" + "=" * 65)
        print(f"  {title}")
        print("=" * 65)
        print(f"  Total Trades        : {s['total_trades']:<8} (Wins: {s['winning_trades']}, Losses: {s['losing_trades']})")
        print(f"  Win Rate            : {s['win_rate']:.1f}%")
        print(f"  Net Realized P&L    : ${s['total_pnl']:+,.2f}")
        print(f"  Profit Factor       : {s['profit_factor']}")
        print(f"  Expectancy ($/trade): ${s['expectancy']:+,.2f}")
        print(f"  Avg R-Multiple      : {s['avg_r_multiple']:+.2f}R")
        print(f"  Average Win         : ${s['average_win']:,.2f}")
        print(f"  Average Loss        : ${s['average_loss']:,.2f}")
        print(f"  Win / Loss Ratio    : {s['win_loss_ratio']}")
        print(f"  Max Drawdown ($)    : ${s['max_drawdown']:,.2f} ({s['max_drawdown_pct']:.1f}%)")
        print(f"  Sharpe Ratio        : {s['sharpe_ratio']}")
        print(f"  Sortino Ratio       : {s['sortino_ratio']}")
        print(f"  Max Win Streak      : {s['max_win_streak']} trades")
        print(f"  Max Loss Streak     : {s['max_loss_streak']} trades")
        print(f"  Long P&L / Win%     : ${s['long_pnl']:+,.2f} ({s['long_win_rate']:.1f}%)")
        print(f"  Short P&L / Win%    : ${s['short_pnl']:+,.2f} ({s['short_win_rate']:.1f}%)")
        print("=" * 65)

    def position_calculator(self):
        """Interactive position size calculator"""
        print("\n--- Position Sizing & Risk Management Calculator ---")
        try:
            account = float(input("Account Equity / Capital ($): ").strip())
            risk_pct = float(input("Risk Percentage (% of account, e.g. 1.0): ").strip())
            entry = float(input("Entry Price ($): ").strip())
            stop = float(input("Stop Loss Price ($): ").strip())

            result = TradingCalculator.calculate_position_size(
                account_size=account,
                risk_percentage=risk_pct,
                entry_price=entry,
                stop_loss=stop
            )

            print("\n--- Recommended Sizing ---")
            print(f"  Max Dollar Risk   : ${result['dollar_risk']:,.2f} ({risk_pct}%)")
            print(f"  Risk Per Share    : ${result['risk_per_unit']:,.2f}")
            print(f"  Position Size     : {result['shares']:,.2f} units")
            print(f"  Total Position    : ${result['position_value']:,.2f}")
            print(f"  Account Leverage  : {result['leverage']:.2f}x")
        except Exception as e:
            print(f"Calculation error: {e}")


def main():
    service = TradeService("trading_journal.db")
    if len(service.get_all_trades()) == 0:
        print("Initializing journal with sample trades...")
        service.seed_sample_data()
    cli = TradingJournalCLI(service)
    cli.run()


if __name__ == "__main__":
    main()
