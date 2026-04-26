# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## CRITICAL RULES - READ FIRST

### RULE ACKNOWLEDGMENT REQUIRED
Before starting ANY task, respond with:
> "CRITICAL RULES ACKNOWLEDGED - I will follow all prohibitions and requirements listed in CLAUDE.md"

### ABSOLUTE PROHIBITIONS
- **NEVER** create new files in the root directory — use proper module structure
- **NEVER** write output files to the root directory — use `output/`
- **NEVER** create documentation files (.md) unless explicitly requested
- **NEVER** use `find`, `grep`, `cat`, `head`, `tail`, `ls` bash commands — use Read, Grep, Glob tools
- **NEVER** use git with the `-i` flag (interactive mode not supported)
- **NEVER** create duplicate or versioned files (`manager_v2.py`, `enhanced_xyz.py`, `utils_new.py`) — extend existing files
- **NEVER** use naming like `enhanced_`, `improved_`, `new_`, `v2_`

### MANDATORY REQUIREMENTS
- **COMMIT** after every completed task/phase
- **PUSH** to GitHub after every commit: `git push origin main`
- **SEARCH FIRST** before creating anything — Grep for existing implementations
- **READ FILES FIRST** before editing (Edit/Write tools require a prior Read)

---

## Project Status (as of 2026-04-26)

### Maturity: 9 / 10 — Feature-complete, test coverage solid, ops hardened

### Completed Phases
- **Phase 1** — Core backend (accounts, trades, CSV import, analytics, PostgreSQL)
- **Phase 2** — Frontend (Next.js 14, all pages wired to real API data)
- **Phase 3** — Coaching, MT5 sync, Telegram
- **Phase 4** — Trade plans, daily plans/reviews, plan-adherence analytics
- **Phase 5** — Advanced analytics (R:R trend, behavioral trend, exit decomposition, entry/exit quality)
- **Phase 6** — Deployment hardening (Docker Compose, alembic shadow-package fix, port 5432 published, API base URL fix, TypeScript build errors resolved)
- **Phase 7** — Ops hardening + onboarding fix (README rewrite, startup scripts, alert()→banners, dashboard empty state, datetime deprecation)
- **Phase 8** — HTTP route test coverage (59 route tests across 8 groups, zero `datetime.utcnow()` remaining)
- **Phase 9** — MT5 scheduler resilience (alert cooldown 4h, polling jitter 0–30s, `lookback_days` configurable, single-worker startup advisory)
- **Phase 10** — MT5 `lookback_days` UI + `GET /accounts/{id}/trades/export/csv` + `backup.ps1`/`backup.sh`
- **Phase 11** — CI hardening: Postgres 15 CI job (migration + ORM smoke tests), Playwright E2E (8 tests, mocked API), `restore.ps1`/`restore.sh`

### Strongest Modules
1. `core/account_analytics.py` + `core/metrics_calculator.py` — 15+ metric families, no stubs
2. `services/ai_coach.py` — real Anthropic API with genuine 300-line rule-based fallback
3. `api/routes/` — full CRUD on all entities; 50+ endpoints; analytics is read-only/extensive
4. Frontend `app/dashboard/page.tsx` — 15 wired panels, no fake data

### Current Weak / Rough Areas
- Telegram webhook has no HTTP route tests — chat_id guard regression would be invisible
- Frontend E2E tests use mocked API only — no real-data end-to-end coverage
- No automated backup schedule — `backup.ps1`/`backup.sh` exist but must be run manually

### Next Direction (no phase assigned yet)
Highest-value candidates:
1. Add Telegram webhook route tests (same pattern as existing `test_routes.py`)
2. Empty-state guidance on Trades, Plans, Daily, Coaching pages (onboarding polish)

---

## Operating Modes

### Mode 1: Docker Full Stack (normal use)
The entire stack runs in Docker. Use this for day-to-day journaling, analytics, and coaching.

```bash
# Start
cp .env.example .env   # only first time; set ANTHROPIC_API_KEY etc.
docker compose up -d   # or with --build after code changes

# Access
# Frontend:  http://localhost:3000
# Backend:   http://localhost:8000
# API docs:  http://localhost:8000/docs
```

The Docker backend **cannot** do MT5 live sync — `MetaTrader5` is Windows-only and not installed in the container. MT5 sync routes return an error gracefully; no data is corrupted.

### Mode 2: Local Windows Backend + Docker Postgres (MT5 sync)
Use this when you need MT5 live sync. The Docker `db` service (Postgres on port 5432) stays running; the Docker backend is stopped to free port 8000; a native Windows Python process runs the backend instead.

```powershell
# 1. Keep db + frontend running; stop only the backend container
docker compose stop backend

# 2. Activate your venv from repo root
.\venv\Scripts\activate

# 3. Ensure .env has Docker Postgres credentials:
#    DATABASE_URL=postgresql+psycopg2://trading:trading@localhost:5432/trading_journal

# 4. Run migrations if needed
#    Use the alembic binary directly — python -m alembic fails because the
#    local alembic/ migration directory shadows the installed package.
alembic upgrade head

# 5. Start local backend (PYTHONPATH must be repo root for src.main.python.* imports)
$env:PYTHONPATH = "."
python -m uvicorn src.main.python.api.app:app --reload --host 0.0.0.0 --port 8000

# 6. Verify DB connection
Invoke-WebRequest http://localhost:8000/ready | Select-Object -ExpandProperty Content
# Expected: {"status":"ready","database":"connected"}
```

**Why these modes are different:**
- `MetaTrader5` Python package is Windows-only and requires a running MT5 terminal on the same machine
- The Docker backend runs on Linux (Alpine) so it cannot import `MetaTrader5`
- The `db` service publishes `5432:5432` to the host so the local Windows backend can share the same Postgres data
- MT5 sync overlap protection is in-memory — **must use `--workers 1`** (already set in `docker-entrypoint.sh`; must also be enforced in local dev)

**Do not mix modes carelessly:**
- Running `docker compose up` when a local backend already holds port 8000 → Docker backend restart-loops
- Running `docker compose down` stops the db, which disconnects the local backend
- `docker compose down -v` permanently destroys all journal data (no backup warning, no undo)

### MT5 password handling
MT5 passwords are **never stored in the database**. They are read from environment variables at sync time:
```
MT5_<ACCOUNT_ID_UPPER_UNDERSCORED>_PASSWORD=yourpassword
# Example: account "ftmo-p1" → MT5_FTMO_P1_PASSWORD=yourpassword
# Example: account "ic.markets.01" → MT5_IC_MARKETS_01_PASSWORD=yourpassword
```
These must be in `.env` (loaded by `load_dotenv()` at import time) or set in the shell environment before starting the backend.

---

## Commands

```bash
# Start backend (run from repo root — src.main.python.* imports and resource paths require it)
python -m uvicorn src.main.python.api.app:app --reload
# API at http://localhost:8000  |  Docs at http://localhost:8000/docs

# Run all tests
python -m pytest src/test/

# Run a single test file
python -m pytest src/test/unit/test_metrics_calculator.py -v

# Run a single test by name
python -m pytest src/test/unit/test_csv_parser.py::TestMTCSVParser::test_parse_win -v

# Apply DB migrations
alembic upgrade head

# Start frontend
cd frontend && npm run dev
# App at http://localhost:3000

# Push to GitHub
git push origin main

# Docker (full stack)
docker compose up --build

# Health / readiness checks
curl http://localhost:8000/health
curl http://localhost:8000/ready

# Run Playwright E2E tests (first time: cd frontend && npx playwright install chromium)
cd frontend && npm run test:e2e

# Backup database (Docker db service must be running)
.\backup.ps1                                              # Windows PowerShell → backups/
bash backup.sh                                            # WSL/Linux

# Restore from backup
.\restore.ps1 -BackupFile backups\backup_YYYYMMDD.sql    # Windows
bash restore.sh backups/backup_YYYYMMDD.sql               # WSL/Linux
```

---

## Architecture

### Backend (`src/main/python/`)

**Entry point:** `api/app.py` — `create_app()` builds the FastAPI app and registers all routers. The module-level `app = create_app()` is what uvicorn targets (`uvicorn api.app:app`).

**Layer structure (strict top-down, no skipping):**
```
api/routes/     →  api/schemas/    →  services/   →  core/    →  models/
(HTTP handlers)    (Pydantic I/O)    (DB + ext.)    (logic)    (dataclasses)
```

- **`models/`** — Pure Python dataclasses (`Trade`, `Account`, `TradePlan`, `DailyPlan`). No SQLAlchemy here. Enums live in `models/enums.py` (`TradeResult`, `Direction`, `AssetClass`, `Platform`, `ChallengePhase`).
- **`models/db_models.py`** — SQLAlchemy ORM models. Completely separate from domain dataclasses. Conversions happen in `utils/db_converters.py` via `orm_to_trade()` / `trade_to_orm()`.
- **`services/`** — Repository classes (one per entity: `TradeRepository`, `AccountRepository`, `TradePlanRepository`, etc.) that accept a `Session` in `__init__`. Also: `MT5SyncService`, `AICoachService`, `TelegramNotifier`. Services never commit — the caller (route) owns session lifecycle via `get_session()` context manager in `database.py`.
- **`core/`** — Pure business logic, no DB: `AccountAnalytics`, `MetricsCalculator`, `MistakeAnalyzer`, `SetupAnalyzer`, `DerivedFieldCalculator`. All stateless static/class methods.
- **`api/dependencies.py`** — FastAPI DI functions: `get_db()`, `get_account_repo()`, `get_trade_repo()`, `require_account()`. `get_db()` yields a session from `get_session()` context manager. `load_dotenv()` fires in `database.py` at import time — this means env vars are available for all subsequent imports.

**Session pattern:**
```python
# In routes — caller commits via get_db():
def my_route(db: Session = Depends(get_db)):
    repo = TradeRepository(db)   # repo stores session, never commits
    repo.save(trade)             # flush only; commit happens when route exits
```

**Singleton services** (instantiated once at module level, reused across requests):
- `_coach = AICoachService()` in `api/routes/coaching.py`
- `_analytics = AccountAnalytics()` in `api/routes/analytics.py`
- `_notifier = TelegramNotifier()` in `services/telegram_notifier.py` (via `get_notifier()`)

**All API routes are account-scoped:** `/api/v1/accounts/{account_id}/...`

**`Account` model fields:** `account_id`, `broker`, `platform`, `prop_firm`, `challenge_phase`, `starting_balance`, `account_currency`, `created_at`. There is **no `name` field** — use `account_id` or `account.broker` as a display label.

### Frontend (`frontend/`)

Next.js App Router (`frontend/app/`). Components in `frontend/components/`. Shared utilities in `frontend/lib/` (`api.ts` for all backend calls, `utils.ts` for formatting). Uses SWR for data fetching with key pattern `"resource-{accountId}-{filters}"` for correct cache invalidation.

### Config & Environment

- `.env` at repo root (gitignored) — loaded by `load_dotenv()` in `database.py`
- `.env.example` documents all required/optional vars: `DATABASE_URL`, `ANTHROPIC_API_KEY`, `CORS_ORIGINS`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `TELEGRAM_ENABLED`, `MT5_<ACCOUNT_ID_UPPER>_PASSWORD`
- YAML config in `src/main/resources/config/` — loaded via `config_loader.py` with `@lru_cache`

### Database

- PostgreSQL. Migrations in `alembic/versions/`.
- ORM ↔ domain conversion: `utils/db_converters.py` — always go through `orm_to_trade()` / `trade_to_orm()`, never access ORM fields directly in business logic.

### MT5 Sync

`services/mt5_sync_service.py` → `services/mt5_connector.py`. MT5 password never stored in DB — read from env var `MT5_<ACCOUNT_ID_UPPER_UNDERSCORED>_PASSWORD` at request time. Windows-only; degrades gracefully on Linux/Mac.

**Background polling:** `services/mt5_scheduler.py` — `MT5PollingScheduler` singleton (APScheduler). Started/stopped via a FastAPI lifespan context manager in `api/app.py`. One `IntervalJob` per enabled account. Overlap protection is in-memory only (`_running` set) — safe for single-process, not multi-worker deployments.

### Telegram

Push notifications: `services/telegram_notifier.py` — `TelegramNotifier` singleton. Methods: `notify_mt5_sync_result()`, `check_and_notify_ftmo()` (state-change dedup via in-memory `_last_ftmo_status` dict), `notify_coaching_generated()`. All fire-and-forget. Structured write-in: `api/routes/telegram.py` — webhook/command handler with chat_id guard.

### Setup Library

`SetupDefinition` is **globally scoped** (not per-account). The `GET /setups` endpoint is not under `/accounts/{id}/`. Analytics (`GET /accounts/{id}/setups`) is account-scoped and groups by `trade.setup_type` string. The `SetupTypeSelect` frontend component (`frontend/components/SetupTypeSelect.tsx`) is shared across trade edit and trade plan forms — it stores `setup.name` as the `setup_type` string so analytics keying is unaffected.

### Testing

- Unit tests: `src/test/unit/` — use in-memory fixtures, no DB
- Integration tests: `src/test/integration/` — use SQLite in-memory via pytest fixtures
- Factory helpers: `make_trade()`, `make_account()` in each test file
- No mocking of DB — tests use real SQLite sessions

---

## GitHub Setup

- **Remote:** https://github.com/pengfuchao/trading_record_analysis.git
- **Branch:** `main`
- After every commit: `git push origin main`
