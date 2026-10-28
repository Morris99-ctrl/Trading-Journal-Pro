# Trading Journal Pro

An institutional-grade trading journal, automated MetaTrader 5 (MT5) synchronization engine, and quantitative portfolio analytics suite for active traders across **Forex**, **Commodities / Metals**, **Crypto**, **Indices**, and **Stocks**.

---

## Key Features

### 1. Automated MetaTrader 5 (MT5) Synchronization
- **Direct Terminal Integration**: Connects via the official MetaTrader 5 Python IPC API to read deals and orders directly from your local MT5 terminal.
- **Round-Trip Reconciliation**: Pairs `DEAL_ENTRY_IN` and `DEAL_ENTRY_OUT` deals by `position_id` to extract lot size, entry price, exit price, commission, swap fees, and realized net P&L.
- **Stop Loss & Take Profit Extraction**: Pulls original order SL and TP targets automatically.
- **Zero Duplicate Risk**: Keyed on unique MT5 position tickets (`MT5-<ticket>`), preventing double imports.
- **Auto-Asset Classification**: Automatically classifies tickers (e.g. `XAUUSD` -> Commodities, `EURUSD` -> Forex, `US30` -> Indices, `BTCUSDT` -> Crypto).

### 2. Modern Web Dashboard (Default)
- **FinTech Dark-Mode UI**: Built with Tailwind CSS and ApexCharts.
- **Interactive Diagrams & Visual Charts**:
  - **Portfolio Equity Growth Curve**: Vector spline area chart with gradient shading, zoom, and hover balance tooltips.
  - **Win / Loss Ratio Donut Chart**: Visual outcome breakdown with win probability and center percentage badge.
  - **Directional Performance Chart**: Side-by-side Long vs. Short net P&L and win rate.
  - **Strategy & Setup Attribution Bar Chart**: Horizontal bar chart comparing profitability across setups (`Bull Flag`, `Support Bounce`, `Order Block`, etc.).
  - **Daily P&L Bar Chart / Histogram**: Green bars for winning days, red bars for losing days.
- **Real-Time MT5 Status Pill**: Live connection badge (`🟢 MT5 Live: FBS-Real (#42920594)`) with one-click sync button (Last 7 Days, Last 30 Days, Last 90 Days, All History).
- **Interactive Modals**:
  - `+ New Trade` modal with live real-time risk/reward calculation and discipline rating.
  - `Close Position` modal with inline P&L realization.
  - `Trade Details` modal with chart screenshot viewer and psychology review.
  - `Position Sizing Calculator` modal.
  - `Daily Prep & Reflection` modal (macro bias, news calendar, mindset score, post-session notes).

### 3. Practical Daily Use Tools
- **Psychology & Discipline Tracking**: Record execution discipline ratings (1-5 stars) and adherence tags (*Followed Plan*, *FOMO*, *Moved Stop*, *Revenge Trade*).
- **Chart Screenshot Attachments**: Attach chart before/after screenshots directly to each trade.
- **Data Portability**: One-click CSV Export and Import for external backups or broker migration.
- **Dual Interface**: Run the **Web Dashboard** (`python main.py`) or the **Terminal CLI** (`python cli.py`).

---

## Getting Started

### 1. Installation
Install requirements (Flask, MetaTrader5, and Pygame-ce):
```bash
pip install -r requirements.txt
```

### 2. Launch the Web Dashboard (Recommended)
```bash
python main.py
```
This automatically starts the local server and opens your browser at **`http://127.0.0.1:5000`**.

### 3. MetaTrader 5 Sync
1. Ensure your MetaTrader 5 terminal is running on your computer.
2. In the top navigation bar of the Web Dashboard, verify the green connection pill:
   `MT5 Live: <Broker> (#<Account>)`
3. Select your lookback window (e.g., *Last 30 Days*) and click **Sync MT5**.
4. All closed and open positions will instantly import and populate your charts and tables!

### 4. Running the CLI Interface
```bash
python cli.py
```
Type `sync` to pull MT5 deals from the command line, `trades` to list positions, `stats` for quantitative ratios, or `web` to launch the browser UI.
