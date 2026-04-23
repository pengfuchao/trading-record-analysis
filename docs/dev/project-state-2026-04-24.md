# Project State — 2026-04-24

## What Was Completed Recently (Phases 1–6)

All six build phases are done. The project is a working, end-to-end trading journal with:
- Full trade workflow (log → detail → journal enrichment → linked plan)
- Trade plans, daily plans, daily reviews with adherence analytics
- 15+ analytics panels on the dashboard (equity curve, FTMO status, R:R trend, behavioral trend, exit decomposition, entry/exit quality diagnosis)
- AI coaching (Claude Haiku + rule-based fallback) with 15-block prompt
- MT5 live sync (Windows-only) with INOUT partial-close reconstruction and open-positions snapshots
- Telegram push notifications + structured write-in commands
- Docker Compose full stack (db + backend + frontend, automatic migrations, health gating)

## What Was Fixed in Phase 6 (Deployment Hardening)

| Fix | File |
|---|---|
| Frontend Docker build: `frontend/.dockerignore` to stop `node_modules` entering build context | `frontend/.dockerignore` |
| `eslint-config-next` upgraded to `^15` to resolve ESLint 9 peer-dep conflict in `npm ci` | `frontend/package.json`, `package-lock.json` |
| Recharts `formatter`/`tickFormatter`/`labelFormatter` callback type annotations removed (too narrow for strict TS) | `frontend/app/dashboard/page.tsx` |
| `openEdit()` closure in trade detail didn't re-narrow `trade: Trade \| undefined` | `frontend/app/trades/[tradeId]/page.tsx` |
| Alembic shadow-package fix: `alembic/` directory shadowed installed `alembic` package under `PYTHONPATH=/app` | `docker-entrypoint.sh` |
| Postgres healthcheck fixed: `pg_isready -U trading` → `-U trading -d trading_journal` to stop FATAL log spam | `docker-compose.yml` |
| Frontend API base URL: `NEXT_PUBLIC_API_URL` was silently losing `/api/v1` if env var omitted suffix | `frontend/lib/api.ts`, `frontend/Dockerfile`, `docker-compose.yml` |
| `db` service now publishes `5432:5432` to host for local Windows backend (MT5 sync mode) | `docker-compose.yml` |

## What Remains Rough

1. **Zero HTTP route tests** — only core logic is tested; API surface has no regression protection
2. **`datetime.utcnow()` deprecation** — used in `db_models.py` and `mt5_scheduler.py`; will warn on Python 3.12+
3. **4 `alert()` calls in `app/daily/page.tsx`** — delete/create error paths use browser alert; every other page uses inline banners
4. **README backend install was broken** — `src/main/python/requirements.txt` (doesn't exist) and `cd src/main/python && uvicorn api.app:app` (breaks imports) — FIXED in this session
5. **No data backup story** — `docker compose down -v` destroys all data; no `pg_dump` script documented
6. **`CORS_ORIGINS` hardcoded in compose** — `.env` cannot override it; remote deploy requires editing compose YAML
7. **CI SQLite-only** — Postgres-specific migration issues can pass CI silently

## Two Operating Modes (Do Not Confuse)

| Mode | When | Frontend | Backend | Database |
|---|---|---|---|---|
| **Docker full stack** | Normal journaling | Docker :3000 | Docker :8000 | Docker :5432 |
| **Local Windows MT5 sync** | Live MT5 sync | Docker :3000 | Native Windows :8000 | Docker :5432 |

In MT5 sync mode: `docker compose stop backend`, then run `python -m uvicorn src.main.python.api.app:app --reload` from the Windows venv. The `db` service stays running and is reachable on `localhost:5432`.

MT5 passwords are never in the DB — always from env vars: `MT5_<ACCOUNT_ID_UPPER_UNDERSCORED>_PASSWORD`.

## Next Phase: Phase 7 — Ops Hardening + Onboarding Fix

**Priority:** Do this before adding any new features.

**Scope:**
- Write `start-local-backend.ps1` (PowerShell) and `start-local-backend.sh` (WSL) startup scripts
- Replace 4 `alert()` calls in `app/daily/page.tsx` with inline error banners
- Add "no accounts yet" onboarding prompt on dashboard empty state
- Fix `datetime.utcnow()` → `datetime.now(timezone.utc)` in `db_models.py` and `mt5_scheduler.py`
- Document `pg_dump` backup flow as a simple one-liner script
- (README backend install is already fixed in this session)

**After Phase 7:** Phase 8 is HTTP route test coverage, Phase 9 is MT5 scheduler resilience (alert cooldown, lookback_days in UI, jitter).

## Pending GitHub Push

9 commits are queued locally but blocked by a PAT scope issue: the PAT needs `workflow` scope to push because a `.github/workflows/ci.yml` file exists. Grant `workflow` scope at GitHub → Settings → Personal Access Tokens, then `git push origin main`.
