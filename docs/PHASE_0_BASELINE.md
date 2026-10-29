# Phase 0: Baseline Audit

**Repository:** `Morris99-ctrl/Trading-Journal-Pro`  
**Baseline branch:** `main`  
**Audit branch:** `phase-0/baseline-audit`  
**Audit date:** 2026-10-29  
**Status:** Static baseline underway. Safe model, CLI, and sample-data safety regression tests pass in CI on Python 3.11 and 3.12. The sample-data startup remediation is verified on the audit branch; broader application validation remains outstanding.

## Scope and limitations

This is an initial repository inventory and static inspection, not a complete security audit. Source files were inspected through GitHub. The application and test suite have **not** been executed in a local Python environment during this pass. Findings below must be reproduced and regression-tested before they are marked fixed.

## Repository inventory

Root modules/files include `main.py`, `web_app.py`, `ui.py`, `cli.py`, `models.py`, `services.py`, `data.py`, `calculators.py`, `analytics.py`, `mt5_service.py`, `test_suite.py`, `requirements.txt`, `README.md`, and `Start_Journal.bat`, plus `templates/`, `static/`, and `screenshots/`.

- Only `main` was present at the time of inventory.
- The recent commit listing returned one initial commit.
- The audit branch now includes `.github/workflows/tests.yml`; its latest run passed the safe unit-test suite on Python 3.11 and 3.12. This workflow was added after the initial inventory.
- Dependencies are specified with minimum versions, not a lockfile or fully pinned requirements.
- `.gitignore` excludes Python caches, virtual environments, environment files, logs, SQLite/database files, and `instance/`.

## Initial findings register

| ID | Priority | Evidence | Risk / next action | Status |
|---|---|---|---|---|
| P0-01 | High | `web_app.py` sets `app.config["SECRET_KEY"]` to a hard-coded literal (line 22). | Move secret configuration to environment/configuration; fail safely when production secret is missing; inspect history and rotate if it was used outside local development. | Open |
| P0-02 | High | `templates/index.html` builds table/detail/modal markup with `innerHTML`, including trade-derived values (e.g. around lines 802 and 951). | Trace all interpolated values and prove exploitability; render user data with safe DOM APIs/textContent or contextual escaping; add XSS regression tests. | Open |
| P0-03 | High | `web_app.py` exposes mutating API routes for trades and MT5 sync; no authentication/authorization was visible in the inspected route handlers. `main.py` binds to loopback by default. | Document intended deployment. Keep local-only deployment explicit; add appropriate access control and CSRF protection if browser sessions or remote access are supported. | Open |
| P0-04 | High | `main.py` and `cli.py` seeded sample trades automatically when the database was empty. | Demo seeding is now opt-in via `--demo`; both entry points refuse to seed into a non-empty journal, and the CLI `sample` command has the same guard. Regression tests pass on Python 3.11 and 3.12. | Fixed on audit branch; not merged |
| P0-05 | High | `README.md` includes a concrete-looking MT5 server/account label: `FBS-Real (#42920594)`. | Confirm whether this is synthetic. Remove or replace with clearly fictional example data if it identifies a real account. | Open |
| P0-06 | High | `data.py` backup path uses `shutil.copy2` for the database (around line 126). | Verify database connection/transaction behavior; use SQLite's online backup API and test restore integrity. | Open |
| P0-07 | High | `calculators.py` computed Sharpe/Sortino from position-level trade returns and annualized Sharpe using a fixed assumption of 252 trades per year. | Removed the unsupported 252-trades/year annualization. Ratios are now explicitly unannualized per-observation diagnostics; README warns these are not portfolio-period ratios. Added ratio regression tests. | Fixed on audit branch; portfolio-level daily metrics still future work |
| P0-08 | High | `data.py` originally filtered all date ranges by `entry_time`, including realized-performance reporting. | Added explicit `date_basis='entry'|'exit'`; performance summaries and period analysis now filter closed trades by exit date, while entry-cohort filtering remains available. Added regression tests for both semantics. | Fixed on audit branch; not merged |
| P0-09 | High | `mt5_service.py` groups deals by `position_id` and selects entry/exit deals (around lines 126-192). | Test partial exits, multiple entries, reversals, commissions, swaps, and broker-reported realized P&L against imported journal values. | Open |
| P0-10 | Medium | `cli.py` originally called `os.system` in the `web` command without importing `os`. | Added `import os` and a regression test for the `web` command. Verify via CI; broader CLI behavior still needs testing. | Fixed in audit branch; expanded CI suite passed |
| P0-11 | Medium | API handlers in `web_app.py` return exception strings to clients in several error paths. | Return stable generic errors to clients and log details server-side without leaking secrets or internal state. | Open |
| P0-12 | Medium | `test_suite.py` originally removed and overwrote fixed relative paths such as `test_trading.db`, `test_import.db`, and `test_export.csv`. | The suite now stores its database and CSV files inside `tempfile.TemporaryDirectory()`, and a `unittest` wrapper runs it in CI. Regression suite passes on Python 3.11 and 3.12. | Fixed on audit branch; not merged |
| P0-13 | Medium | `requirements.txt` uses minimum version constraints only; no lockfile is present. | Define a tested dependency strategy and keep CI checks stable as the baseline becomes reproducible. | Open |
| P0-14 | Medium | `data.py` CSV import and `web_app.py` upload paths need deeper validation review. | Test malformed rows, duplicate IDs, invalid numeric values, oversized/mislabelled uploads, and spreadsheet formula payloads before changing behavior. | Open |
| P0-15 | Medium | `calculators.py` initialized the realized equity curve using the first trade's entry time even though trades are ordered by exit time; non-positive starting balances were also accepted. | Order realized equity points by close time, anchor the initial point at the first close, and reject non-positive initial balances. Add regression tests for peak-to-trough drawdown and chronological ordering. | Fixed on audit branch; not merged |

## Baseline checks

| Check | Result |
|---|---|
| Repository root inventory | Completed |
| Recent branch/commit inventory | Completed |
| GitHub Actions workflow inventory | Workflow added on audit branch; safe unit tests passed on Python 3.11 and 3.12 |
| Static inspection of key application/test modules | Initial pass completed |
| Run legacy `test_suite.py` | Executed through the safe `unittest` wrapper in CI after moving its database/CSV artifacts into a temporary directory; passed on Python 3.11 and 3.12 |
| Launch web app and exercise API | **Not run** |
| MT5 integration test | **Not run; requires supported local MT5 terminal/account environment** |
| Dependency/security scan | **Not run** |

## Safe baseline tests added

Added `tests/test_models_baseline.py`, `tests/test_cli_web_command.py`, `tests/test_sample_data_safety.py`, and `tests/test_financial_calculations.py`. Coverage includes trade-model P&L behavior, CLI web launch behavior, safe demo seeding, Sharpe/Sortino assumptions, exit-date period filtering, entry-date cohort filtering, invalid date-basis rejection, realized-equity chronology, peak-to-trough drawdown, and initial-balance validation. These tests use mocks and in-memory objects and do not touch the journal database. The expanded suite, including sample-data safety tests, passed on Python 3.11 and 3.12 in GitHub Actions. Run locally with `python -m unittest discover -s tests -v`. This remains a regression suite, not full application validation.

## Phase 0 execution plan

1. Reproduce the baseline in a controlled environment without connecting to a live trading account.
2. **Completed:** Refactor the legacy suite to use temporary directories and include it in CI.
3. Expand safe tests for calculations, service/database behavior, CSV validation, and date-period semantics.
4. Confirm each finding against exact code paths and assign severity based on realistic exposure and impact.
5. Record test commands, environment details, outputs, and known limitations.
6. Use the audit branch for isolated changes; do not merge fixes into `main` until tests and diff review pass.

## Acceptance criteria

- The baseline can be reproduced from a documented setup.
- Tests cannot overwrite or delete the user's real journal database.
- Each high-priority finding has evidence, a remediation plan, and a regression test or documented reason why automated testing is not possible.
- No finding is marked fixed without verification.
