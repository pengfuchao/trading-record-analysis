# Project State — 2026-04-25 (after Phase 8)

## What Was Completed in Phase 8 (HTTP Route Test Coverage)

### New test file: `src/test/integration/test_routes.py`

59 route tests across 8 groups. All pass in under 3 seconds.

| Group | Tests | What's covered |
|---|---|---|
| Health | 1 | GET /health → 200 |
| Accounts | 9 | list, create, get, patch, delete, 404s |
| Trades | 12 | list (empty/filtered/paginated), create, get, patch journal, delete, 404s |
| Trade Plans | 11 | list, create, get, patch, delete, link/unlink (both sides), get linked trades |
| Analytics | 10 | analytics (empty/with trades/PnL), FTMO status shape, plan adherence, mistakes, 404 propagation |
| Daily Plans | 6 | list, create, duplicate-date 409, get by id, 404, delete |
| Setups | 7 | list, create, get, patch, delete, 404 |
| Coaching | 3 | list reviews (empty), 404 propagation, get review 404 |

### Test infrastructure

- `FastAPI` app created without MT5 scheduler lifespan — no external services needed
- `dependency_overrides[get_db]` injects a fresh SQLite in-memory session per test
- `StaticPool` ensures all requests in a test share the same in-memory database
- Fixture scope: `app` = module, `client` = function (fresh DB per test)

### Bugs fixed during testing

1. **`datetime.utcnow()` sweep (completing Phase 7)** — route tests surfaced deprecation warnings in modules that Phase 7 didn't touch. Fixed in all 11 remaining locations:
   - `api/routes/coaching.py`, `api/routes/mt5_sync.py`, `api/routes/setups.py`
   - `core/account_analytics.py`, `core/performance_summary.py`
   - `models/account.py`, `models/setup.py`, `models/mistake_report.py`
   - `services/mt5_sync_service.py`, `services/output_writer.py`
   - Zero `datetime.utcnow()` calls remain anywhere in the codebase

### No regressions

- 435 existing unit + integration tests: all still pass
- 59 new route tests: all pass

## Current Test Coverage Summary

| Layer | Coverage |
|---|---|
| Unit (core logic) | Strong — metrics, analytics, parsers, validators, converters |
| Integration (repositories) | Strong — full CRUD for accounts and trades via real SQLite |
| Integration (import pipeline) | Moderate — CSV parse + output writer pipeline |
| Integration (MT5 sync) | Basic — connector/sync logic |
| **HTTP routes** | **Now covered — 59 tests across all route groups** |
| Coaching generation | Not tested — would require Anthropic API mock |
| Import multipart upload | Not tested — deferred to Phase 9+ |
| MT5/Telegram HTTP routes | Not tested — external service dependency |

## What Remains Rough

1. **No `pg_dump` backup story** — `docker compose down -v` destroys data; no documented recovery
2. **`CORS_ORIGINS` hardcoded in compose** — can't override via `.env` for remote deploys
3. **CI SQLite-only** — Postgres-specific migration issues can pass CI silently
4. **Coaching generation not route-tested** — would need Anthropic mock
5. **Import route not route-tested** — multipart form upload, practical to add later

## Next Phase: Phase 9 — MT5 Scheduler Resilience

**Scope:**
- Add `lookback_days` config field to MT5SyncConfig so the polling window is configurable (currently hardcoded to 7 days in `_poll_account()`)
- Add alert cooldown so the same error doesn't Telegram-spam every poll cycle
- Add jitter to polling interval to avoid synchronized spikes when multiple accounts poll at once
- Expose polling window in the `/mt5-sync` UI (currently no way to change it without code)

## Pending Push

Commits are local (push fails in WSL due to credential limitation). Run `git push origin main` from a Windows terminal with the GitHub PAT.
