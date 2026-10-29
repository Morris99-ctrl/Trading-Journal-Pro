# Trading Journal Pro

An institutional-grade trading journal, automated MetaTrader 5 (MT5) synchronization engine, and quantitative portfolio analytics suite for active traders across **Forex**, **Commodities / Metals**, **Crypto**, **Indices**, and **Stocks**.

---

## Key Features

### 1. Automated MetaTrader 5 (MT5) Synchronization
- **Direct Terminal Integration**: Connects via the official MetaTrader 5 Python IPC API to read deals and orders directly from your local MT5 terminal.
- **Broker-authoritative P&L**: Aggregates all deals for a position, including partial exits, and uses MT5-reported profit, commission, swap, and fee amounts for realized net P&L. Price × volume remains a fallback only for manual trades without broker P&L.
- **Stop Loss & Take Profit Extraction**: Pulls original order SL and TP targets automatically.
- **Idempotent Position Reconciliation**: Uses MT5 position tickets (`MT5-<ticket>`) and refreshes existing MT5 records when later deals arrive. Reversal deals are skipped until the application has a dedicated lifecycle-splitting model.
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

## Financial Metric Notes

- Date-bounded realized-performance reports use **exit date**: a trade closed in the selected period is included even if it was opened earlier. Entry-date filtering remains available for trade-cohort analysis.
- Legacy trade-analysis Sharpe and Sortino values use eligible per-trade returns and are diagnostics, not portfolio-period ratios. The portfolio analytics module uses account-equity snapshots and external cash-flow records, computes Modified Dietz returns per snapshot interval, and derives flow-neutral drawdown from a compounded return index. Risk ratios are unannualized and are only emitted when observation intervals have a consistent cadence.
- Record actual account equity snapshots and deposits/withdrawals through `TradeService.record_equity_snapshot()` and `TradeService.record_portfolio_cash_flow()`; query the resulting series with `TradeService.get_portfolio_performance()`. Snapshots must use one account currency and unique timestamps per account. This does not infer open-position mark-to-market equity from trade history. Modified Dietz is an approximation; exact time-weighted returns require valuations bracketing each external cash flow.
- MT5 broker gross/net P&L is persisted separately from the journal's price-based fallback. The database migration adds nullable columns, so existing manual trades retain their previous calculation behavior. Realized-P&L analytics consume broker net P&L when available.
- MT5 lot volume cannot safely be treated as share units. Until symbol contract size, tick value, and account-currency conversion are captured, trades carrying a broker P&L value do not publish a guessed return percentage, cash risk, or R-multiple, even if an import omitted the position ID. Legacy return diagnostics therefore use only manual trades with a defensible price-notional denominator.
- These per-trade ratios are diagnostic only and should not be compared directly with annualized portfolio ratios from fund factsheets. A future portfolio-risk module should calculate time-weighted daily equity returns before presenting annualized Sharpe/Sortino metrics.

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
This starts the local server and opens your browser at **`http://127.0.0.1:5000`**. A new journal starts empty so fictional trades are never mixed into your records.

To explicitly load sample trades for a demo, use:
```bash
python main.py --demo
```
The demo option only loads samples when the journal is empty. It will refuse to add them to a journal that already contains trades.

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
Type `sync` to pull MT5 deals from the command line, `trades` to list positions, `stats` for quantitative ratios, or `web` to launch the browser UI. Use `python cli.py --demo` to load sample trades for a demo; samples are only added to an empty journal. The CLI's `sample` command follows the same safety rule.
