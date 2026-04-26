# Project State — 2026-04-27

## Summary

Full reassessment pass after 14 commits landed post-2026-04-26 doc.
The project is at **9 / 10 maturity** for its stated scope (single-user, local-trust,
personal trading journal). Feature surface is closed. Test coverage is real. The
remaining 1 point is operational trust — specifically data durability and a few
low-cost stability improvements.

**Key fact:** the docs were stale at the start of this session. Three of the four gaps
listed in the 2026-04-26 state doc were already closed, and a significant new feature
surface (SL/TP enrichment — 2 endpoints, 1 UI panel) had landed without being documented.
This doc records the actual state as of 2026-04-27.

---

## What Was Completed After the 2026-04-26 Doc

### Closed gaps (were listed as open in 2026-04-26 doc)

| Gap | Status | Commit |
|---|---|---|
| `CORS_ORIGINS` hardcoded in compose | **Closed** — `${CORS_ORIGINS:-...}` in compose | `30ec02c` |
| Telegram webhook untested at HTTP layer | **Closed** — 25 route tests added | `722bf1f` |
| Empty-state onboarding on /trades, /plans, /daily, /coaching | **Closed** | `4ee56b2` |

### New work (not in 2026-04-26 doc at all)

#### Fix: MT5 SL/TP from orders (Phase 2 deferral resolved)
Root cause: `history_deals_get()` deals do not carry `sl`/`tp` — those live on trade
orders. The Phase-2 comment in `mt5_connector.py` acknowledged this deferral. Now
implemented.

| What | Detail |
|---|---|
| `MT5Connector.fetch_orders_sl_tp()` | Calls `history_orders_get`, builds `{position_id: (sl, tp)}` lookup keyed to the earliest order per position. Non-fatal: returns `{}` on any failure so sync continues without SL/TP rather than aborting. |
| `reconstruct_positions` updated | Accepts optional `orders_sl_tp` kwarg; uses order-derived SL/TP when available, falls back to deal attribute. |
| `MT5SyncService.sync_account` updated | Calls `fetch_orders_sl_tp` after `fetch_deals`, passes result into `reconstruct_positions`. Synced trades now populate `stop_loss`, `take_profit`, `actual_r_multiple`. |
| Trade Log UI | SL and TP columns added; null values shown as dimmed. |
| Trade log sort order | `get_by_account_filtered` now orders by `exit_datetime DESC` (newest first). CSV export remains ASC for chronological output. |

Files: `services/mt5_connector.py`, `services/mt5_sync_service.py`,
`services/trade_repository.py`, `frontend/app/trades/page.tsx` — commit `afa7248`

---

#### Feat: Historical SL/TP backfill endpoint (MT5-based)
Root cause: `sync_account` only processes trades within the deal-fetch window (7d
scheduled / 30d manual). Historical trades already in DB are never re-queried. This
endpoint provides a one-time wide-window backfill path.

**Endpoint:** `POST /accounts/{id}/mt5-sync/backfill-sl-tp`

- Fetches `history_orders_get` for a configurable date range (default: 2 years back)
- Queries **all** trades for the account with `stop_loss IS NULL`
- Matches by position ID: `trade.trade_id == str(order.position_id)`
- Writes `stop_loss` / `take_profit` / `actual_r_multiple` for each match
- Never creates new trades, never overwrites existing SL/TP
- Returns diagnostic counts distinguishing three failure modes:
  - `updated` — SL found on order, written (R recomputed if prices exist)
  - `sl_zero` — order found but `SL=0.0` (broker did not set SL on order)
  - `no_order_found` — no order for this position in the requested date window
- Uses same per-account overlap lock as `sync_account` (cannot run concurrently with a live sync)

Files: `services/mt5_sync_service.py`, `api/schemas/mt5_sync.py`,
`api/routes/mt5_sync.py`, `src/test/integration/test_mt5_sync.py` (35 tests total) — commit `457f34c`

---

#### Feat: CSV-based SL/TP enrichment flow (FTMO/MT5 CSV)
Root cause: MT5 broker API returns `SL=0.0` on most historical deals. FTMO and
MetaTrader CSV exports *do* contain S/L and T/P columns. This provides a safe enrichment
path using those exports.

**Endpoint:** `POST /accounts/{id}/import/enrich-sl-tp`

- Accepts a CSV file parsed via the existing `csv_parser`
- Matches existing trades by exact `trade_id` (MT5 position number = `trade_id` in DB;
  MT4 ticket = `trade_id`). No heuristic matching.
- Safety guarantees:
  - Never creates new trades (enrichment only)
  - Never overwrites existing `stop_loss` or `take_profit` (NULL-only fill)
  - `actual_r_multiple` is recomputed immediately when `stop_loss` is filled

**Frontend:** "Enrich SL/TP from CSV" panel on `/import` page (always visible when
account selected; file upload → result summary with SL/TP/R counts).

Files: `services/trade_repository.py` (`enrich_sl_tp`), `api/schemas/imports.py`,
`api/routes/imports.py`, `frontend/lib/api.ts`, `frontend/app/import/page.tsx`,
`src/test/integration/test_repositories.py` (39 tests total) — commit `c062a6c`

---

## SL/TP Enrichment Playbook (operator reference)

Two paths exist. Use exactly one depending on what you have available:

| If you have… | Use… | Notes |
|---|---|---|
| A fresh FTMO or MetaTrader CSV export with S/L and T/P columns | **CSV enrichment** — Import page → "Enrich SL/TP from CSV" | No MT5 terminal needed. Exact `trade_id` match. Works offline. |
| An active MT5 terminal (Windows) and need to fill historical trades | **MT5 backfill** — `/mt5-sync` page → Backfill button (or `POST .../backfill-sl-tp`) | Requires local Windows backend + MT5 running. Default 2-year window. May take several minutes; do not click twice. |

Both paths are NULL-only fills — running one after the other is safe and idempotent for
any trade that already has SL/TP.

---

## Current Test Coverage

| Layer | Count | Notes |
|---|---|---|
| Unit (core logic) | ~435 tests | metrics, analytics, parsers, validators, converters |
| Integration (repositories) | ~39 tests | CRUD + enrich_sl_tp |
| Integration (import pipeline) | ~15 tests | CSV parse + output writer |
| Integration (MT5 sync) | ~35 tests | connector/sync/backfill via mocked MT5Connector |
| HTTP routes | 59 + 25 = **84 tests** | all router groups including Telegram (722bf1f) |
| Postgres migration + ORM | 9 tests (skipped in SQLite) | schema check + CRUD on real Postgres 15 |
| Frontend E2E | 8 tests | Playwright, mocked API, Chromium |
| **Total backend (SQLite run)** | **≈ 557 passed, 9 skipped** | |

---

## Current CI Jobs (all green)

| Job | Trigger | What it catches |
|---|---|---|
| `backend-tests` | push / PR | Unit + integration regressions (SQLite) |
| `postgres-migration-check` | push / PR | Migration chain breaks, Postgres ORM drift |
| `frontend-typecheck` | push / PR | TypeScript type errors |
| `frontend-e2e` | push / PR | Frontend page load crashes, broken navigation |

---

## Migration Chain

010 migrations (001–010), all intact.
Latest: `010_mt5_lookback_days.py` — `lookback_days INTEGER NOT NULL DEFAULT 7` on `mt5_sync_configs`.

---

## What Remains Rough / Open Issues

| Issue | Severity | Notes |
|---|---|---|
| **No automated backup schedule; no off-host copy** | **High** | One backup file on disk in `backups/`. `docker compose down -v` destroys all data. Scripts exist but must be triggered manually. |
| **Two SL/TP backfill paths, no UI playbook** | Medium | Both are safe, but operator must know which to use (see playbook above). |
| **`docker compose down -v` has no guardrail** | Medium | One CLI typo destroys all data. No confirmation prompt, no auto-backup trigger. |
| Stale `trading_data.db` / `trading_data_backup.db` at repo root | Low | Gitignored (`*.db`) so safe, but misleading in a Postgres-only project. Delete them. |
| Single-worker requirement not runtime-enforced outside Docker | Low–Medium | `docker-entrypoint.sh` and startup scripts pin `--workers 1`. No assertion in `_lifespan`. Running multi-worker silently corrupts MT5 sync state. |
| In-memory FTMO dedup + scheduler cooldown reset on restart | Low–Medium | First run after restart re-fires FTMO alert; cooldown timer resets. Trust in Telegram channel is affected. |
| Frontend E2E tests use mocked API only | Low | No real-data UI integration coverage — acknowledged; lower priority until a real regression slips through. |

---

## Operating Modes (Unchanged)

| Mode | Frontend | Backend | Database |
|---|---|---|---|
| **Docker full stack** (journaling, no MT5) | Docker :3000 | Docker :8000 | Docker :5432 |
| **Local Windows MT5 sync** | Docker :3000 | Native Windows :8000 | Docker :5432 |

Use `start-local-backend.ps1` (Windows PowerShell) for Mode 2.
MT5 passwords: `MT5_<ACCOUNT_ID_UPPER_UNDERSCORED>_PASSWORD` env var only — never stored in DB.

**Alembic note:** use `alembic upgrade head` (binary), **not** `python -m alembic upgrade head`.
The local `alembic/` directory shadows the installed package when Python module path
includes the repo root. The binary bypasses this entirely.

---

## Refreshed Roadmap

Old "Next Recommended Direction" (CORS / Telegram tests / empty-state) is **fully done**.
Below is the next priority queue.

### R1 — Backup discipline *(data durability — do this first)*
- **Problem:** Single host, single volume, single manual backup = real data-loss risk.
- **Concrete bar:** Documented Task Scheduler (Windows) + cron (WSL) one-liners for daily `backup.sh`; off-host copy step (OneDrive / external drive); one verified `restore.sh` drill; rotation policy (14 daily + 12 monthly).
- **No code required.** ~1 hour of docs + setup.
- **Category:** data durability.

### R2 — Doc sweep: SL/TP enrichment playbook
- **Problem:** README and RPD do not describe the new enrichment surface or when to use which path.
- **Concrete bar:** README "Core Workflow" gains "If SL/TP shows blank in Trade Log" subsection; UI panels get one-line guidance; RPD Phase 12 entry added.
- **Category:** ops/deployment + UX/onboarding.

### R3 — `docker compose down -v` guardrail
- **Problem:** Most likely accidental data-loss path.
- **Concrete bar:** A `reset-data.sh` / `Makefile` target that auto-runs `backup.sh`, prompts "type 'reset' to continue", then runs `down -v`. README marks the bare command as ⚠️.
- **Category:** ops/deployment.

### R4 — Single-worker startup enforcement
- **Problem:** Silent correctness failure if backend ever starts with `--workers >1`.
- **Concrete bar:** `_lifespan` logs WARN (or refuses) if `UVICORN_WORKERS != 1`; optionally gated on `MT5_ENFORCE_SINGLE_WORKER=true`.
- **Category:** stability/quality.

### R5 — Persist FTMO + scheduler cooldown state across restarts
- **Problem:** Restart-induced false alerts and cooldown reset degrade trust in Telegram.
- **Concrete bar:** Small `runtime_state` table keyed on `(account_id, kind)`, migration 011. Scheduler error cooldown and FTMO last-status read from DB at boot.
- **Category:** stability/quality.

### R6 — MT5 password env var presence indicator in `/mt5-sync` UI
- **Problem:** Silent "no password env var found" is the #1 first-setup failure.
- **Concrete bar:** `GET /accounts/{id}/mt5-config/password-status` returns `{present: bool}`. UI shows green ✓ / red ✗ next to computed env var name.
- **Category:** UX/onboarding.

### R7 — SL/TP backfill UX (async / progress if needed)
- **Problem:** 2-year window blocks HTTP and the per-account sync lock with no progress signal.
- **Concrete bar:** (a) UI copy "may take several minutes — do not click twice"; (b) async background task with `mt5_sync_runs` row of kind `"backfill"` only if the user actually feels pain with (a).
- **Category:** MT5/runtime.

### R8 — Real-data Playwright E2E (defer)
- **Problem:** Mocked tests don't catch API-shape regressions.
- **Concrete bar:** One Playwright spec that boots the real Docker backend, seeds a fixture account, clicks dashboard / trades / coaching.
- **Defer until:** a real-data regression slips past mocked tests.
- **Category:** stability/quality.

---

## Decision Memo

| Question | Answer |
|---|---|
| Current maturity | **9 / 10** for single-user, local-trust scope |
| Good enough for daily use? | **Yes** — with the caveat: do not trust the Docker volume to survive without an off-host backup |
| Biggest weakness | Backup/recovery is a script, not a discipline |
| Best next improvement | R1 — backup discipline (no code, highest impact-per-hour) |
| What should wait | Auth, AI provider abstraction, screenshots, MT4 bridge, Telegram NLP, async backfill, real-data E2E |
| Manual drills needed | (1) `restore.sh` rehearsal on a throwaway DB; (2) verify `start-local-backend.ps1` stops the Docker backend; (3) MT5 backfill on a small window first to validate diagnostic counts; (4) copy `backups/` off-host |
