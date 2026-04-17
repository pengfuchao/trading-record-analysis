# Trading Record Analysis

A professional trading journal and performance analytics system for discretionary traders. Built for FTMO/prop firm tracking, execution improvement, and behavioral analysis.

## What Is This?

A full-stack web app that gives you a structured way to:
- Import your MT4/MT5 trade history via CSV
- Enrich each trade with setup tags, execution quality notes, and reflections
- See account-level analytics: equity curve, drawdown, win rate, profit factor, etc.
- Monitor your FTMO challenge progress in real time (daily loss used, overall drawdown)
- Create daily pre-market plans and post-market reviews
- Link trade plans to actual executed trades
- Generate AI-powered weekly coaching summaries

## Current Feature Set (MVP+)

| Area | Status |
|---|---|
| Account create / select / edit | Done |
| Multi-format CSV import (MT4 + MT5) with preview and dedup | Done |
| Trade log with filtering (symbol, result, date range) | Done |
| Trade detail + journal enrichment (flags, notes, tags, reflection) | Done |
| Setup type autocomplete from setup library | Done |
| Trade plans CRUD + manual link to executed trades | Done |
| Dashboard: equity curve, drawdown chart, core analytics | Done |
| FTMO / prop firm status panel with live limit monitoring | Done |
| Daily pre-market plans: create / edit / delete | Done |
| Daily post-market reviews: create / edit / delete | Done |
| AI coaching (weekly review via Claude API, rule-based fallback) | Done |
| Coaching review history | Done |
| MT5 live sync — Phase 1 (config UI, manual sync trigger, run history, audit log) | Done |
| Telegram notifications — Phase 1 (MT5 sync result, FTMO risk alerts, coaching generated) | Done |

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 14 (App Router), TypeScript, Tailwind CSS, Recharts, SWR |
| Backend | Python 3.11+, FastAPI, SQLAlchemy, Alembic |
| Database | PostgreSQL (Supabase or local) |
| AI | Anthropic Claude API (with rule-based fallback) |

## Running Locally

### Prerequisites

- Python 3.11+
- Node.js 18+
- PostgreSQL database (local or Supabase)

### Backend

```bash
# From repo root
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r src/main/python/requirements.txt

# Set environment variables
export DATABASE_URL="postgresql://user:password@localhost:5432/trading_db"
export ANTHROPIC_API_KEY="sk-ant-..."   # Optional — coaching falls back to rule-based without it

# Run migrations
alembic upgrade head

# Start server
cd src/main/python
uvicorn api.main:app --reload
# API available at http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install

# Create .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local

npm run dev
# App available at http://localhost:3000
```

## Core Workflow

1. **Create an account** — go to the account selector, create a new account with your broker, platform, and starting balance

2. **Import trades** — go to Import, drop your MT4/MT5 CSV export, preview the results, confirm import; optionally run Recompute R & Session afterward

3. **Enrich trades** — open any trade from the Trade Log, click Edit Journal, fill in setup type (autocomplete from your setup library), mistake flags, execution quality, and reflection notes

4. **Create trade plans** — go to Plans, create a pre-trade plan with thesis and R:R, then link it to the actual trade after execution

5. **Monitor the dashboard** — the Dashboard shows equity curve, drawdown, FTMO panel (daily loss used / overall drawdown vs your limits), and top analytics

6. **Daily workflow** — use Daily Plans to write your pre-market plan each morning, then post a Daily Review at end of session

7. **Generate coaching** — go to AI Coach, select a date range, click Generate Review to get a pattern-based or AI-written performance summary

## MT5 Live Sync — Phase 1 Usage

Phase 1 is backend-only. Use the API directly (no frontend UI yet).

### First-time setup

1. Apply migration 006:
   ```bash
   alembic upgrade head
   ```

2. Set the MT5 password env var (Windows only — same machine as MetaTrader 5):
   ```bash
   # Key format: MT5_<ACCOUNT_ID_UPPER_UNDERSCORED>_PASSWORD
   # Example for account "ftmo-p1":
   MT5_FTMO_P1_PASSWORD=yourpassword
   ```

3. Create the MT5 config for your account:
   ```bash
   curl -X POST http://localhost:8000/api/v1/accounts/ftmo-p1/mt5-config \
     -H "Content-Type: application/json" \
     -d '{
       "mt5_login": 12345678,
       "mt5_server": "ICMarkets-Live",
       "broker_utc_offset": 2
     }'
   ```

4. Trigger a manual sync:
   ```bash
   curl -X POST http://localhost:8000/api/v1/accounts/ftmo-p1/mt5-sync \
     -H "Content-Type: application/json" \
     -d '{"from_date": "2024-01-01T00:00:00", "to_date": "2024-04-01T00:00:00"}'
   # Omit body to default to last 30 days
   ```

5. Check sync status:
   ```bash
   curl http://localhost:8000/api/v1/accounts/ftmo-p1/mt5-sync/status
   ```

### Notes

- After sync, the **dashboard, FTMO panel, and trade log all update automatically** — they query trades live on every page load, no cache flush needed.
- MT5 syncs broker-sourced fields only. All manual enrichment (setup_type, notes, flags, reflection) is preserved on re-sync.
- `session` (Asia/London/NY) is set on first sync. It is **not** updated on re-sync to preserve any manual overrides. If you want session populated for existing trades, run `POST /accounts/{id}/import/recompute-derived?recalculate_session=true` after sync.
- The `broker_utc_offset` in your MT5 config controls session classification and FTMO daily loss calculation. Verify it matches your broker's server timezone.
- On Linux/Mac (no MetaTrader5 package): sync returns `status: "error"` with a platform message. The error is recorded in the audit log. No data is corrupted.

## Current Limitations

- MT5 sync UI is at `/mt5-sync` in the sidebar — configure connection, trigger sync, view run history
- MT5 sync requires Windows with MetaTrader5 package: `pip install MetaTrader5`
- MT5 password is stored in `.env` only, never in the database
- MT5 sync is manual-trigger only in Phase 1 — no background polling (Phase 2)
- Open positions and partial closes (hedges) are not synced yet (Phase 2)
- No authentication — the app is single-user, designed for local/personal use
- No chart screenshot attachments — image upload is not yet implemented
- Trade log pagination not implemented — may be slow with 500+ trades
- Coaching review covers closed trades only; no open position awareness
- Setup library is manually managed; no auto-population from imported trades

## Telegram Notifications — Phase 1

Telegram push notifications are implemented. No interactive commands or write-in yet.

### Events covered

| Event | When |
|---|---|
| MT5 sync success | After every successful manual sync — shows new/updated/skipped counts |
| MT5 sync failure | After any sync error — shows error message |
| FTMO risk alert | When `account_status` changes (SAFE → AT_RISK → BREACHED or back) |
| Coaching review | After a successful AI-generated weekly review |

### Required environment variables

```bash
TELEGRAM_BOT_TOKEN=7xxxxxxxxx:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
TELEGRAM_CHAT_ID=-1001234567890
# TELEGRAM_ENABLED=false   # uncomment to silence without removing tokens
```

### Test integration

```bash
curl -X POST http://localhost:8000/api/v1/telegram/test-ping
# → {"sent": true, "message": "ping sent"}
```

### Trigger FTMO check (for cron/scheduler)

```bash
curl -X POST http://localhost:8000/api/v1/accounts/ftmo-p1/ftmo-check
# Only sends Telegram alert if account_status has changed since last check.
# Returns full FTMO status + notification_sent + prev_status fields.
```

### What is deferred

- Telegram commands (`/status`, `/sync`, `/report`)
- Trade plan creation from Telegram
- Journal write-in or structured Telegram input
- Interactive linking / approval flows
- Per-account Telegram chat configuration

---

## Future Roadmap

See `RPD.md` for full product roadmap. Summary:

| Priority | Feature |
|---|---|
| 1 | MT5 live sync Phase 2 (background polling, open positions) |
| 2 | Telegram notifications — **Done (Phase 1)** |
| 3 | Telegram structured write-in (create plans, add journal notes, query account status) |
| 4 | Plan-vs-execution analytics (followed_plan signal, planned vs unplanned trade performance) |
| Later | AI provider abstraction (Anthropic / OpenAI / Gemini switching) |
