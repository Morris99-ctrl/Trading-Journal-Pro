# Phase 0: Baseline Audit

**Repository:** `Morris99-ctrl/Trading-Journal-Pro`  
**Baseline branch:** `main`  
**Audit branch:** `phase-0/baseline-audit`  
**Audit date:** 2026-10-29  
**Status:** Static baseline started; runtime test execution is still pending.

## Scope and limitations

This is an initial repository inventory and static inspection, not a complete security audit. Source files were inspected through GitHub. The application and test suite have **not** been executed in a local Python environment during this pass. Findings below must be reproduced and regression-tested before they are marked fixed.

## Repository inventory

Root modules/files include `main.py`, `web_app.py`, `ui.py`, `cli.py`, `models.py`, `services.py`, `data.py`, `calculators.py`, `analytics.py`, `mt5_service.py`, `test_suite.py`, `requirements.txt`, `README.md`, and `Start_Journal.bat`, plus `templates/`, `static/`, and `screenshots/`.

- Only `main` was present at the time of inventory.
- The recent commit listing returned one initial commit.
- No `.github/workflows/` directory or GitHub Actions runs were found.
- Dependencies are specified with minimum versions, not a lockfile or fully pinned requirements.
- `.gitignore` excludes Python caches, virtual environments, environment files, logs, SQLite/database files, and `instance/`.

## Initial findings register

| ID | Priority | Evidence | Risk / next action | Status |
|---|---|---|---|---|
| P0-01 | High | `web_app.py` sets `app.config["SECRET_KEY"]` to a hard-coded literal (line 22). | Move secret configuration to environment/configuration; fail safely when production secret is missing; inspect history and rotate if it was used outside local development. | Open |
| P0-02 | High | `templates/index.html` builds table/detail/modal markup with `innerHTML`, including trade-derived values (e.g. around lines 802 and 951). | Trace all interpolated values and prove exploitability; render user data with safe DOM APIs/textContent or contextual escaping; add XSS regression tests. | Open |
| P0-03 | High | `web_app.py` exposes mutating API routes for trades and MT5 sync; no authentication/authorization was visible in the inspected route handlers. `main.py` binds to loopback by default. | Document intended deployment. Keep local-only deployment explicit; add appropriate access control and CSRF protection if browser sessions or remote access are supported. | Open |
| P0-04 | High | `main.py` seeds sample trades whenever the configured database has no trades. | Prevent demo records from being silently inserted into a real journal; make demo seeding an explicit opt-in and test empty-database startup. | Open |
| P0-05 | High | `README.md` includes a concrete-looking MT5 server/account label: `FBS-Real (#42920594)`. | Confirm whether this is synthetic. Remove or replace with clearly fictional example data if it identifies a real account. | Open |
| P0-06 | High | `data.py` backup path uses `shutil.copy2` for the database (around line 126). | Verify database connection/transaction behavior; use SQLite's online backup API and test restore integrity. | Open |
| P0-07 | High | `calculators.py` computes Sharpe/Sortino from a list of trade percentage returns (around lines 158-172; aggregation around 237-240). | Review return definitions and annualization assumptions. Do not present trade-level ratios as annualized portfolio risk metrics without a defensible sampling model. | Open |
| P0-08 | High | `data.py` filters `get_all_trades` date ranges on `entry_time` (around lines 218-246). | Define entry-cohort vs. realized-period reporting and test trades entered outside but closed inside a requested period. | Open |
| P0-09 | High | `mt5_service.py` groups deals by `position_id` and selects entry/exit deals (around lines 126-192). | Test partial exits, multiple entries, reversals, commissions, swaps, and broker-reported realized P&L against imported journal values. | Open |
| P0-10 | Medium | `cli.py` imports `sys` but the `web` command calls `os.system` (near the start of the command loop); no `os` import appears in the inspected imports. | Reproduce the CLI web-launch path and fix with a regression test. | Open |
| P0-11 | Medium | API handlers in `web_app.py` return exception strings to clients in several error paths. | Return stable generic errors to clients and log details server-side without leaking secrets or internal state. | Open |
| P0-12 | Medium | `test_suite.py` is a custom assert-based runner that writes fixed filenames such as `test_trading.db` and deletes those files. | Run only in an isolated workspace initially; migrate to a standard test runner with temporary directories/fixtures and ensure test cleanup cannot touch user data. | Open |
| P0-13 | Medium | `requirements.txt` uses minimum version constraints only; no CI workflow was found. | Add a tested dependency strategy and CI checks after the baseline environment is reproducible. | Open |
| P0-14 | Medium | `data.py` CSV import and `web_app.py` upload paths need deeper validation review. | Test malformed rows, duplicate IDs, invalid numeric values, oversized/mislabelled uploads, and spreadsheet formula payloads before changing behavior. | Open |

## Baseline checks

| Check | Result |
|---|---|
| Repository root inventory | Completed |
| Recent branch/commit inventory | Completed |
| GitHub Actions workflow inventory | No workflows found |
| Static inspection of key application/test modules | Initial pass completed |
| Run existing test suite | **Not run in this environment** |
| Launch web app and exercise API | **Not run** |
| MT5 integration test | **Not run; requires supported local MT5 terminal/account environment** |
| Dependency/security scan | **Not run** |

## Phase 0 execution plan

1. Obtain a reproducible local test environment without connecting to a live trading account.
2. Run the existing suite in an isolated temporary workspace and record failures and side effects.
3. Add a standard test runner and deterministic fixtures; preserve current behavior in characterization tests where appropriate.
4. Confirm each finding against exact code paths and assign severity based on realistic exposure and impact.
5. Record test commands, environment details, outputs, and known limitations.
6. Use the audit branch for isolated changes; do not merge fixes into `main` until tests and diff review pass.

## Acceptance criteria

- The baseline can be reproduced from a documented setup.
- Tests cannot overwrite or delete the user's real journal database.
- Each high-priority finding has evidence, a remediation plan, and a regression test or documented reason why automated testing is not possible.
- No finding is marked fixed without verification.
