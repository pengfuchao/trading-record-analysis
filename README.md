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

## Current Limitations

- No live MT5/MT4 connection — import is CSV-only; live sync is not yet implemented
- No authentication — the app is single-user, designed for local/personal use
- No chart screenshot attachments — image upload is not yet implemented
- Trade log pagination not implemented — may be slow with 500+ trades
- Coaching review covers closed trades only; no open position awareness
- Setup library is manually managed; no auto-population from imported trades

## Future Roadmap

See `RPD.md` for full product roadmap. Summary:

| Priority | Feature |
|---|---|
| 1 | MT5 live sync (periodic background sync of closed trades, open positions, account info) |
| 2 | Telegram notifications (FTMO warnings, import success, coaching generated, daily summary) |
| 3 | Telegram structured write-in (create plans, add journal notes, query account status via Telegram) |
| 4 | Plan-vs-execution analytics (followed_plan signal, planned vs unplanned trade performance) |
| Later | AI provider abstraction (Anthropic / OpenAI / Gemini switching) |
