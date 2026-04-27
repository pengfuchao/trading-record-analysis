# Project State — 2026-04-27 (R5 session)

## R1 Backup Discipline — MANUALLY COMPLETED AND VERIFIED

R1 is now done. The user confirmed all of the following:

| Step | Verified |
|---|---|
| `backup.sh` (or `backup.ps1`) runs successfully and produces a `.sql` file in `backups/` | Yes |
| The `.sql` backup file was copied off-host (OneDrive or external drive) | Yes |
| Daily automated backup is configured via Task Scheduler (Windows) or cron (WSL) | Yes |
| A throwaway database `trading_journal_restore_test` was created | Yes |
| The backup was restored into the test DB | Yes |
| Restored tables and row counts were verified as reasonable | Yes |

**R1 is no longer open. Do not list it as a gap in future sessions.**

The project now has:
- Automated daily backup (scheduled)
- Off-host copy discipline
- A verified restore path

---

## Session Summary

Implemented roadmap item R5 from the refreshed roadmap.
Predecessor commits: `b4f208f` (R2–R4), `97465c4` (state doc).

---

## R5 — Persist FTMO + Scheduler Cooldown State (DONE)

### Problem
Two runtime state dicts lived only in memory:
1. `_error_suppress_until` in `mt5_scheduler.py` — per-account timestamp after which the next
   error alert is re-allowed. Cleared on success; set 4 hours into the future on first error alert.
2. `_last_ftmo_status` in `telegram_notifier.py` — per-account last-notified FTMO status string.
   Used to suppress duplicate Telegram alerts when status hasn't changed.

On every backend restart, both dicts reset to empty. This caused:
- MT5 scheduler error alerts re-firing immediately after restart (cooldown lost)
- FTMO status alerts re-firing after restart even if nothing changed

### Solution: `runtime_state` table (migration 011)

**Schema:** `(scope TEXT, kind TEXT, value_json TEXT, updated_at DATETIME)` with composite PK `(scope, kind)`.
- `scope` = `account_id` (or `"_global"` for non-account state)
- `kind` = `"scheduler_error_cooldown"` or `"ftmo_last_status"`
- `value_json` = JSON-serialized value (ISO datetime string for cooldown; status string for FTMO)

**Service layer:** `src/main/python/services/runtime_state.py`
- `get_state(session, scope, kind) -> Optional[Any]`
- `set_state(session, scope, kind, value) -> None`
- `delete_state(session, scope, kind) -> None`
All stateless; caller owns the session via `get_session()`.

**Lazy-load pattern:**
- Module-level `_state_loaded: Set[str]` (scheduler) / `self._ftmo_loaded: set` (notifier) tracks which accounts have had their state loaded from DB.
- On first call per account, state is loaded from DB and cached in the existing in-memory dict.
- On state changes, DB is written immediately.
- DB failures (read or write) are non-fatal: logged at WARN/DEBUG, behavior falls back to current defaults.

### Files changed

| File | Change |
|---|---|
| `alembic/versions/011_runtime_state.py` | New migration: creates `runtime_state` table |
| `src/main/python/models/db_models.py` | New `RuntimeStateModel` ORM class |
| `src/main/python/services/runtime_state.py` | New service: `get_state`, `set_state`, `delete_state` |
| `src/main/python/services/mt5_scheduler.py` | Lazy-load + persist scheduler cooldown; clear on success |
| `src/main/python/services/telegram_notifier.py` | Lazy-load + persist FTMO last-status |
| `src/test/integration/test_runtime_state.py` | New: service layer tests + simulated restart tests |

### Behavior after this change

| Scenario | Before | After |
|---|---|---|
| Backend restarts during active 4h cooldown | Cooldown lost; next poll re-alerts Telegram | Cooldown restored from DB; alert suppressed |
| Backend restarts; FTMO status unchanged | Alert re-fires (status was UNKNOWN before restart) | Status restored from DB; no alert if status unchanged |
| DB unavailable at startup | N/A | Log WARN; start with empty state (same as before) |
| FTMO status actually changes | Alert fires | Alert fires (unchanged) |
| First sync error after success | Alert fires + cooldown set | Alert fires + cooldown set + written to DB |
| Sync succeeds after error | Cooldown cleared (memory) | Cooldown cleared (memory + DB) |

### What stays in memory (correct)

- `_running: Set[str]` — in-process sync lock. Must reset on restart (mid-sync processes are dead after restart).

---

## Updated Roadmap

| Item | Status | Notes |
|---|---|---|
| R1 — Backup discipline | **DONE (manual)** | Scheduled + off-host + restore drill verified |
| R2 — SL/TP doc sweep | Done | README, RPD, import page, MT5 sync page |
| R3 — reset-data guardrail | Done | reset-data.sh + reset-data.ps1 |
| R4 — single-worker enforcement | Done | _lifespan WARN log |
| R5 — Persist FTMO/scheduler cooldown | **Done** | runtime_state table, migration 011 |
| R6 — MT5 password env var presence indicator | **Done** | GET .../mt5-config/password-status + UI ✓/✗ badge; commit ec656cc |
| R7 — SL/TP backfill UX | Partially done | UI panel added; async only if user feels pain |
| R8 — Real-data Playwright E2E | Deferred | No regression has slipped through mocked tests yet |

**Next session:** R7 or R8, or new items raised by the operator.
