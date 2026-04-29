# Trading Record Analysis

A professional trading journal and performance analytics system for discretionary traders. Built for FTMO/prop firm tracking, execution improvement, and behavioral analysis.

## What Is This?

A full-stack web app that gives you a structured way to:
- Import your MT4/MT5 trade history via CSV, or sync directly from MT5 in the background
- Enrich each trade with setup tags, execution quality notes, and reflections
- Compare pre-trade plans against actual execution (plan adherence, planned R:R vs realized R)
- See account-level analytics: equity curve, drawdown, win rate, profit factor, Sharpe, Sortino
- Monitor your FTMO challenge progress (daily loss limit, overall drawdown)
- Create daily pre-market plans and post-market reviews
- Generate AI-powered or rule-based weekly coaching summaries
- Receive Telegram push alerts and log trades from your phone via commands

## Current Feature Set

| Area | Status |
|---|---|
| Account create / select / edit / delete | Done |
| Multi-format CSV import (MT4 + MT5) with preview and dedup strategies | Done |
| Trade log with server-side pagination and filtering (symbol, result, date range) | Done |
| Trade detail + journal enrichment (flags, notes, tags, reflection) | Done |
| Setup Library — global setup definitions CRUD | Done |
| Setup type dropdown from Setup Library in trade edit + trade plans | Done |
| Trade plans CRUD + manual link to executed trades | Done |
| Plan-vs-execution analytics: planned/unplanned + followed/deviated comparison | Done |
| Planned R:R vs realized R comparison, realization %, coaching signals | Done |
| Per-setup planned R:R vs realized R breakdown (Setup Library page, coaching) | Done |
| R:R realization trend over time — weekly bar chart on dashboard, coaching signals | Done |
| Per-symbol / per-session analytics — ranked tables, best/worst callouts, coaching signals | Done |
| Dashboard: equity curve, drawdown chart, core analytics | Done |
| FTMO / prop firm status panel with live limit monitoring | Done |
| Daily pre-market plans: create / edit / delete | Done |
| Daily post-market reviews: create / edit / delete | Done |
| Setup analytics: per-setup win rate, avg PnL, profit factor, ranking | Done |
| Mistake analysis: frequency/cost ranking, per-mistake win rate | Done |
| AI coaching (weekly review via Claude API, rule-based fallback, review history) | Done |
| MT5 live sync — config UI, manual trigger, run history, audit log | Done |
| MT5 live sync — open positions snapshot on each sync | Done |
| MT5 live sync — partial close (INOUT) reconstruction | Done |
| MT5 live sync — background polling (APScheduler, per-account interval) | Done |
| MT5 live sync — configurable lookback window (`lookback_days`) per account | Done |
| MT5 scheduler resilience — alert cooldown, polling jitter, single-worker advisory | Done |
| MT5 data freshness UX — Fresh/Stale/Delayed/Error badge on /mt5-sync and dashboard | Done |
| Telegram push notifications (MT5 sync, FTMO alerts, coaching generated) | Done |
| Telegram structured write-in (`/plan`, `/journal`, `/status`, `/ping`) | Done |
| Trade CSV export — `GET /accounts/{id}/trades/export/csv` with active filters | Done |
| Backup + restore scripts (`backup.ps1`/`sh`, `restore.ps1`/`sh`) | Done |
| MT5 SL/TP from order history — `stop_loss`/`take_profit` populated from `history_orders_get` | Done |
| Historical SL/TP backfill — `POST .../mt5-sync/backfill-sl-tp` + UI on MT5 Sync page | Done |
| CSV SL/TP enrichment — `POST .../import/enrich-sl-tp` + UI on Import page | Done |

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts, SWR |
| Backend | Python 3.11+, FastAPI, SQLAlchemy 2.x, Alembic |
| Database | PostgreSQL (local or Supabase) |
| AI | Anthropic Claude API (with rule-based fallback) |
| Scheduling | APScheduler 3.10+ (MT5 background polling) |

## Running Locally

### Prerequisites

- Python 3.11+
- Node.js 20+
- PostgreSQL database (local or Docker — see Docker section below)

### Backend

```bash
# From repo root (IMPORTANT: all commands must run from repo root — imports require it)
python -m venv venv
source venv/bin/activate          # Windows: .\venv\Scripts\activate

# requirements.txt is at the repo root (not inside src/)
pip install -r requirements.txt

# Create .env (see .env.example for all variables)
cp .env.example .env
# Edit .env: set DATABASE_URL at minimum

# Run migrations (from repo root)
python -m alembic upgrade head

# Start server (from repo root — do NOT cd into src/ first)
python -m uvicorn src.main.python.api.app:app --reload
# API at http://localhost:8000 | Docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install

# Create .env.local — NEXT_PUBLIC_API_URL is the backend origin only (/api/v1 is appended by the client)
echo "NEXT_PUBLIC_API_URL=http://localhost:8000" > .env.local

npm run dev
# App at http://localhost:3000
```

### Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `CORS_ORIGINS` | No | Comma-separated allowed origins. Docker default: `http://localhost:3000`. Override in `.env` for remote deploys. |
| `ANTHROPIC_API_KEY` | No | AI coaching — falls back to rule-based without it |
| `LOG_LEVEL` | No | Log verbosity: `DEBUG`, `INFO`, `WARNING`, `ERROR` (default: `INFO`) |
| `TELEGRAM_BOT_TOKEN` | No | Telegram push notifications |
| `TELEGRAM_CHAT_ID` | No | Telegram target chat (for alerts and webhook auth) |
| `TELEGRAM_ENABLED` | No | Set `false` to silence without removing tokens |
| `MT5_<ACCOUNT_ID_UPPER>_PASSWORD` | No | MT5 account password (never stored in DB) |

See `.env.example` for the full annotated reference.

---

## Docker

### Quick start (full stack)

```bash
cp .env.example .env
# Edit .env — set ANTHROPIC_API_KEY, TELEGRAM_*, and any MT5 passwords you need.
# DATABASE_URL is automatically overridden by docker-compose to point at the Compose db service.

docker compose up --build
# Backend: http://localhost:8000 | API docs: http://localhost:8000/docs
# Frontend: http://localhost:3000
```

Migrations run automatically on backend startup before the server accepts traffic.

### What's in the Compose stack

| Service | Image | Port |
|---|---|---|
| `db` | `postgres:15` | 5432 (host + internal) |
| `backend` | built from `Dockerfile` | 8000 |
| `frontend` | built from `frontend/Dockerfile` | 3000 |

Database data persists in a named Docker volume `pgdata`. To reset the database:

> **⚠️ WARNING:** `docker compose down -v` permanently destroys all journal data with no undo.
> Use the safe wrapper instead — it auto-runs a backup first and requires explicit confirmation:
> ```bash
> bash reset-data.sh    # WSL/Linux — backs up, prompts "type reset to continue", then down -v
> .\reset-data.ps1      # Windows PowerShell equivalent
> ```
> Only run the raw command if you are certain there is no data worth keeping:
> ```bash
> docker compose down -v   # DESTRUCTIVE — no backup, no prompt
> docker compose up --build
> ```

### Backup and restore

```bash
# Backup (Docker db must be running) — saves to backups/ with timestamp
.\backup.ps1           # Windows PowerShell
bash backup.sh         # WSL/Linux

# Restore from a backup file
.\restore.ps1 -BackupFile backups\backup_YYYYMMDD_HHMMSS.sql   # Windows
bash restore.sh backups/backup_YYYYMMDD_HHMMSS.sql              # WSL/Linux
```

After restoring, restart the backend to pick up the new data:
```bash
docker compose restart backend
```

### Deploying to a remote host

`NEXT_PUBLIC_API_URL` is baked in at build time and must be the backend **origin only** (no `/api/v1` suffix — the API client always appends it). For a remote server:

```bash
docker compose build --build-arg NEXT_PUBLIC_API_URL=https://your-backend.example.com frontend
```

Or override it in a `docker-compose.override.yml`.

### MT5 live sync — local Windows backend + Docker Postgres

**MT5 sync does not work inside containers.** The `MetaTrader5` Python package is Windows-only and requires a locally running MT5 terminal. In the Docker backend, MT5 sync requests return an error ("MetaTrader5 not available") — no data is corrupted.

For live MT5 sync, run the backend **natively on Windows** while keeping the Docker Postgres database running. The `db` service publishes port 5432 to the host, so the local backend can connect to the same database.

**Two-mode setup:**

| Mode | Frontend | Backend | Database |
|---|---|---|---|
| **Full Docker stack** | Docker container (port 3000) | Docker container (port 8000) | Docker container (port 5432) |
| **Local MT5 sync** | Docker container (port 3000) | Native Windows Python | Docker container (port 5432) |

**Running the local Windows backend (PowerShell):**

```powershell
# From repo root — keep the Docker stack running (for the db and frontend)
# but run the backend natively so MetaTrader5 works

# 1. Activate your Python venv
.\venv\Scripts\activate

# 2. Ensure .env has the Docker Postgres credentials:
#    DATABASE_URL=postgresql+psycopg2://trading:trading@localhost:5432/trading_journal
#    (other vars — API keys, Telegram, MT5 passwords — as needed)

# 3. Run migrations (only needed after a schema change)
$env:PYTHONPATH = "."
python -m alembic upgrade head

# 4. Start the backend
python -m uvicorn src.main.python.api.app:app --reload --host 0.0.0.0 --port 8000
```

> **Note:** When the local backend is running on port 8000, stop the Docker `backend` service first
> to avoid a port conflict:
> ```bash
> docker compose stop backend
> ```
> The `db` and `frontend` containers can keep running.

**Verify the local backend is DB-connected:**
```powershell
Invoke-WebRequest http://localhost:8000/ready | Select-Object -ExpandProperty Content
# Expected: {"status":"ready","database":"connected"}
```

## Core Workflow

1. **Create an account** — go to the home page, create an account with your broker, platform, and starting balance

2. **Import trades** — go to Import, drop your MT4/MT5 CSV export, preview, confirm; optionally run Recompute R & Session afterward

3. **If SL/TP shows blank in Trade Log** — two paths:
   - *Have an FTMO / MT5 CSV export?* → Import page → **Enrich SL/TP from CSV** — no MT5 terminal needed, works offline, exact `trade_id` match
   - *No CSV, but MT5 terminal running (Windows)?* → MT5 Sync page → **Backfill SL/TP from MT5** — queries 2-year order history; may take several minutes; do not click twice
   Both paths are NULL-only fills — running one after the other is safe and idempotent.

4. **Enrich trades** — open any trade from the Trade Log, click Edit Journal, fill in setup type (dropdown from your Setup Library), mistake flags, execution quality, and reflection notes

5. **Create trade plans** — go to Plans, create a pre-trade plan with thesis and R:R, then link it to the actual trade after execution

6. **Monitor the dashboard** — equity curve, drawdown, FTMO panel (daily loss / overall drawdown vs limits), plan adherence, R:R realization

7. **Daily workflow** — use Daily Plans to write your pre-market plan each morning, post a Daily Review at end of session

8. **Generate coaching** — go to AI Coach, select a date range, click Generate Review

---

## MT5 Live Sync

MT5 sync requires a Windows machine with MetaTrader 5 running and the `MetaTrader5` Python package (`pip install MetaTrader5`). It degrades gracefully on Linux/Mac (sync returns an error, no data corruption).

### Setup

1. Set the MT5 password env var:
   ```bash
   # Key format: MT5_<ACCOUNT_ID_UPPER_UNDERSCORED>_PASSWORD
   # Example for account "ftmo-p1":
   MT5_FTMO_P1_PASSWORD=yourpassword
   ```

2. Go to `/mt5-sync` in the sidebar. Fill in your MT5 login, server, and UTC offset. Save.

3. Click **Sync Now** to trigger a manual sync, or enable **Background Polling** and set an interval. The scheduler starts automatically at app boot — no restart needed after config changes.

### What each sync does

- Fetches closed deals for the configured date range
- Reconstructs partial closes (INOUT deals) into a single trade record with volume-weighted exit price
- Upserts trades via `duplicate_strategy="update_broker"` — broker fields update, manual enrichment (notes, flags, setup_type) is preserved
- Replaces the open positions snapshot with current live positions
- Records the run in the audit log with counts and status

### Background polling

- One APScheduler `IntervalJob` per account with `enabled=True`
- Overlap protection: if a sync is already running for an account, the next scheduled fire is skipped
- On error, a Telegram alert is sent (if configured); success runs are silent to avoid noise
- **Note:** overlap lock is in-memory only — multi-process deployments would lose this protection

### Open positions

After each sync, `GET /accounts/{id}/open-positions` returns the current snapshot. The `/mt5-sync` page shows a live table with floating PnL and a total footer.

---

## Plan-vs-Execution Analytics

The dashboard includes a **Plan vs Execution** section showing:

**Plan linkage** (formal `trade_plan_id` link):
- Planned vs unplanned trade performance (win rate, avg PnL, profit factor)

**Self-reported adherence** (`followed_plan` field on trade):
- Followed vs deviated performance

**Planned R:R vs Realized R** (for trades with a linked plan, `planned_rr > 0`, and `actual_r_multiple` set):
- Avg planned R:R / avg realized R / avg shortfall / realization %
- Target-hit rate (% of trades that met or exceeded planned R:R)
- Pre-computed coaching signals

These signals also flow into the AI coaching prompt and rule-based fallback.

---

## Telegram

### Push notifications

| Event | When |
|---|---|
| MT5 sync success/failure | After every manual or scheduled sync |
| FTMO status change | When `account_status` transitions (SAFE → AT_RISK → BREACHED or back) |
| Coaching review generated | After a successful AI-generated review |

```bash
# Test integration
curl -X POST http://localhost:8000/api/v1/telegram/test-ping
```

### Structured write-in (webhook)

Set your webhook URL once:
```bash
curl -X POST "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=https://your-server.com/api/v1/telegram/webhook"
# For local dev: ngrok http 8000
```

Supported commands (key:value format only — no natural-language parsing):

**`/plan`** — create a trade plan  
**`/journal`** — update trade enrichment (requires `trade_id` UUID)  
**`/status`** — account + FTMO snapshot  
**`/ping`** — liveness check

The webhook rejects messages from any chat_id that doesn't match `TELEGRAM_CHAT_ID`.

---

## Known Limitations

| Limitation | Notes |
|---|---|
| No authentication | Single-user, local deployment only. Do not expose publicly without adding auth. |
| MT5 requires Windows | MetaTrader5 Python package is Windows-only. Docker containers run on Linux — MT5 sync will return an error inside containers. Run the backend natively on Windows for live sync. |
| MT5 sync is single-process | Overlap protection is in-memory only. Multi-process (Gunicorn multi-worker) deployments would lose this protection. Use `--workers 1`. |
| Screenshot upload not implemented | `screenshot_examples` field exists in the schema but no image storage is wired up. |
| Telegram NLP deferred | `/journal` requires exact trade UUID. No broker ticket lookup, no multi-step flows. |
| FTMO alert dedup persists across restarts | State stored in `runtime_state` table (migration 011); restarts no longer re-fire stale alerts. |
| Setup Library not auto-populated | New setup names from imports don't create Library entries automatically. |
| Coaching covers closed trades only | No open position awareness in coaching context. |

## CI

GitHub Actions runs on every push and pull request to `main`:

- **Backend tests (SQLite)** — full pytest suite (`src/test/unit/` + `src/test/integration/`) against SQLite
- **Postgres migration check** — spins up Postgres 15, runs `alembic upgrade head`, then 9 migration + ORM smoke tests; catches schema issues that SQLite silently misses
- **Frontend typecheck** — `tsc --noEmit` on the Next.js codebase
- **Frontend E2E** — 8 Playwright smoke tests with mocked API (no backend required); verifies pages render and navigation works

See `.github/workflows/ci.yml`.

---

## Manual Regression Checklist

Use this after changes or before a session to verify core flows.

### Account & Navigation
- [ ] Create a new account; it appears in the account selector
- [ ] Switch accounts; all pages reflect the newly selected account
- [ ] Edit account fields (broker, balance); changes persist

### Import
- [ ] Drop a CSV on the Import page; preview shows parsed rows and skipped count
- [ ] Complete import with `skip` strategy; check trade count in Trade Log
- [ ] Run Recompute R; check `actual_r_multiple` updated on a trade
- [ ] Re-import same file with `update_broker` strategy; trade count unchanged, no duplicates

### Trade Log & Detail
- [ ] Trade log loads with correct pagination (prev/next work, total shown)
- [ ] Filter by symbol narrows results; clearing filter restores all
- [ ] Open a trade detail; all fields display
- [ ] Edit Journal: set setup_type from Setup Library dropdown, add notes, save; changes persist

### Trade Plans
- [ ] Create a trade plan with a setup from the dropdown
- [ ] Open plan detail; all fields display correctly
- [ ] Edit plan; changes persist
- [ ] Link a trade to the plan; trade appears in Linked Trades section
- [ ] Unlink the trade; trade disappears from section
- [ ] Delete plan; plan removed from list

### Setup Library
- [ ] Create a new setup definition; it appears in the list and in the Trade Plan / Trade Edit dropdowns
- [ ] Edit a setup; changes persist
- [ ] Delete a setup with confirmation; setup removed
- [ ] Empty library: Setup Type dropdown in Trade Plans shows only "— unset —" and "Custom…"

### Dashboard & Analytics
- [ ] Dashboard loads with equity curve and drawdown chart
- [ ] FTMO panel shows current daily loss % and overall drawdown
- [ ] Plan vs Execution section shows planned/unplanned split (if linked plans exist)
- [ ] R:R Realization panel appears and shows data (if linked plans with `planned_rr` exist)

### MT5 Sync (Windows only)
- [ ] Save MT5 config; it persists across page reload
- [ ] Trigger manual sync; result card shows new/updated/skipped counts
- [ ] Run history shows the new run with "manual" source badge
- [ ] Open Positions table appears after sync (may be empty if no open trades)
- [ ] Enable background polling; "Next poll" time shown in UI

### Telegram (requires TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID)
- [ ] `POST /api/v1/telegram/test-ping` returns `{sent: true}`
- [ ] Trigger FTMO check; Telegram alert fires if status changed
- [ ] `/ping` in Telegram returns liveness response
- [ ] `/status account: <id>` returns account + FTMO snapshot

### Coaching
- [ ] Select date range; click Generate Review; review appears in history
- [ ] Source badge shows "AI" or "Fallback" correctly
- [ ] Expanding review shows summary, diagnosis, improvement, top mistakes

---

## Future Roadmap

See `RPD.md` and `docs/dev/project-state-2026-04-30-public-release-prep.md` for the full product roadmap. The project is in long-term observation mode — items below are trigger-based, not scheduled.

| Priority | Area | Trigger |
|---|---|---|
| Later | Screenshot / image attachment upload | When trade-context evidence becomes a workflow gap |
| Later | AI provider abstraction (OpenAI / Gemini option) | Anthropic outage or pricing change |
| Later | Multi-user authentication | Hosted-deployment requirement |
| Later | MAE / MFE analytics | Operator wants entry-vs-exit decomposition with bar-data evidence |
| Later | Open-trade awareness in coaching | Operator wants "what should I do with this open position" coaching |
| Later | Async backfill job with progress endpoint | Synchronous backfill wait becomes painful at scale |
