# Priority 5: Scheduled portfolio equity snapshots

## Design

The scheduled capture is a one-shot Python command, intended to be called by the operating system's scheduler. This avoids starting a background scheduler inside Flask, where debug reloaders or multiple web workers could accidentally create duplicate jobs.

Each run calls the existing `TradeService.capture_mt5_equity_snapshot()` method. The broker's account balance, equity, account currency, login/server identity, capture time, and source are persisted through the existing SQLite equity-snapshot table. The command does not place, modify, or close trades.

## Manual test

With MT5 open and logged into the intended account, run from the repository root:

```powershell
python scripts/capture_scheduled_snapshot.py
```

A successful run prints a JSON confirmation with a masked account login and snapshot ID. Confirm the new point appears in the dashboard's portfolio equity history. Run the command twice at different times to confirm that two observations are stored.

## Windows Task Scheduler

Configure this only after the manual command succeeds:

1. Open **Task Scheduler** and choose **Create Task**.
2. Name it `Trading Journal Pro - Equity Snapshot`.
3. Under **General**, choose **Run only when user is logged on**. The MT5 Python IPC connection depends on the desktop terminal session.
4. Under **Triggers**, create a daily trigger and select **Repeat task every: 1 hour** for **Indefinitely**. This is a starting cadence; daily snapshots are also acceptable if that is the desired reporting resolution.
5. Under **Actions**, choose **Start a program**:
   - Program/script: the full path to the Python executable in the project's virtual environment, for example `C:\path\to\project\.venv\Scripts\python.exe`.
   - Add arguments: `scripts\capture_scheduled_snapshot.py`
   - Start in: the repository root folder.
6. Under **Conditions**, do not require the computer to be idle if you want the task to run during active trading hours.
7. Save the task. Keep MT5 open and logged in when snapshots are due.
8. Use **Run** in Task Scheduler once, then inspect **Last Run Result** and the dashboard equity history.

The exact Python executable and repository paths must be taken from your own computer. Do not paste credentials into Task Scheduler arguments or source files.

## Operational rules

- MT5 must be installed, open, connected, and logged into the intended account.
- If the terminal is closed or disconnected, the command fails and prints an error; it does not invent a snapshot.
- The database path is fixed to the repository's `trading_journal.db`, regardless of the scheduler's working directory.
- The task runs in the logged-in desktop session. Avoid running multiple copies of this task concurrently.
- Use a stable snapshot cadence. The portfolio analytics code requires consistent observation intervals for risk ratios; missing runs or irregular timing can make those ratios unavailable.
- Deposits and withdrawals must still be recorded separately so Modified Dietz returns are adjusted correctly.
- Back up the journal database before enabling recurring capture.

## What this does not do

This does not keep MT5 running, reconnect to a broker, or guarantee that Windows is awake at the scheduled time. It is an operating-system scheduled one-shot capture, not a cloud service.
