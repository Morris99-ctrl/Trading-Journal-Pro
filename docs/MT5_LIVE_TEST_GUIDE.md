# Priority 4: Live MetaTrader 5 validation

## Purpose

Validate the connection and the shape of real broker data before importing or reconciling it into the journal. The diagnostic is read-only: it does not place, modify, or close orders and does not write to the journal database.

## Before running

1. Use the Windows computer where your MetaTrader 5 desktop terminal is installed.
2. Open MT5 and log in to the intended demo account first. A demo account is preferred for the first pass.
3. Keep the terminal running and connected.
4. Use the same Python installation/environment in which the project dependencies are installed.
5. Do not send passwords, investor passwords, API keys, or unmasked account numbers.

## Run the diagnostic

From the repository root:

```powershell
python -m pip install -r requirements.txt
python scripts/mt5_readonly_diagnostics.py --days 30
```

The script reports:
- Whether the Python MT5 package can initialize the local terminal.
- Masked account login, broker server/company, and account currency.
- Whether terminal/account information is readable.
- Number and symbols of currently open positions.
- Number of historical deals and position groups found in the selected lookback.
- How many position groups the current lifecycle aggregator supports versus skips.
- Confirmation that no orders were placed, modified, or closed and no journal database was written.

The script deliberately omits account balance/equity values, terminal filesystem path, and full account login from the report. Do not manually add passwords or other secrets when sharing results.

## Validation sequence

1. Run the diagnostic on a demo account with the terminal open.
2. Save the JSON output and share it for review. Check that `success` is true and that account currency/server are the expected demo account.
3. Compare the open-position count and symbols with the MT5 Trade tab.
4. Compare the historical deal count and symbols with MT5 History for the same lookback. MT5 History display filters can affect what is visible; set the terminal History tab to the full relevant period.
5. Identify one closed position with a simple lifecycle and compare its individual deal rows in MT5 History: entry/exit volume, profit, commission, swap, and fee.
6. Identify a position with partial exits if one exists. Verify that all its deals share the same position identifier and that their volumes reconcile to the original entry volume.
7. Only after the read-only report is reviewed should we run the application's Sync MT5 action against a backed-up test journal. Then compare imported trade rows and broker P&L against the terminal history.

## Important limitations

- A successful diagnostic proves terminal connectivity and basic data retrieval, not that every broker's deal conventions are fully supported.
- The current importer intentionally skips reversal lifecycles and malformed/over-exited position groups.
- The current commission field stores the absolute sum of signed commissions, while broker net P&L uses signed profit + commission + swap + fee. We must compare the journal's broker net P&L with the broker's realized deal totals, not infer it from entry/exit prices.
- Do not run the first import against your only production journal. Back it up and use a separate test database first.
- If the terminal is logged into a live account, the diagnostic still performs read-only queries, but a demo account is the safer first test.

## What to send back

Share the JSON output from the diagnostic, with any broker/account details you do not want disclosed redacted. The login is already masked by the script. Never share passwords or authentication codes.
