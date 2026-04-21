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
| Telegram push notifications (MT5 sync, FTMO alerts, coaching generated) | Done |
| Telegram structured write-in (`/plan`, `/journal`, `/status`, `/ping`) | Done |

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
- Node.js 18+
- PostgreSQL database (local or Supabase)

### Backend

```bash
# From repo root
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r src/main/python/requirements.txt

# Create .env (see .env.example for all variables)
cp .env.example .env
# Edit .env: set DATABASE_URL at minimum

# Run migrations
alembic upgrade head

# Start server
cd src/main/python
uvicorn api.app:app --reload
# API at http://localhost:8000 | Docs at http://localhost:8000/docs
```

### Frontend

```bash
cd frontend
npm install

# Create .env.local
echo "NEXT_PUBLIC_API_URL=http://localhost:8000/api/v1" > .env.local

npm run dev
# App at http://localhost:3000
```

### Environment Variables

| Variable | Required | Purpose |
|---|---|---|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `ANTHROPIC_API_KEY` | No | AI coaching — falls back to rule-based without it |
| `CORS_ORIGINS` | No | Allowed origins for CORS (default: localhost:3000) |
| `TELEGRAM_BOT_TOKEN` | No | Telegram push notifications |
| `TELEGRAM_CHAT_ID` | No | Telegram target chat (for alerts and webhook auth) |
| `TELEGRAM_ENABLED` | No | Set `false` to silence without removing tokens |
| `MT5_<ACCOUNT_ID_UPPER>_PASSWORD` | No | MT5 account password (never stored in DB) |

## Core Workflow

1. **Create an account** — go to the home page, create an account with your broker, platform, and starting balance

2. **Import trades** — go to Import, drop your MT4/MT5 CSV export, preview, confirm; optionally run Recompute R & Session afterward

3. **Enrich trades** — open any trade from the Trade Log, click Edit Journal, fill in setup type (dropdown from your Setup Library), mistake flags, execution quality, and reflection notes

4. **Create trade plans** — go to Plans, create a pre-trade plan with thesis and R:R, then link it to the actual trade after execution

5. **Monitor the dashboard** — equity curve, drawdown, FTMO panel (daily loss / overall drawdown vs limits), plan adherence, R:R realization

6. **Daily workflow** — use Daily Plans to write your pre-market plan each morning, post a Daily Review at end of session

7. **Generate coaching** — go to AI Coach, select a date range, click Generate Review

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
| MT5 requires Windows | MetaTrader5 Python package is Windows-only. Linux/Mac: sync returns an error, no data is affected. |
| Screenshot upload not implemented | `screenshot_examples` field exists in the schema but no image storage is wired up. |
| Telegram NLP deferred | `/journal` requires exact trade UUID. No broker ticket lookup, no multi-step flows. |
| FTMO alert dedup is in-memory | Server restart clears dedup state; first check after restart will re-fire the current status alert. |
| Setup Library not auto-populated | New setup names from imports don't create Library entries automatically. |
| APScheduler is single-process | Background polling overlap protection is in-memory. Multi-process deployments would need an external lock. |
| Coaching covers closed trades only | No open position awareness in coaching context. |

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

See `RPD.md` for the full product roadmap.

| Priority | Area |
|---|---|
| Next | Per-symbol / per-session analytics tabs on dashboard |
| Later | Target-hit vs stop-hit decomposition |
| Later | Entry quality vs exit quality decomposition |
| Later | Richer MT5 sync status / freshness UX |
| Later | Screenshot / image attachment upload |
| Later | AI provider abstraction (OpenAI / Gemini option) |
| Later | Multi-user authentication |
