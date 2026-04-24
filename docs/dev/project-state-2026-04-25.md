# Project State — 2026-04-25

## What Was Completed in Phase 7 (Ops Hardening + Onboarding Fix)

| Fix | File(s) |
|---|---|
| Replace 4 `alert()` calls with inline red banners | `frontend/app/daily/page.tsx` |
| Add `CreateAccountCard` onboarding form on dashboard empty state | `frontend/app/dashboard/page.tsx`, `frontend/lib/api.ts` |
| Fix `datetime.utcnow()` deprecation → `datetime.now(timezone.utc)` | `src/main/python/models/db_models.py`, `services/mt5_scheduler.py` |
| Add `start-local-backend.ps1` (PowerShell MT5 sync mode guide) | `start-local-backend.ps1` |
| Add `start-local-backend.sh` (WSL/Linux dev mode guide) | `start-local-backend.sh` |

### Detail

**daily/page.tsx — `alert()` replacement:**
- `PlanCard.handleDelete` → `deleteError` state + inline red banner below card header
- `ReviewCard.handleDelete` → same pattern
- `NewPlanForm.handleSubmit` → `createError` state + inline error before buttons
- `NewReviewForm.handleSubmit` → same pattern

**dashboard empty state:**
- When `accounts.length === 0` and loading is done: shows `CreateAccountCard` with a full inline account creation form (account_id, broker, platform, starting_balance, prop_firm, challenge_phase)
- `api.createAccount()` added to `frontend/lib/api.ts`
- On success, SWR's `globalMutate("accounts")` refreshes the account list

**datetime deprecation:**
- `db_models.py`: added `_utcnow()` helper function using `datetime.now(timezone.utc)`; all `default=datetime.utcnow` and `onupdate=datetime.utcnow` replaced with `default=_utcnow` / `onupdate=_utcnow`
- `mt5_scheduler.py`: `datetime.utcnow()` → `datetime.now(timezone.utc)`, import updated

**Startup scripts:**
- `start-local-backend.ps1`: stops Docker `backend` container, activates venv, sets PYTHONPATH, runs migrations, starts uvicorn
- `start-local-backend.sh`: same for WSL/bash; uses `exec` so Ctrl+C cleanly stops the process

### Deferred from Phase 7

- `pg_dump` backup one-liner (low-impact, doc-only) — still missing
- `CORS_ORIGINS` hardcoded in docker-compose — requires compose restructuring
- CI SQLite-only (Postgres-specific issues can pass CI) — Phase 8+

## What Remains Rough

1. **Zero HTTP route tests** — API surface has no regression protection at HTTP layer
2. **No pg_dump backup story** — `docker compose down -v` destroys data; no documented recovery
3. **`CORS_ORIGINS` hardcoded in compose** — can't override via `.env` for remote deploys
4. **CI SQLite-only** — Postgres-specific migration issues can pass CI silently

## Two Operating Modes (Unchanged)

| Mode | When | Frontend | Backend | Database |
|---|---|---|---|---|
| **Docker full stack** | Normal journaling | Docker :3000 | Docker :8000 | Docker :5432 |
| **Local Windows MT5 sync** | Live MT5 sync | Docker :3000 | Native Windows :8000 | Docker :5432 |

Use `start-local-backend.ps1` for MT5 sync mode. The `db` service publishes `5432:5432` to the host.

MT5 passwords are never in the DB — always from env vars: `MT5_<ACCOUNT_ID_UPPER_UNDERSCORED>_PASSWORD`.

## Pending GitHub Push

10 commits (Phases 6+7) are queued locally but blocked by a PAT scope issue: the PAT needs `workflow` scope to push because a `.github/workflows/ci.yml` file exists. Grant `workflow` scope at GitHub → Settings → Personal Access Tokens, then `git push origin main`.

## Next Phase: Phase 8 — HTTP Route Test Coverage

**Scope:**
- Add pytest-based HTTP integration tests hitting real FastAPI routes (using `httpx.AsyncClient` or `TestClient`)
- Priority routes: account CRUD, trade import preview/confirm, analytics, plan adherence
- Run against SQLite in-memory (consistent with existing integration tests)
- Goal: catch regressions at the API boundary before they reach the frontend

**After Phase 8:** Phase 9 is MT5 scheduler resilience (alert cooldown, lookback_days config in UI, jitter).
