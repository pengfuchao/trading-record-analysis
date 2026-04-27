# Project State — 2026-04-28

## Session Summary

Continuation of the 2026-04-27 hardening roadmap.
Predecessor docs:
- `project-state-2026-04-27.md` — original roadmap
- `project-state-2026-04-27-r2-r4.md` — R2–R4 completion
- `project-state-2026-04-27-r5.md` — R5 + R6 completion

Commits this period (local, GitHub push pending — expired token in remote URL):

| Commit | Description |
|---|---|
| `14dfaf6` | feat(ops): R5 — persist FTMO dedup + scheduler cooldown across restarts |
| `97465c4` | docs: project state 2026-04-27 R2–R4 handoff |
| `ec656cc` | feat(r6): MT5 password env var presence indicator |
| `9f5d17e` | docs: mark R6 done in project-state handoff |
| `59bdaad` | fix: MT5 sync must not null-overwrite enriched SL/TP/R |

**Pending action:** update GitHub remote URL with a fresh token and `git push origin main` to sync all local commits.

---

## Completed Items

### R1 — Backup Discipline (manual, fully verified by operator)

| Step | Done |
|---|---|
| `backup.sh` / `backup.ps1` ran and produced `.sql` in `backups/` | Yes |
| Backup copied off-host (OneDrive or external drive) | Yes |
| Daily automated backup configured (Task Scheduler / cron) | Yes |
| Throwaway DB `trading_journal_restore_test` created | Yes |
| Backup restored into test DB | Yes |
| Tables and row counts verified | Yes |

R1 is closed. Do not raise again.

---

### R2–R4 — Ops Hardening (code, done)

- **R2 SL/TP doc sweep:** README, RPD, import page, MT5 sync page all updated with the two-path SL/TP playbook
- **R3 reset-data guardrail:** `reset-data.sh` and `reset-data.ps1` added — auto-backup before wipe, confirmation prompt
- **R4 single-worker enforcement:** `_lifespan` in `app.py` logs WARN when `UVICORN_WORKERS != "1"`

---

### R5 — Persist FTMO + Scheduler Cooldown State (code, done)

**Problem:** Two runtime state dicts lived only in memory:
- `_error_suppress_until` in `mt5_scheduler.py` — error alert cooldown timestamp
- `_last_ftmo_status` in `telegram_notifier.py` — FTMO status dedup

**Solution:**
- Migration 011: `runtime_state(scope TEXT, kind TEXT, value_json TEXT, updated_at DATETIME)` with composite PK `(scope, kind)`
- `src/main/python/services/runtime_state.py`: `get_state`, `set_state`, `delete_state` stateless helpers
- `mt5_scheduler.py`: lazy-load + persist cooldown; clear on sync success
- `telegram_notifier.py`: lazy-load + persist FTMO last-status
- Lazy-load pattern: state loaded from DB on first call per account, cached in memory
- DB failures are non-fatal (log, fall back to empty state)
- 20 integration tests in `test_runtime_state.py`

**Run after any clean DB start:** `alembic upgrade head` (to apply migration 011).

---

### R6 — MT5 Password Env Var Presence Indicator (code, done)

**Problem:** MT5 sync page showed the required env var name but could not tell the operator whether the backend process could see that env var. Silent setup failure: sync skips with no visible feedback.

**Solution:**
- `GET /accounts/{id}/mt5-config/password-status` → `{env_var_name: str, present: bool}`
- Account must exist (`require_account`), no config required
- Password value is never read into the response — presence check only
- Frontend `/mt5-sync`: green `✓ Present` / red `✗ Not found` badge in the password note block
- Badge refreshes automatically after config save
- 8 route tests in `test_mt5_password_status.py`

---

### Data Integrity Bug Fix — MT5 Sync Must Not Null-Overwrite Enriched SL/TP

**Severity:** High — silent data loss on every MT5 sync for enriched trades.

**Observed symptom:** After running SL/TP enrichment (CSV or backfill), `stop_loss` / `take_profit` values are correctly populated. After the next MT5 sync, they disappear — reset to null/blank.

#### Root Cause (exact code path)

`sync_account()` calls:
```python
self._trade_repo.save_batch_import(trades, import_run_id=run_id, duplicate_strategy="update_broker")
```

`save_batch_import` with `update_broker`:
```python
new_orm = trade_to_orm(trade, import_run_id=import_run_id)
for field in _BROKER_FIELDS:
    setattr(orm_obj, field, getattr(new_orm, field, None))
```

`_BROKER_FIELDS` included `"stop_loss"`, `"take_profit"`, `"actual_r_multiple"`.

MT5 sync fetches orders only within a rolling window (default 7 days). For trades whose matching orders fall outside that window, `reconstruct_positions` sets `pos["sl"] = None` and `pos["tp"] = None`. `_normalize_positions` produces a `Trade` object with `stop_loss=None` and `take_profit=None`. The `update_broker` loop then writes those nulls directly onto the DB row, erasing any previously enriched value.

#### Fix Implemented

In `src/main/python/services/trade_repository.py`:

1. Added constant after `_BROKER_FIELDS`:
```python
_SL_TP_PROTECTED_FIELDS = frozenset(("stop_loss", "take_profit", "actual_r_multiple"))
```

2. Changed the `update_broker` field assignment loop:
```python
for field in _BROKER_FIELDS:
    incoming = getattr(new_orm, field, None)
    if (
        field in _SL_TP_PROTECTED_FIELDS
        and incoming is None
        and getattr(orm_obj, field) is not None
    ):
        continue
    setattr(orm_obj, field, incoming)
```

#### Merge Policy After Fix

| Scenario | Behavior |
|---|---|
| Incoming SL/TP is None, existing is None | Still None (no change) |
| Incoming SL/TP is None, existing is non-null | **Skip** — existing value preserved |
| Incoming SL/TP is non-null, existing is None | Write incoming (fill) |
| Incoming SL/TP is non-null, existing is non-null | Write incoming (update) |

The guard `incoming is None` ensures that when MT5 genuinely provides a real SL/TP value, it still updates the DB. The protection only fires when the sync window missed the order.

#### Invariant to Preserve Going Forward

**`update_broker` must never use incoming `None` to overwrite a non-null `stop_loss`, `take_profit`, or `actual_r_multiple`.** The source of truth for these fields is the enrichment/backfill path; the sync path should only fill them when it has real data.

If `_BROKER_FIELDS` is ever extended, do not add SL/TP adjacent fields without checking whether they should also appear in `_SL_TP_PROTECTED_FIELDS`.

#### Regression Tests Added

7 new tests in `TestSaveBatchImportUpdateBroker` in `test_repositories.py`:
- `test_existing_sl_not_overwritten_by_null`
- `test_existing_tp_not_overwritten_by_null`
- `test_existing_r_not_cleared_when_sync_sl_null`
- `test_sl_tp_filled_when_existing_is_null`
- `test_sl_tp_updated_when_sync_brings_real_values`
- `test_other_broker_fields_still_updated`
- `test_enrich_then_sync_sequence` ← full reproduction of the observed bug sequence

---

## Current Test Counts

| Suite | Count |
|---|---|
| Before this session | 553 passed |
| After R5 (20 new) | 573 passed |
| After R6 (8 new) | 581 passed |
| After SL/TP fix (7 new) | 588 passed |
| Postgres smoke errors (pre-existing, require live DB) | 9 errors (unchanged) |

All non-Postgres tests pass.

---

## Roadmap Status

| Item | Status | Notes |
|---|---|---|
| R1 — Backup discipline | **DONE (manual)** | Scheduled + off-host + restore drill verified |
| R2 — SL/TP doc sweep | **Done** | README, RPD, import page, MT5 sync page |
| R3 — reset-data guardrail | **Done** | reset-data.sh + reset-data.ps1 |
| R4 — single-worker enforcement | **Done** | _lifespan WARN log |
| R5 — Persist FTMO/scheduler cooldown | **Done** | runtime_state table, migration 011 |
| R6 — MT5 password env var presence indicator | **Done** | GET .../mt5-config/password-status + UI badge |
| SL/TP null-overwrite bug | **Fixed** | _SL_TP_PROTECTED_FIELDS guard in save_batch_import |
| R7 — SL/TP backfill UX | Partially done | UI panel added; async progress only if painful |
| R8 — Real-data Playwright E2E | Deferred | Mocked tests still catching regressions |

---

## Recommended Manual Validations (in priority order)

### 1. Apply migration 011 (if not already applied)
```bash
alembic upgrade head
```
Verify `runtime_state` table exists in the running Postgres DB.

### 2. Test SL/TP null-overwrite fix (highest priority — data integrity)
Sequence to run manually in the UI:
1. Open the Trade Log — find a recent MT5 trade with `stop_loss` populated
2. Check its SL/TP values before the test
3. Trigger a manual MT5 sync (`POST /accounts/{id}/mt5-sync`)
4. Open the same trade again — verify `stop_loss` and `take_profit` did not change
5. If previously enriched trades had their SL/TP wiped by a past sync, re-run SL/TP backfill now

### 3. Test FTMO status alert dedup survives restart (R5)
1. Note the current FTMO status in the UI
2. Restart the backend (`docker compose restart backend` or restart the local uvicorn)
3. Verify no duplicate FTMO alert fires in Telegram immediately after restart (status unchanged → no alert)

### 4. Test MT5 scheduler error cooldown survives restart (R5)
1. Deliberately cause a sync error (disable MT5 terminal, or wrong password)
2. Verify Telegram receives one error alert
3. Restart the backend
4. Wait for the next scheduled poll — verify Telegram does NOT receive a duplicate alert (cooldown should be restored from DB)

### 5. Test MT5 password presence badge (R6)
1. Open `/mt5-sync` page
2. Verify the password note block shows `✓ Present` if the env var is set, `✗ Not found` if not
3. Temporarily rename the env var, restart backend, reload page — badge should turn red

### 6. Enrich SL/TP → sync → verify SL/TP survives
1. Import a CSV with SL/TP for trades that currently lack them
2. Verify stop_loss / take_profit appear in Trade Log
3. Run MT5 sync
4. Verify the values are still present after sync

---

## Recommended Next Roadmap Item for Tomorrow

All high-urgency items (R1–R6 + SL/TP integrity) are done. Good candidates:

**A. Manual validation first** (above list) — do this before any code.

**B. R7 — SL/TP backfill async UX** (code, only if the wait is painful)
The backfill endpoint can take several minutes for large trade histories. The UI currently says "may take several minutes — do not click twice." If the operator finds this confusing or unreliable, add async status (task ID + polling). Low urgency unless the user reports problems.

**C. R8 — Real-data Playwright E2E** (code, lower priority)
Playwright tests are mocked only. Real-data coverage would catch API contract drift. No regression has slipped through yet; defer until mocked tests fail to catch something real.

**D. Any new issues** observed during manual validation above — fix those first.
