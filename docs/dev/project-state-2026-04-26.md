# Project State — 2026-04-26

## Summary

Phases 9–11 are complete. The project is now at **9/10 maturity**:  
all features implemented, test coverage solid (backend + Postgres + E2E frontend),  
ops hardened (backup/restore scripts, CI covering real Postgres). The remaining gaps are  
quality/ops polish, not feature gaps.

---

## What Was Completed in Phases 9–11

### Phase 9 — MT5 Scheduler Resilience

| Fix | Detail |
|---|---|
| Alert cooldown | Repeated scheduled failures suppressed for 4h after first Telegram alert; cleared on success |
| Polling jitter | New jobs start after 0–30s random delay to prevent lockstep polling at startup |
| `lookback_days` configurable | DB column (migration 010), Pydantic field, wired through scheduler kwargs |
| Startup advisory log | `MT5PollingScheduler.start()` now logs explicit `--workers 1` advisory |

Files: `services/mt5_scheduler.py`, `models/db_models.py`, `api/schemas/mt5_sync.py`, `api/routes/mt5_sync.py`, `alembic/versions/010_mt5_lookback_days.py`

### Phase 10 — Export + Ops Closure

| Fix | Detail |
|---|---|
| `lookback_days` in MT5 config UI | Form field in `/mt5-sync` between poll interval and enabled toggle |
| `GET /accounts/{id}/trades/export/csv` | All matching trades, same filters as list endpoint, no pagination cap |
| Export CSV button on Trade Log | Filter-aware `<a download>` in Trade Log header |
| `backup.ps1` + `backup.sh` | `docker compose exec -T db pg_dump` → timestamped file in `backups/` |

Files: `frontend/app/mt5-sync/page.tsx`, `frontend/app/trades/page.tsx`, `frontend/lib/api.ts`, `src/main/python/api/routes/trades.py`, `src/main/python/services/trade_repository.py`, `backup.ps1`, `backup.sh`

### Phase 11 — CI Hardening + Restore Scripts

| Fix | Detail |
|---|---|
| Postgres 15 CI job | `postgres-migration-check`: spins up Postgres 15, runs `alembic upgrade head`, then unit tests + 9 smoke tests |
| `test_postgres_smoke.py` | 9 tests: all 11 tables exist, `lookback_days` server_default=7, ORM CRUD for Account/Trade/MT5Config/Setup |
| Playwright E2E | 8 smoke tests with mocked API; `frontend/playwright.config.ts` + `frontend/e2e/smoke.spec.ts` |
| `frontend-e2e` CI job | Installs Playwright Chromium, starts Next.js dev server, runs tests |
| `restore.ps1` + `restore.sh` | Symmetric with backup scripts; requires typed "yes" confirmation; prints restart hint |
| CI fixes | `alembic upgrade head` (not `python -m alembic`); `setup_id` in smoke test |

Files: `.github/workflows/ci.yml`, `src/test/integration/test_postgres_smoke.py`, `frontend/playwright.config.ts`, `frontend/e2e/smoke.spec.ts`, `frontend/package.json`, `restore.ps1`, `restore.sh`

---

## Current Test Coverage

| Layer | Count | Notes |
|---|---|---|
| Unit (core logic) | ~435 tests | metrics, analytics, parsers, validators, converters |
| Integration (repositories) | ~30 tests | full CRUD for accounts and trades via real SQLite |
| Integration (import pipeline) | ~15 tests | CSV parse + output writer |
| Integration (MT5 sync) | ~14 tests | connector/sync logic via mocked MT5Connector |
| HTTP routes | 59 tests | 8 router groups via TestClient + SQLite in-memory |
| **Postgres migration + ORM** | **9 tests (skipped in SQLite)** | schema check + CRUD on real Postgres 15 |
| **Frontend E2E** | **8 tests** | Playwright, mocked API, Chromium |
| **Total backend (SQLite run)** | **494 passed, 9 skipped** | |

---

## Current CI Jobs (all green after Phase 11 fixes)

| Job | Trigger | What it catches |
|---|---|---|
| `backend-tests` | push / PR | Unit + integration regressions (SQLite) |
| `postgres-migration-check` | push / PR | Migration chain breaks, Postgres ORM drift |
| `frontend-typecheck` | push / PR | TypeScript type errors |
| `frontend-e2e` | push / PR | Frontend page load crashes, broken navigation |

**Known CI fix applied:** `alembic upgrade head` (binary) instead of `python -m alembic upgrade head` — the local `alembic/` migration directory shadowed the installed package under `python -m`.

---

## What Remains Rough

| Gap | Severity | Notes |
|---|---|---|
| `CORS_ORIGINS` hardcoded in compose | Medium | Blocks remote deploys; 5-min fix (`${CORS_ORIGINS:-...}`) |
| Telegram webhook untested at HTTP layer | Medium | chat_id guard regression is invisible; pattern exists in `test_routes.py` |
| Frontend E2E tests use mocked API only | Low | No real-data UI integration coverage |
| No automated backup schedule | Low | Scripts exist; schedule via Task Scheduler/cron |
| Single-worker assumption | Low — documented | `--workers 1` in `docker-entrypoint.sh`; advisory logged at startup |

---

## Operating Modes (Unchanged)

| Mode | When | Frontend | Backend | Database |
|---|---|---|---|---|
| **Docker full stack** | Normal journaling | Docker :3000 | Docker :8000 | Docker :5432 |
| **Local Windows MT5 sync** | Live MT5 sync | Docker :3000 | Native Windows :8000 | Docker :5432 |

Use `start-local-backend.ps1` for MT5 sync mode.  
MT5 passwords: `MT5_<ACCOUNT_ID_UPPER_UNDERSCORED>_PASSWORD` env var only, never in DB.

### Alembic migration command (Mode 2 note)

Use `alembic upgrade head` (binary), **not** `python -m alembic upgrade head`.  
The local `alembic/` migration directory shadows the installed package when Python's module path includes the repo root. The binary bypasses this entirely.

---

## Next Recommended Direction

No specific phase assigned. In order of value-to-effort:

1. **CORS fix** — one compose line: `CORS_ORIGINS: ${CORS_ORIGINS:-http://localhost:3000}`. Unblocks remote deploys.
2. **Telegram webhook tests** — add `telegram_router` to `test_routes.py` app fixture; mock `requests.post`; test chat_id guard. Closes the last untested route group.
3. **Empty-state onboarding** — `/trades`, `/plans`, `/daily`, `/coaching` pages: show a "Create an account first" or "No data yet" message when `accountId` is null. Dashboard already has this (Phase 7 `CreateAccountCard`).

---

## Migration Chain

010 migrations (001–010), all intact. Latest: `010_mt5_lookback_days.py` adds `lookback_days INTEGER NOT NULL DEFAULT 7` to `mt5_sync_configs`.
