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
| P0-07 | High | `calculators.py` computes Sharpe/Sortino from a list of trade percentage returns (around lines 158-172; aggregation around 237-240). | Review return definitions and annualization assumptions. Do not present trade-level ratios as annualized portfolio risk metrics without a defensible sampling model. | Open |
| P0-08 | High | `data.py` filters `get_all_trades` date ranges on `entry_time` (around lines 218-246). | Define entry-cohort vs. realized-period reporting and test trades entered outside but closed inside a requested period. | Open |
| P0-09 | High | `mt5_service.py` groups deals by `position_id` and selects entry/exit deals (around lines 126-192). | Test partial exits, multiple entries, reversals, commissions, swaps, and broker-reported realized P&L against imported journal values. | Open |
| P0-10 | Medium | `cli.py` originally called `os.system` in the `web` command without importing `os`. | Added `import os` and a regression test for the `web` command. Verify via CI; broader CLI behavior still needs testing. | Fixed in audit branch; expanded CI suite passed |
| P0-11 | Medium | API handlers in `web_app.py` return exception strings to clients in several error paths. | Return stable generic errors to clients and log details server-side without leaking secrets or internal state. | Open |
| P0-12 | Medium | `test_suite.py` removes `test_trading.db` and `test_import.db` if present, writes `test_export.csv`, and unconditionally deletes those same paths at the end. These are fixed relative paths in the current working directory. | Do not run from a user's project/data directory. Migrate database and export paths to a `tempfile.TemporaryDirectory()` and use a standard test runner. | Open |
| P0-13 | Medium | `requirements.txt` uses minimum version constraints only; no lockfile is present. | Define a tested dependency strategy and keep CI checks stable as the baseline becomes reproducible. | Open |
| P0-14 | Medium | `data.py` CSV import and `web_app.py` upload paths need deeper validation review. | Test malformed rows, duplicate IDs, invalid numeric values, oversized/mislabelled uploads, and spreadsheet formula payloads before changing behavior. | Open |

## Baseline checks

| Check | Result |
|---|---|
| Repository root inventory | Completed |
| Recent branch/commit inventory | Completed |
| GitHub Actions workflow inventory | Workflow added on audit branch; safe unit tests passed on Python 3.11 and 3.12 |
| Static inspection of key application/test modules | Initial pass completed |
| Run legacy `test_suite.py` | **Not run**: it deletes fixed-name files in the working directory; inspect and isolate before execution |
| Launch web app and exercise API | **Not run** |
| MT5 integration test | **Not run; requires supported local MT5 terminal/account environment** |
| Dependency/security scan | **Not run** |

## Safe baseline tests added

Added `tests/test_models_baseline.py`, `tests/test_cli_web_command.py`, and `tests/test_sample_data_safety.py`. Coverage includes trade-model P&L behavior, CLI web launch behavior, no automatic sample seeding, explicit `--demo` seeding for an empty journal, and refusal to mix demo data into an existing journal. These tests use mocks and in-memory objects and do not touch the journal database. The expanded suite, including sample-data safety tests, passed on Python 3.11 and 3.12 in GitHub Actions. Run locally with `python -m unittest discover -s tests -v`. This remains a regression suite, not full application validation.

## Phase 0 execution plan

1. Reproduce the baseline in a controlled environment without connecting to a live trading account.
2. Refactor the legacy suite to use temporary directories before executing it.
3. Expand safe tests for calculations, service/database behavior, CSV validation, and date-period semantics.
4. Confirm each finding against exact code paths and assign severity based on realistic exposure and impact.
5. Record test commands, environment details, outputs, and known limitations.
6. Use the audit branch for isolated changes; do not merge fixes into `main` until tests and diff review pass.

## Acceptance criteria

- The baseline can be reproduced from a documented setup.
- Tests cannot overwrite or delete the user's real journal database.
- Each high-priority finding has evidence, a remediation plan, and a regression test or documented reason why automated testing is not possible.
- No finding is marked fixed without verification.
