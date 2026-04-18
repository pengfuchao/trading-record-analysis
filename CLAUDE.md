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

## Commands

```bash
# Start backend (from repo root)
cd src/main/python && uvicorn api.app:app --reload
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

### Telegram

Phase 1 (notifications): `services/telegram_notifier.py` — `TelegramNotifier` singleton. Three notification methods: `notify_mt5_sync_result()`, `check_and_notify_ftmo()` (state-change dedup via in-memory `_last_ftmo_status` dict), `notify_coaching_generated()`. All fire-and-forget. Phase 2 (structured write-in): `api/routes/telegram.py` — webhook/command handler.

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
