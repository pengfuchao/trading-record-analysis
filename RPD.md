# Product Requirements Document
## Trading Record Analysis — MVP+ State and Future Roadmap

**Document version:** 2.4  
**Last updated:** 2026-04-28  
**Status:** Feature-complete for current scope; remaining work is operational hardening and data-durability improvements

---

## 1. Product Purpose

A professional trading journal and account analytics platform for discretionary traders operating in prop firm (FTMO-style) environments. The system helps traders:

- Understand *why* they lose money — analysis errors vs execution errors vs psychology
- Identify which setups perform best and which should be paused
- Monitor prop firm challenge survival in real time (daily loss limit, overall drawdown)
- Build consistent daily pre-market and post-market habits
- Generate periodic AI coaching insights from trade history

---

## 2. Current MVP+ State (as of 2026-04-28)

### 2.1 What Is Built and Working

| Module | Feature | State |
|---|---|---|
| Accounts | Create, select, edit, delete (broker, balance, platform, prop firm, phase) | Complete |
| Import | MT4 + MT5 CSV multi-format parsing, preview, dedup strategies, recompute R/session | Complete |
| Trade Log | Server-side pagination, filterable list (symbol, result, date range) | Complete |
| Trade Detail | Full execution data, journal enrichment (flags, tags, reflection), inline edit | Complete |
| Trade Plans | CRUD + manual link to executed trades + setup type dropdown from Setup Library | Complete |
| Setup Library | Global setup definitions CRUD (backend + frontend), setup type autocomplete in trade edit + trade plans | Complete — screenshot upload deferred |
| Dashboard | Equity curve, drawdown chart, core analytics (win rate, PF, expectancy, R, drawdown, Sharpe, Sortino, streaks) | Complete |
| FTMO Panel | Daily loss used vs limit, overall drawdown vs limit, status badges, progress bars, 1-min auto-refresh | Complete |
| Daily Plans | Pre-market plan CRUD (bias, symbols, setups, rules) | Complete |
| Daily Reviews | Post-market review CRUD (PnL, mistakes, emotional summary, reflection) | Complete |
| Mistake Analysis | Mistake frequency/cost ranking on dashboard | Complete |
| Plan-vs-Execution | Planned/unplanned + followed/deviated comparison, planned R:R vs realized R, coaching signals, dashboard panels | Complete |
| R:R Trend | Weekly R:R realization trend chart on dashboard, trend signal (improving/worsening/stable), coaching integration | Complete |
| Setup Analytics | Per-setup win rate, avg PnL, profit factor, ranking | Complete |
| AI Coaching | Weekly review via Anthropic Claude API, rule-based fallback, review history | Complete |
| MT5 Sync | Config UI, manual trigger, run history, open positions, partial close reconstruction, background polling | Complete |
| Telegram | Push notifications (sync, FTMO, coaching) + structured write-in (/plan, /journal, /status, /ping) | Complete |

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
| Per-symbol / per-session analytics tabs | Medium | Dashboard shows account-level only. Segmented analytics by symbol/session would improve coaching signal quality. |
| Chart screenshot upload | Low | `screenshot_examples` field exists in schema. Requires file storage (Supabase Storage / S3). |
| Setup library auto-suggestions from import | Low | New setup names from CSV don't auto-populate the library; trader must add them manually. |
| `broker_utc_offset` UI configuration | Low | Currently per-MT5-config. Surfacing it more prominently would help session classification accuracy for non-UTC brokers. |
| Manual trade entry form | Low | Trades currently come from CSV import or MT5 sync only. |

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

#### Phase 1b — Frontend UI (IMPLEMENTED 2026-04-16)

Added `/mt5-sync` page (accessible from sidebar) with:
- **Connection config form**: login, broker server, UTC offset, terminal path; save/update button
- **Password note**: computed env var name shown in UI (`MT5_<ACCOUNT_ID_UPPER>_PASSWORD`)
- **Manual sync trigger**: date range picker + Sync Now button with loading state
- **Sync result card**: new/updated/skipped/deals_fetched/open_positions counts or error message
- **Run history table**: last 10 runs with started_at, status badge, date range, counts, error
- **Last sync time**: shown prominently in header of run history section
- SWR invalidation after successful sync (trades, analytics, FTMO, mistakes, open-positions)

#### Phase A — Deeper Sync: Open Positions (IMPLEMENTED 2026-04-18)

Each manual MT5 sync now also fetches currently open positions via `mt5.positions_get()`.

**What is implemented:**
- `MT5OpenPositionModel` ORM model + migration 009 (`mt5_open_positions` table)
- `MT5Connector.fetch_open_positions()` — calls `mt5.positions_get()`, returns normalized dicts
- `MT5SyncService._refresh_open_positions()` — deletes the previous snapshot and inserts the fresh list (replace-wholesale strategy ensures closed positions disappear after the next sync)
- `MT5SyncService.get_open_positions()` — query helper used by the API
- `SyncResult.open_positions_count` — surfaced in the sync response
- `GET /accounts/{id}/open-positions` — returns the latest snapshot as `OpenPositionsResponse`
- `/mt5-sync` page: new **Open Positions** section — table with symbol, side, lots, entry, current price, SL/TP, floating PnL, opened_at, and a total floating PnL footer row

**Idempotency / staleness:**
- PK is `(account_id, ticket)` — same position ticket across syncs maps to the same row
- On every sync, all rows for the account are deleted then re-inserted from the live MT5 list
- A closed position disappears automatically after the next sync — no manual cleanup needed

**What remains deferred (Phase 2):**
- Background polling (APScheduler) — `polling_interval_minutes` column exists as placeholder
- DEAL_ENTRY_INOUT (partial close/hedge reconstruction)
- Richer real-time position monitoring or streaming

#### Phase B — Partial Close Reconstruction (IMPLEMENTED 2026-04-18)

`DEAL_ENTRY_INOUT` (partial close) deals are now included alongside `DEAL_ENTRY_OUT` deals:
- PnL is the sum across all exit deals (correct for partials)
- Exit price is the volume-weighted average across all exit deals
- Exit time is the last exit deal's timestamp
- `partial_close_count` field records how many INOUT deals were present

#### Phase C — Background Polling (IMPLEMENTED 2026-04-18)

APScheduler-based background sync runs automatically per account:

- `apscheduler>=3.10` added to `requirements.txt`
- `services/mt5_scheduler.py` — `MT5PollingScheduler` singleton; one `IntervalJob` per enabled account; overlap protection via in-memory `_running` set; Telegram notification on error only (no spam on success)
- `api/app.py` — FastAPI lifespan context manager starts/stops scheduler at app boot/shutdown
- Config route (`POST /mt5-config`) calls `scheduler.reload_account()` immediately after save — interval/enabled changes take effect without restart
- Status endpoint (`GET /mt5-sync/status`) now returns `polling_interval_minutes` and `next_poll_at` (next APScheduler fire time)
- `triggered_by` column in `mt5_sync_runs` differentiates `"manual"` from `"scheduled"` runs — run history shows a Source badge per row
- Frontend `/mt5-sync` page: polling interval + enabled checkbox added to config form; new "Background Polling" status panel shows active/disabled badge, interval, and next scheduled run time

**No DB migration needed** — `polling_interval_minutes` and `enabled` columns existed since migration 006.

**Deferred:**

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

#### Phase A — Notification Mode (Priority 2) — IMPLEMENTED 2026-04-17

Push-only Telegram notifications. No bot commands or write capability.

**What is implemented:**
- `TelegramNotifier` service (`services/telegram_notifier.py`) — thin singleton wrapping `requests.post` to Telegram Bot API
- MT5 sync result notification (success + failure) — fires after every manual sync
- FTMO risk/status-change alert — triggered via `POST /accounts/{id}/ftmo-check`; in-memory state change deduplication prevents spam
- Coaching review notification — fires after successful AI-generated reviews only
- Test ping endpoint: `POST /api/v1/telegram/test-ping`
- Config: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, optional `TELEGRAM_ENABLED=false` flag

**Deferred to Phase B:**
- Background/scheduled FTMO checks (configure externally using `POST /ftmo-check`)
- Per-account Telegram chat ID configuration
- FTMO state persistence across server restarts (current: in-memory only)
- Daily plan reminders / EOD review prompts

#### Phase B — Structured Write-In Mode (Priority 3) — IMPLEMENTED 2026-04-17

Strict key:value command intake via Telegram webhook. No natural-language parsing.

**What is implemented:**
- `POST /api/v1/telegram/webhook` — Telegram webhook receiver with chat ID guard
- `services/telegram_command_parser.py` — pure parser: `parse_command()`, `coerce_bool()`, `coerce_float()`, `coerce_list()`
- `/plan` command → creates a `TradePlan` via `TradePlanRepository`
- `/journal` command → updates trade enrichment fields via `TradeRepository` (requires `trade_id`)
- `/status` command → returns account + FTMO status snapshot via `AccountAnalytics.compute_ftmo_status()`
- `/ping` command → liveness check
- Validation error replies with usage examples
- Not-found and unknown-command replies

**Deferred to Phase C:**
- Natural-language parsing
- Multi-step conversational flows
- Broker ticket → trade_id lookup
- `/link` plan-to-trade command
- Per-user Telegram auth (user ID allowlist)
- Scheduled reminders and attachment commands

---

### 4.4 Plan-vs-Execution Analytics (Priority 4) — IMPLEMENTED 2026-04-17 / Extended 2026-04-21

**Purpose:** Close the loop between pre-trade planning and actual performance.

**What is implemented:**

- `GET /accounts/{id}/plan-adherence` — endpoint extended with `rr_comparison` field:
  - **Dimension 1 (trade_plan_id):** planned vs unplanned trade performance (win rate, avg PnL, profit factor)
  - **Dimension 2 (followed_plan):** self-reported plan adherence vs deviations
  - **Intersection:** linked-but-deviated count (wrote a plan, then broke it)
  - **Planned R:R vs Realized R (`rr_comparison`):** compares `TradePlan.planned_rr` against `Trade.actual_r_multiple` for all trades with a linked plan, a positive planned_rr, and a non-null actual_r_multiple
  - Pre-computed coaching signal sentences in `coaching_signals[]` and `rr_comparison.coaching_signals[]`
- **Dashboard "Plan vs Execution" section** — shows plan linkage/adherence panels + `RRComparisonPanel`:
  - Avg Planned R:R / Avg Realized R / Avg Shortfall / R:R Realization %
  - Target-hit progress bar (% of trades that met or exceeded planned R:R)
  - R:R-specific coaching signals (purple badge)
- **Coaching integration** — `CoachingContext` now carries R:R metrics; AI prompt includes a `PLANNED R:R vs REALIZED R` section; fallback diagnosis and improvement sections use R:R realization as a primary signal when < 80%

**Inclusion criteria for R:R comparison:**
- Trade must have a linked plan (`trade_plan_id` is not None)
- Linked plan must have `planned_rr > 0`
- Trade must have `actual_r_multiple` set
- Minimum 3 qualifying trades before coaching signals are generated
- Negative-R trades are always included (diagnostically important)

**Implemented (2026-04-21):**
- Per-setup planned vs realized R breakdown — see Phase 6 below

**Deferred (follow-up phases):**
- R:R realization trend over time (improving / worsening)
- Target-hit vs stop-hit decomposition (requires entry quality tagging)
- Entry quality vs exit quality decomposition
- Daily plan `allowed_setups` vs actual setups taken enforcement

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

Expansion Phase 1 (DONE)
  └── MT5 live sync — backend + frontend UI
        - MT5Connector + MT5SyncService
        - manual trigger API endpoint
        - sync audit log
        - /mt5-sync page (config form, sync trigger, run history)

Expansion Phase A (DONE 2026-04-18)
  └── MT5 deeper sync — open positions
        - MT5OpenPositionModel + migration 009
        - MT5Connector.fetch_open_positions()
        - MT5SyncService.refresh/get open positions
        - GET /accounts/{id}/open-positions endpoint
        - /mt5-sync open positions table (live floating PnL)

Expansion Phase B (DONE 2026-04-18)
  └── MT5 partial close reconstruction
        - DEAL_ENTRY_INOUT included in out_deals aggregation
        - volume-weighted exit price across partial exits
        - partial_close_count field in reconstructed position

Expansion Phase C (DONE 2026-04-18)
  └── MT5 background polling
        - apscheduler BackgroundScheduler, one job per enabled account
        - overlap protection via in-memory _running set
        - reload_account() called on config save (no restart needed)
        - Telegram error-only notification for scheduled runs
        - /mt5-sync page: polling controls + status panel + Source column in history

Expansion Phase 2 (DONE 2026-04-17)
  └── Telegram notifications — Phase 1 (push-only)
        - MT5 sync success/failure
        - FTMO risk/status-change alerts
        - Coaching review generated (AI only)
        - test-ping endpoint

Expansion Phase 3 (DONE 2026-04-17)
  └── Telegram structured write-in — Phase 2
        - webhook intake + chat ID guard
        - /plan → create trade plan
        - /journal → update trade enrichment
        - /status → account + FTMO snapshot
        - /ping → liveness check

Expansion Phase 4 (DONE 2026-04-17)
  └── Plan-vs-execution analytics
        - GET /plan-adherence: planned vs unplanned + followed vs deviated
        - coaching_signals[] pre-computed per-account
        - dashboard Plan vs Execution section
        - coaching context + AI prompt + fallback extended with adherence signals

Expansion Phase 5 (DONE 2026-04-21)
  └── Setup Library frontend CRUD
        - /setups page: inline "New Setup" form (blue border panel)
        - each setup card: Edit button (expands inline form) + Delete with inline confirmation
        - SWR mutate("setups") invalidates list after create/edit/delete
        - setup_id auto-generated as kebab slug from name (editable before save)
        - existing setup stats/analytics display fully preserved
        - Deferred: screenshot_examples (no image upload infrastructure in v1)

Expansion Phase 5b (DONE 2026-04-21)
  └── Setup Library integration into Trade Plans create/edit
        - SetupTypeSelect shared component (frontend/components/SetupTypeSelect.tsx)
        - dropdown populated from GET /setups (same SWR key "setups" — shared cache)
        - stores setup.name as setup_type string (analytics unaffected)
        - "Custom…" fallback preserves free-text entry
        - old plans with free-text values render correctly in the dropdown

Consolidation pass (DONE 2026-04-21)
  └── Full project audit: inventory, stability review, doc sync, QA baseline
        - README rewritten to match actual feature state
        - RPD updated to v2.1 with all completed phases
        - Known limitations and risk notes updated
        - Manual regression checklist added to README

Expansion Phase 6 (DONE 2026-04-21)
  └── Per-setup planned R:R vs realized R breakdown
        - SetupStats gains: rr_sample_count, rr_avg_planned_rr, rr_avg_actual_r,
          rr_avg_shortfall, rr_realization_pct, rr_pct_met_target
        - SetupReport gains: ranked_by_rr_realization (setups with rr_sample_count >= 1)
        - SetupAnalyzer._compute_stats() computes R:R per setup using trades with
          linked plan + planned_rr > 0 + actual_r_multiple (same inclusion as account-level)
        - get_setup_report() route now enriches trades with planned_rr from linked plans
        - Coaching context: worst_rr_setup / best_rr_setup added; fallback improvement
          names the worst-leakage setup; AI prompt has PER-SETUP R:R EXECUTION block
        - Frontend: R:R Real. % column inline in SetupCard header (color-coded)
        - Frontend: SetupRRTable ranked table on Setup Library page (n, planned R,
          realized R, shortfall, realization %, target hit %; signals at n >= 3)

Phase 7 (DONE 2026-04-25)
  └── Ops hardening + onboarding fix
        - README rewritten (correct install paths, two-mode setup guide)
        - start-local-backend.ps1 / .sh startup scripts
        - alert() calls replaced with inline error banners (daily/page.tsx)
        - Dashboard empty-state onboarding form (CreateAccountCard)
        - datetime.utcnow() → datetime.now(timezone.utc) everywhere

Phase 8 (DONE 2026-04-25)
  └── HTTP route test coverage
        - 59 route tests across 8 groups (Health, Accounts, Trades, Trade Plans,
          Analytics, Daily Plans, Setups, Coaching)
        - FastAPI TestClient + dependency_overrides + SQLite in-memory
        - All remaining datetime.utcnow() calls eliminated (sweep complete)

Phase 9 (DONE 2026-04-26)
  └── MT5 scheduler resilience
        - Alert cooldown: repeated scheduled failures suppressed 4h after first alert;
          resets automatically on sync success
        - Polling jitter: 0–30s random start delay on job registration to prevent lockstep
        - lookback_days column (migration 010) + API field + scheduler wired
        - Startup advisory log for single-worker constraint

Phase 10 (DONE 2026-04-26)
  └── Export + ops closure
        - lookback_days exposed in /mt5-sync config UI form
        - GET /accounts/{id}/trades/export/csv (all matching trades, same filters as list, no pagination)
        - Export CSV button on Trade Log page (filter-aware, plain <a download>)
        - backup.ps1 + backup.sh (pg_dump → timestamped files in backups/)

Phase 11 (DONE 2026-04-26)
  └── CI hardening + restore
        - Postgres 15 CI job: alembic upgrade head + 9 migration/ORM smoke tests;
          catches schema issues SQLite silently misses
        - Frontend E2E: Playwright @1.59, 8 smoke tests, mocked API, CI job;
          verifies pages render and sidebar navigation works without a real backend
        - restore.ps1 + restore.sh (symmetric with backup scripts; confirmation prompt;
          restart hint on success)

Phase 12 (DONE 2026-04-27)
  └── SL/TP enrichment + ops hardening
        SL/TP from MT5 orders (Phase 2 deferral resolved):
          - MT5Connector.fetch_orders_sl_tp() — history_orders_get lookup keyed to
            earliest order per position; non-fatal on failure
          - reconstruct_positions updated to accept orders_sl_tp kwarg; fills SL/TP
            from order, falls back to deal attribute
          - MT5SyncService.sync_account wired up; synced trades now populate
            stop_loss, take_profit, actual_r_multiple
          - Trade Log SL/TP columns added; sort order fixed (exit_datetime DESC)
        Historical SL/TP backfill endpoint (MT5-based):
          - POST /accounts/{id}/mt5-sync/backfill-sl-tp — 2-year window by default
          - Queries all trades with stop_loss IS NULL; matches by position_id
          - Diagnostic counts: updated / sl_zero / no_order_found / r_computed
          - Frontend: Backfill SL/TP panel on /mt5-sync page
        CSV SL/TP enrichment flow (FTMO/MT5 CSV):
          - POST /accounts/{id}/import/enrich-sl-tp — exact trade_id match
          - NULL-only fill; idempotent; R recomputed on SL fill
          - Frontend: Enrich SL/TP from CSV panel on /import page
        Closed ops gaps (from 2026-04-26 doc):
          - CORS_ORIGINS: ${CORS_ORIGINS:-...} in docker-compose (was hardcoded)
          - Telegram route tests: 25 HTTP-layer tests added (commit 722bf1f)
          - Empty-state onboarding: /trades, /plans, /daily, /coaching now show
            helpful guidance when no data exists (commit 4ee56b2)
        Ops hardening (this session):
          - reset-data.sh / reset-data.ps1: safe wrapper for docker compose down -v
            (auto-backup + "type reset to continue" prompt)
          - README: ⚠️ warning on docker compose down -v; SL/TP workflow section
          - _lifespan: WARN log if UVICORN_WORKERS != 1 (MT5 sync correctness)

Phase 13 (DONE 2026-04-28)
  └── Reliability hardening: runtime_state persistence, password indicator, SL/TP integrity
        R5 — Persist FTMO + scheduler cooldown state across restarts:
          - migration 011: runtime_state(scope, kind, value_json, updated_at) table
          - services/runtime_state.py: get_state / set_state / delete_state helpers
          - mt5_scheduler.py: lazy-load + persist _error_suppress_until (cooldown);
            clear on sync success; log WARN on DB failure (non-fatal)
          - telegram_notifier.py: lazy-load + persist _last_ftmo_status (FTMO dedup);
            persist on status change; non-fatal on DB failure
          - 20 integration tests (service CRUD + simulated restart scenarios)
        R6 — MT5 password env var presence indicator:
          - GET /accounts/{id}/mt5-config/password-status → {env_var_name, present}
          - password value never returned; only boolean presence check
          - frontend /mt5-sync: green ✓ Present / red ✗ Not found badge in password
            note block; refreshes after config save
          - 8 route tests covering missing/present/empty var, 404, convention variants
        SL/TP null-overwrite data integrity fix:
          - bug: save_batch_import(update_broker) applied _BROKER_FIELDS blindly;
            _BROKER_FIELDS includes stop_loss, take_profit, actual_r_multiple;
            MT5 sync windows miss older orders → incoming sl/tp=None → DB values wiped
          - fix: _SL_TP_PROTECTED_FIELDS guard in update_broker loop — incoming None
            does not overwrite existing non-null; incoming non-null still updates
          - 7 regression tests including full enrich → sync → verify sequence

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
| MT5 live sync Phase C (background polling) implemented | APScheduler starts at app boot and schedules one IntervalJob per enabled account. Partial closes (INOUT) are aggregated into single trade records. Alert cooldown (4h) + jitter (0–30s) prevent spam and lockstep polling. |
| CI now covers both SQLite and Postgres 15 | `postgres-migration-check` job: runs `alembic upgrade head` + 9 ORM smoke tests on real Postgres. SQLite job remains for fast unit + integration test feedback. |
| Backup/restore scripts available | `backup.ps1`/`backup.sh` + `restore.ps1`/`restore.sh` at repo root. Must be run manually — no automated schedule yet. |
| No authentication | Single-user local deployment. Do not expose to public internet without adding auth. |
| Coaching quality depends on trade data quality | Sparse trades or missing setup_type values reduce coaching signal. |
| MT4 live sync path is fragile | EA-based bridges are platform-version-sensitive and hard to maintain. |
| Telegram bot Phase B requires NLP robustness | Poorly structured commands can create bad journal data silently. |
| plan_adherence analytics require consistent plan linking | If traders don't link plans to trades, the signal is weak. |
| CORS_ORIGINS configurable | `${CORS_ORIGINS:-http://localhost:3000}` in `docker-compose.yml` — override in `.env` for remote deploys. |
