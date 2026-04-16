# Product Requirements Document
## Trading Record Analysis — MVP+ State and Future Roadmap

**Document version:** 2.0  
**Last updated:** 2026-04-16  
**Status:** Active development — MVP+ complete, expansion planning phase

---

## 1. Product Purpose

A professional trading journal and account analytics platform for discretionary traders operating in prop firm (FTMO-style) environments. The system helps traders:

- Understand *why* they lose money — analysis errors vs execution errors vs psychology
- Identify which setups perform best and which should be paused
- Monitor prop firm challenge survival in real time (daily loss limit, overall drawdown)
- Build consistent daily pre-market and post-market habits
- Generate periodic AI coaching insights from trade history

---

## 2. Current MVP+ State (as of 2026-04-16)

### 2.1 What Is Built and Working

| Module | Feature | State |
|---|---|---|
| Accounts | Create, select, edit (broker, balance, platform, prop firm, phase) | Complete |
| Import | MT4 + MT5 CSV multi-format parsing, preview, dedup strategies, recompute R/session | Complete |
| Trade Log | Filterable list (symbol, result, date range) | Complete |
| Trade Detail | Full execution data, journal enrichment (flags, tags, reflection), inline edit | Complete |
| Trade Plans | CRUD + manual link to executed trades | Complete |
| Dashboard | Equity curve, drawdown chart, core analytics (win rate, PF, expectancy, R, drawdown, Sharpe, Sortino, streaks) | Complete |
| FTMO Panel | Daily loss used vs limit, overall drawdown vs limit, status badges, progress bars, 1-min auto-refresh | Complete |
| Daily Plans | Pre-market plan CRUD (bias, symbols, setups, rules) | Complete |
| Daily Reviews | Post-market review CRUD (PnL, mistakes, emotional summary, reflection) | Complete |
| Mistake Analysis | Mistake frequency/cost ranking on dashboard | Complete |
| Setup Library | Setup definitions CRUD, setup type autocomplete on trade edit form | Complete |
| AI Coaching | Weekly review via Anthropic Claude API, rule-based fallback, review history | Complete |

### 2.2 Tech Stack

- **Frontend:** Next.js 14 App Router, TypeScript, Tailwind CSS, Recharts, SWR
- **Backend:** Python 3.11, FastAPI, SQLAlchemy 2.x, Alembic
- **Database:** PostgreSQL
- **AI:** Anthropic Claude API (sonnet model), rule-based fallback when API key not set
- **Charts:** Recharts (React-native, no Plotly dependency)

### 2.3 Architecture Notes

- All API routes are under `/api/v1/accounts/{account_id}/...` — account-scoped from the start
- SWR cache invalidation uses prefix-predicate pattern: `mutate(k => k.startsWith("prefix-${accountId}"))` for correct invalidation of filtered keys
- PATCH endpoints use `exclude_unset=True` (daily plans/reviews) or `exclude_none=True` (accounts) — sparse updates are supported
- Coaching uses `source: "ai" | "fallback"` and `status: "success" | "fallback" | "error"` — UI distinguishes these clearly with a FallbackNotice component

---

## 3. Refinement Backlog (Post MVP+)

These are small improvements suitable for the current development phase:

| Item | Priority | Notes |
|---|---|---|
| Trade log pagination | Medium | No pagination today; can be slow at 500+ trades. Implement cursor or page-based pagination on the backend. |
| Per-symbol / per-session analytics tabs | Medium | Dashboard shows account-level only. Segmented analytics by symbol/session would improve coaching signal. |
| Chart screenshot upload | Low | No image attachment today. Would require file storage (Supabase Storage / S3). |
| Setup library auto-suggestions from import | Low | New setup names from CSV don't auto-populate the library; trader must add them manually. |
| `broker_utc_offset` UI configuration | Low | Currently a hidden parameter on FTMO endpoint. Surfacing it would improve daily loss calculation accuracy for non-UTC brokers. |
| Manual trade entry form | Low | Currently trades come from CSV only. A create-trade form would support manually recording trades not from MT4/MT5. |

---

## 4. Next-Stage Architecture Roadmap

These modules are **documented but not yet implemented**. They represent the planned expansion path after the current MVP+ state is stable.

---

### 4.1 MT5 Live Sync (Priority 1)

**Purpose:** Replace manual CSV upload with automatic background sync from MetaTrader 5.

#### Phase 1 — Manual Trigger (IMPLEMENTED 2026-04-16)

Backend-only. No frontend UI yet. Phase 1 delivers:

- `MT5SyncConfigModel` + `MT5SyncRunModel` DB tables (migration 006)
- `MT5Connector` — context manager that owns MT5 terminal lifecycle (`mt5.initialize` / `mt5.login` / `mt5.shutdown`); Windows-only with graceful degradation on Linux/Mac
- `MT5SyncService` — orchestrates fetch → normalize → upsert using existing `save_batch_import(duplicate_strategy="update_broker")` and `DerivedFieldCalculator`; all manual enrichment (notes, flags, setup_type) is preserved
- 4 REST endpoints: `POST /mt5-config`, `GET /mt5-config`, `POST /mt5-sync` (manual trigger), `GET /mt5-sync/status`
- Password convention: `MT5_<ACCOUNT_ID_UPPER>_PASSWORD` env var — never stored in DB
- Audit log: every sync run is recorded with status, counts, and error message

**Constraints:**
- Requires Windows machine with MetaTrader5 Python package installed (`pip install MetaTrader5`)
- App starts normally on Linux/Mac without the package (sync returns error if triggered)
- Phase 1 is synchronous — HTTP request blocks until sync completes

#### Phase 2 — Scheduled Background Polling (DEFERRED)

- APScheduler periodic background sync (closed trades + open positions)
- `polling_interval_minutes` DB column already exists as placeholder — no migration needed
- Open position tracking (`mt5.positions_get()`) — needs separate schema design
- DEAL_ENTRY_INOUT (partial closes/hedges) handling
- Frontend UI: sync config page, manual trigger button, sync status indicator

**Why MT5 first, not MT4:**
- MT5 has a clean Python package with official support
- MT4 requires a bridge (EA/DLL) or file-based export — significantly more fragile
- Most modern prop firm accounts run on MT5

**Frontend impact (Phase 2):**
- Dashboard/FTMO panel would auto-reflect without manual import
- Import page becomes optional ("manual override") rather than primary workflow
- Add a "Sync status" indicator to account selector or dashboard header

---

### 4.2 MT4 Integration (Priority 3, lower confidence)

**Purpose:** Support MT4 users who cannot use the MT5 Python package.

**Preferred approach:**
- File-based sync via an EA (Expert Advisor) that writes trade history to a local CSV/JSON file at configurable intervals
- The backend watches for file changes and auto-imports
- Alternatively: enhanced CSV import that handles MT4 export formats (already partially supported via multi-format parser)

**Why lower priority:**
- MT4 is being phased out by most prop firms
- The Python integration path is not available (no official MT4 Python package)
- EA-based bridges are brittle and require trader to configure their terminal

---

### 4.3 Telegram Integration (Priority 2 + 3)

**Two phases, different value:**

#### Phase A — Notification Mode (Priority 2)
Push-only notifications to a personal Telegram bot. No write capability needed.

Trigger events:
- FTMO daily loss limit approaching (e.g., 70%, 90% consumed)
- FTMO overall drawdown approaching limit
- Import/sync completed (N new trades imported)
- AI coaching review generated
- Daily plan reminder (morning) / review prompt (EOD)

Implementation:
- Simple Telegram Bot API wrapper (POST to `sendMessage`)
- Background job watches for trigger conditions
- Configurable thresholds per account

#### Phase B — Structured Write-In Mode (Priority 3)
Bi-directional bot that lets the trader interact with the journal from Telegram.

Use cases:
- "Create trade plan: XAUUSD long, OB retest, SL 2030, TP 2060, R:R 1.5" → creates a draft plan
- "Add note to last trade: chased entry, should have waited for confirmation"
- "How am I doing today?" → returns daily P&L, FTMO status
- "Generate coaching review for this week"

Implementation path:
- FastAPI webhook endpoint for Telegram Bot
- NLP command parser (structured prompt → backend action)
- Authentication: Telegram user ID allowlist
- Start simple (keyword commands) before adding NLP

---

### 4.4 Plan-vs-Execution Analytics (Priority 4)

**Purpose:** Close the loop between pre-trade planning and actual performance.

**What is already in place:**
- `followed_plan` boolean on each trade
- `trade_plan_id` foreign key linking a trade to a pre-trade plan
- Daily plans with `allowed_setups`, `behavioral_focus`, `max_trades`

**What this feature adds:**
- Analytics comparing followed-plan vs deviated trades (win rate, avg R, PnL)
- Planned vs unplanned trade performance breakdown
- Plan adherence score as a coaching input signal
- "Has plan" vs "no plan" performance differential
- Daily review → daily plan comparison (how many allowed setups were respected)

**Why it matters:**
- Currently the coaching engine uses raw mistake flags
- Adding plan adherence signal improves the diagnostic quality: "your losses were 3x worse on unplanned trades" is more actionable than "you had 12 FOMO trades"

---

### 4.5 AI Provider Abstraction (Later)

**Current state:**
- Coaching uses Anthropic Claude API exclusively
- `ANTHROPIC_API_KEY` env var controls availability
- Falls back to rule-based analysis if key is missing

**Future option (not for current phase):**
- Abstract the AI provider behind a service interface
- Support Anthropic (default), OpenAI (GPT-4o), Google Gemini as alternatives
- Allow per-account or per-request provider selection
- Keep prompt templates provider-agnostic where possible

**Why deferred:**
- The current Anthropic implementation works well and produces high-quality coaching
- Provider switching adds complexity without immediate user value
- Should only be pursued if: (a) Anthropic cost becomes a concern, or (b) a specific model capability from another provider is needed

---

## 5. Implementation Sequencing

```
Current (Done)
  └── MVP+ with full journal, dashboard, FTMO, coaching, daily workflow

Next batch (Refinements)
  ├── Trade log pagination
  ├── Per-symbol/session analytics
  └── broker_utc_offset UI configuration

Expansion Phase 1 (DONE — backend only)
  └── MT5 live sync Phase 1
        - MT5Connector + MT5SyncService
        - manual trigger API endpoint
        - sync audit log

Expansion Phase 1b (NEXT)
  └── MT5 live sync Phase 2
        - background scheduler (APScheduler)
        - open position tracking
        - frontend sync UI

Expansion Phase 2
  └── Telegram notifications (push-only)
        - FTMO limit warnings
        - import/sync success
        - daily prompts

Expansion Phase 3
  └── Telegram structured write-in
        - trade plan creation
        - journal notes
        - account status queries

Expansion Phase 4
  └── Plan-vs-execution analytics
        - followed_plan vs deviated breakdown
        - plan adherence coaching signal

Later
  └── MT4 EA bridge
  └── AI provider abstraction
  └── Chart screenshot attachments
  └── Multi-user / authentication
```

---

## 6. Non-Goals (Current Phase)

- Multi-user authentication or role-based access
- Real-time WebSocket streaming of trade data
- Automated trade execution or signals
- Mobile-native app (responsive web is sufficient for now)
- Social/sharing features

---

## 7. Known Constraints and Risks

| Constraint | Notes |
|---|---|
| MT5 live sync is Phase 1 only (backend, manual trigger) | Phase 1 sync is backend-only; use `POST /api/v1/accounts/{id}/mt5-sync`. Requires Windows + MetaTrader5 package. Phase 2 (scheduled, frontend UI) is deferred. |
| No authentication | Single-user local deployment. Do not expose to public internet without adding auth. |
| Coaching quality depends on trade data quality | Sparse trades or missing setup_type values reduce coaching signal. |
| MT4 live sync path is fragile | EA-based bridges are platform-version-sensitive and hard to maintain. |
| Telegram bot Phase B requires NLP robustness | Poorly structured commands can create bad journal data silently. |
| plan_adherence analytics require consistent plan linking | If traders don't link plans to trades, the signal is weak. |
