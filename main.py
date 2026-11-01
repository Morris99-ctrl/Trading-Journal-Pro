"""
Trading Journal Pro - Application Entry Point
Supports Modern Web Dashboard (Default), Pygame GUI, and Terminal CLI.
"""

import sys
import os
import threading
import time
import webbrowser

# Ensure current directory is on sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from services import TradeService


def open_browser():
    """Wait for server startup and open default web browser"""
    time.sleep(1.2)
    webbrowser.open("http://127.0.0.1:5000")


def launch_web():
    """Launch the Modern Web Dashboard"""
    from web_app import app
    print("=" * 65)
    print("★ LAUNCHING TRADING JOURNAL PRO - MODERN WEB DASHBOARD ★")
    print("Web UI running at: http://127.0.0.1:5000")
    print("Opening your browser automatically...")
    print("Press Ctrl+C in terminal to stop.")
    print("=" * 65)
    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=5000, debug=False)


def launch_gui(service):
    """Launch Pygame Desktop GUI"""
    from ui import TradingJournalUI
    ui = TradingJournalUI(service)
    ui.run()


def launch_cli(service):
    """Launch Terminal CLI"""
    from cli import TradingJournalCLI
    cli = TradingJournalCLI(service)
    cli.run()


def main():
    """Main application entry point"""
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "trading_journal.db")
    service = TradeService(db_path)

    args = sys.argv[1:]

    # Demo data must be explicitly requested and must never be mixed into a real journal.
    if "--demo" in args:
        if service.get_all_trades():
            print("Demo data not loaded: the journal already contains trades.")
        else:
            print("Loading sample trades for demo use...")
            service.seed_sample_data()
    if "--gui" in args:
        launch_gui(service)
    elif "--cli" in args:
        launch_cli(service)
    else:
        # Default mode: Modern Web Dashboard
        launch_web()


if __name__ == "__main__":
    main()

